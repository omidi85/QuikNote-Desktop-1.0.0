# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import threading
import urllib.request
import urllib.error
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QComboBox, QFileDialog, QInputDialog,
    QFrame, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QObject, QPropertyAnimation,
    QEasingCurve, QTimer, Property, QPoint
)
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

# ====== سرویس‌های برنامه ======
from ..title_service import (
    generate_titles_pipeline, list_records,
    remove_titles_from_record, remove_records, update_title_in_record
)
from ..storage_sqlite import get_setting  # برای خواندن کلید API در صورت نبود در state


# ========================== Toast (وسط صفحه، سبز پیش‌فرض) ==========================
class Toast(QFrame):
    def __init__(self, parent, text, kind="info", msec=3500):
        super().__init__(parent)
        self.setObjectName("toast")

        bg = {
            "info":  "#16a34a",   # سبز
            "warn":  "#f59e0b",   # زرد
            "error": "#dc2626"    # قرمز
        }.get((kind or "info").lower(), "#16a34a")

        self.setStyleSheet(f"""
            QFrame#toast {{
                background: {bg};
                color: #fff;
                border-radius: 12px;
            }}
            QLabel {{
                color: #fff;
                font-weight: 500;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        self.lbl = QLabel(text)
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fx.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._timer.start(max(1500, int(msec)))

    def showEvent(self, e):
        super().showEvent(e)
        host = self.window() or self.parent()
        if host:
            self.adjustSize()
            x = (host.width() - self.width()) // 2
            y = (host.height() - self.height()) // 2
            self.move(max(8, x), max(8, y))
        self._fade_in.start()

    def _fade_out(self):
        fade_out = QPropertyAnimation(self._fx, b"opacity", self)
        fade_out.setDuration(300)
        fade_out.setStartValue(self._fx.opacity())
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(self.deleteLater)
        fade_out.start()


def show_toast(widget, text, kind="info", msec=3500):
    t = Toast(widget.window() or widget, text, kind=kind, msec=msec)
    t.raise_()
    t.show()


def humanize_error(msg: str) -> str:
    s = (msg or "").strip()
    if "HTTP 403" in s or "Forbidden" in s or "<!DOCTYPE html" in s:
        return "عدم دسترسی به سرور هوش مصنوعی (HTTP 403). لطفاً کلید/دسترسی را بررسی کنید."
    if s.startswith("❌ تعداد تلاش‌ها تمام شد"):
        return "اتصال برقرار نشد: تعداد تلاش‌ها تمام شد. لطفاً کلید/دسترسی را بررسی کنید."
    return s if len(s) <= 300 else s[:300] + "…"


# ======================= Loader کوچک کنار دکمه =======================
class _MiniFile(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 36)
        self._scale = 0.001
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fx.setOpacity(0.0)

    def getScale(self): return self._scale
    def setScale(self, v): self._scale = max(0.001, float(v)); self.update()
    scale = Property(float, getScale, setScale)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = p.transform()
        t.translate(self.width()/2, self.height()/2)
        t.scale(self._scale, self._scale)
        t.translate(-self.width()/2, -self.height()/2)
        p.setTransform(t)
        p.setBrush(QBrush(QColor("#007bff"))); p.setPen(QPen(Qt.NoPen))
        p.drawRoundedRect(0, 0, 28, 36, 4, 4)
        p.setBrush(QBrush(Qt.white))
        p.drawRoundedRect(5, 6, 18, 3, 2, 2)
        p.drawRoundedRect(5, 12, 12, 3, 2, 2)


class MiniLoader(QWidget):
    def __init__(self, parent=None, items=5, duration=4000):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setMinimumWidth(160)
        self._files = []
        self._an_pos, self._an_op, self._an_sc = [], [], []
        self._duration = int(duration)
        for i in range(items):
            w = _MiniFile(self)
            w.move(-40, (self.height()-w.height())//2)
            self._files.append(w)
        self.hide()

    def _start_for(self, w: _MiniFile, delay_ms: int):
        h = self.height(); w_y = (h - w.height()) // 2
        self_w = max(1, self.width())

        an_pos = QPropertyAnimation(w, b"pos", self)
        an_pos.setDuration(self._duration)
        an_pos.setStartValue(QPoint(-40, w_y))
        an_pos.setKeyValueAt(0.45, QPoint(self_w//2 - w.width()//2, w_y))
        an_pos.setEndValue(QPoint(self_w, w_y))
        an_pos.setLoopCount(-1); an_pos.setEasingCurve(QEasingCurve.InOutQuad)

        an_op = QPropertyAnimation(w.graphicsEffect(), b"opacity", self)
        an_op.setDuration(self._duration)
        an_op.setStartValue(0.0); an_op.setKeyValueAt(0.15, 1.0); an_op.setKeyValueAt(0.85, 1.0); an_op.setEndValue(0.0)
        an_op.setLoopCount(-1)

        an_sc = QPropertyAnimation(w, b"scale", self)
        an_sc.setDuration(self._duration)
        an_sc.setStartValue(0.001); an_sc.setKeyValueAt(0.5, 1.15); an_sc.setEndValue(0.001)
        an_sc.setLoopCount(-1)

        self._an_pos.append(an_pos); self._an_op.append(an_op); self._an_sc.append(an_sc)

        def _start():
            an_pos.start(); an_op.start(); an_sc.start()
        QTimer.singleShot(max(0, delay_ms), _start)

    def start(self):
        self._an_pos.clear(); self._an_op.clear(); self._an_sc.clear()
        self.show(); self.raise_()
        for i, w in enumerate(self._files):
            w.move(-40, (self.height()-w.height())//2)
            self._start_for(w, i*420)

    def stop(self):
        self.hide()
        self._an_pos.clear(); self._an_op.clear(); self._an_sc.clear()

    def resizeEvent(self, e):
        for w in self._files:
            w.move(w.x(), (self.height()-w.height())//2)
        super().resizeEvent(e)

    def paintEvent(self, e):
        pass


# ====================== Worker تولید عناوین ======================
class Worker(QObject):
    sigLog  = Signal(str)
    sigDone = Signal(list, str)   # titles, out_dir
    sigFail = Signal(str)

    def __init__(self, api_key: str, topic: str):
        super().__init__()
        self.api_key = api_key or ""
        self.topic = topic

    def _log(self, msg: str):
        self.sigLog.emit(msg)

    def run(self):
        try:
            titles, out_dir = generate_titles_pipeline(self.api_key, self.topic, logger=self._log)
            self.sigDone.emit(titles, out_dir)
        except Exception as e:
            self.sigFail.emit(str(e))


# ============================ تب عناوین ============================
class TitlesTab(QWidget):
    """
    همهٔ قابلیت‌های نسخهٔ شما حفظ شده +
    - Toast سبز وسط صفحه
    - دکمه «تست سرور هوش مصنوعی» با پینگ سبک (بدون Retry)
    - ایمن‌سازی تماس‌های UI از تردها
    """
    sigQueueArticles = Signal(str, list, int)  # record_id, payloads=[{"seed": "..."}], delay
    sigToast = Signal(str, str)                # text, kind

    def __init__(self, state: dict | None = None, parent=None):
        super().__init__(parent)
        self.state = state or {}

        self.thread: Optional[QThread] = None
        self.worker: Optional[Worker] = None
        self._test_thread: Optional[threading.Thread] = None
        self._test_abort = False

        self._build_ui()
        self._refresh_records()

        # نمایش Toast فقط در UI-thread
        self.sigToast.connect(self._on_toast)

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)

        # Left: رکوردها
        box_left = QGroupBox("رکوردها")
        vl = QVBoxLayout(box_left)

        self.list_records = QListWidget()
        self.list_records.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_records.currentItemChanged.connect(self._on_select_record)
        vl.addWidget(self.list_records, 1)

        row_left = QHBoxLayout()
        self.btn_open_dir = QPushButton("باز کردن پوشه خروجی"); self.btn_open_dir.clicked.connect(self._on_open_dir)
        self.btn_export = QPushButton("خروجی CSV"); self.btn_export.clicked.connect(self._on_export)
        self.btn_delete_record = QPushButton("حذف رکورد(ها)"); self.btn_delete_record.clicked.connect(self._on_delete_records)
        row_left.addWidget(self.btn_open_dir)
        row_left.addWidget(self.btn_export)
        row_left.addWidget(self.btn_delete_record)
        row_left.addStretch()
        vl.addLayout(row_left)

        top.addWidget(box_left, 1)

        # Right: تولید عناوین
        box_right = QGroupBox("تولید عناوین جدید")
        vr = QVBoxLayout(box_right)

        self.cmb_topic = QComboBox()
        self.cmb_topic.setEditable(True)
        self.cmb_topic.setInsertPolicy(QComboBox.InsertAtTop)
        self.cmb_topic.setMinimumContentsLength(20)
        vr.addWidget(self.cmb_topic)

        row_ctrl = QHBoxLayout()
        self.btn_generate = QPushButton("🚀 شروع تولید ایده‌ها")
        row_ctrl.addWidget(self.btn_generate)

        self.btn_test = QPushButton("تست سرور هوش مصنوعی")
        self.btn_test.setToolTip("پینگ سبک به API (بدون تولید محتوا و بدون Retry)")
        self.btn_test.clicked.connect(self._on_test_gemini)
        row_ctrl.addWidget(self.btn_test)

        self.mini_loader = MiniLoader(self)
        self.mini_loader.setFixedWidth(180)
        row_ctrl.addWidget(self.mini_loader)

        row_ctrl.addStretch()
        vr.addLayout(row_ctrl)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        vr.addWidget(self.txt_log, 1)

        top.addWidget(box_right, 1)

        # Bottom: عناوین قابل انتخاب
        box_bottom = QGroupBox("عناوین قابل انتخاب")
        vb = QVBoxLayout(box_bottom)

        self.list_titles = QListWidget()
        vb.addWidget(self.list_titles, 1)

        row_actions = QHBoxLayout()
        self.btn_send   = QPushButton("ارسال به تب تولید مقاله (فقط صف)")
        self.btn_delete = QPushButton("حذف عنوان‌های انتخاب‌شده")
        self.btn_edit   = QPushButton("ویرایش عنوان")
        row_actions.addWidget(self.btn_send)
        row_actions.addWidget(self.btn_delete)
        row_actions.addWidget(self.btn_edit)
        row_actions.addStretch()
        vb.addLayout(row_actions)

        root.addLayout(top, 1)
        root.addWidget(box_bottom, 2)
        box_bottom.setMinimumHeight(300)

        # اتصالات
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_send.clicked.connect(self._on_send)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_edit.clicked.connect(self._on_edit_title)

    # ---------- Toast / Log ----------
    def _on_toast(self, text: str, kind: str = "info"):
        show_toast(self, humanize_error(text), kind)

    def _append_log(self, s: str):
        try:
            self.txt_log.append(humanize_error(str(s)))
        except Exception:
            pass

    # ---------- Thread cleanup ----------
    def _cleanup_thread(self):
        try:
            if self.thread and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait(2000)
        except Exception:
            pass
        try:
            if self.worker:
                self.worker.deleteLater()
        except Exception:
            pass
        try:
            self.mini_loader.stop()
            self.btn_generate.setEnabled(True)
        except Exception:
            pass

    # ---------- Generate ----------
    def _get_api_key(self) -> str:
        key = ""
        try:
            key = (self.state.get("gemini_api_key") or "").strip() if isinstance(self.state, dict) else ""
        except Exception:
            key = ""
        if not key:
            key = (get_setting("gemini_api_key", "") or "").strip()
        return key

    def _on_generate(self):
        topic = (self.cmb_topic.currentText() or "").strip()
        if not topic:
            QMessageBox.information(self, "اطلاع", "موضوع را وارد کنید.")
            return
        api_key = self._get_api_key()
        if not api_key:
            QMessageBox.warning(self, "کلید API", "کلید Gemini را در تنظیمات ذخیره کنید.")
            return

        self._cleanup_thread()
        self.thread = QThread(self)
        self.worker = Worker(api_key, topic)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.sigLog.connect(self._append_log)
        self.worker.sigDone.connect(self._on_done)
        self.worker.sigFail.connect(self._on_fail)

        self.btn_generate.setEnabled(False)
        self.mini_loader.start()
        self.thread.start()

    def _on_done(self, titles: list, out_dir: str):
        self._append_log(f"✅ تولید {len(titles)} عنوان انجام شد.")
        self._refresh_records()
        try:
            self.mini_loader.stop()
            self.btn_generate.setEnabled(True)
        except Exception:
            pass

    def _on_fail(self, msg: str):
        self.sigToast.emit(msg, "error")
        self._append_log("❌ " + msg)
        try:
            self.mini_loader.stop()
            self.btn_generate.setEnabled(True)
        except Exception:
            pass

    # ---------- Records & Titles ----------
    def _refresh_records(self, preserve_id: str | None = None):
        if preserve_id is None:
            it = self.list_records.currentItem()
            rec = (it.data(Qt.UserRole) if it else None) or {}
            preserve_id = rec.get("id")

        self.list_records.clear()
        keep = None
        for r in list_records():
            it = QListWidgetItem(f"{r.get('topic','')}  —  {r.get('count',0)}")
            it.setData(Qt.UserRole, r)
            self.list_records.addItem(it)
            if preserve_id and r.get("id") == preserve_id:
                keep = it
        if keep:
            self.list_records.setCurrentItem(keep)

    def _on_select_record(self, cur: QListWidgetItem, prev: QListWidgetItem = None):
        rec = (cur.data(Qt.UserRole) if cur else None) or {}
        self._load_titles(rec)

    def _load_titles(self, rec: dict):
        self.list_titles.clear()
        titles = (rec or {}).get("titles") or []

        pairs_path = os.path.join((rec or {}).get("out_dir", ""), "titles_full.json")
        pairs = []
        if os.path.exists(pairs_path):
            try:
                with open(pairs_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or []
                    if isinstance(data, dict):
                        pairs = data.get("items", []) or []
                    elif isinstance(data, list):
                        pairs = data
            except Exception:
                pairs = []

        if pairs:
            for row in pairs:
                t = (row.get("title") or "").strip()
                if not t:
                    continue
                it = QListWidgetItem(t)
                it.setData(Qt.UserRole, {"seed": t})
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                it.setCheckState(Qt.Unchecked)
                self.list_titles.addItem(it)
            return

        for txt in titles:
            t = (txt or "").strip()
            if not t:
                continue
            it = QListWidgetItem(t)
            it.setData(Qt.UserRole, {"seed": t})
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            it.setCheckState(Qt.Unchecked)
            self.list_titles.addItem(it)

    def _on_delete_records(self):
        sels = self.list_records.selectedItems()
        if not sels:
            QMessageBox.information(self, "اطلاع", "حداقل یک رکورد را انتخاب کنید.")
            return
        ids = []
        for it in sels:
            rec = it.data(Qt.UserRole) or {}
            if rec.get("id"):
                ids.append(rec["id"])
        if not ids:
            QMessageBox.warning(self, "خطا", "شناسه رکورد نامعتبر است.")
            return
        ok = QMessageBox.question(self, "تأیید حذف", "آیا از حذف رکورد(ها) مطمئن هستید؟")
        if ok != QMessageBox.Yes:
            return
        removed = remove_records(ids)
        QMessageBox.information(self, "نتیجه", f"{removed} رکورد حذف شد.")
        self._refresh_records(preserve_id=None)
        self.list_titles.clear()

    def _on_delete(self):
        it = self.list_records.currentItem()
        if not it:
            QMessageBox.information(self, "اطلاع", "ابتدا یک رکورد را انتخاب کنید.")
            return
        rec = it.data(Qt.UserRole) or {}
        rid = rec.get("id", "")
        if not rid:
            QMessageBox.warning(self, "خطا", "شناسه رکورد نامعتبر است.")
            return

        to_remove = []
        for i in range(self.list_titles.count()):
            item = self.list_titles.item(i)
            if item.checkState() == Qt.Checked:
                seed = (item.data(Qt.UserRole) or {}).get("seed") or item.text()
                if seed:
                    to_remove.append(seed)
        if not to_remove:
            QMessageBox.information(self, "اطلاع", "حداقل یک عنوان را تیک بزنید.")
            return

        remove_titles_from_record(rid, to_remove)

        self._refresh_records(preserve_id=rid)
        for i in range(self.list_records.count()):
            item = self.list_records.item(i)
            r = item.data(Qt.UserRole) or {}
            if r.get("id") == rid:
                self.list_records.setCurrentItem(item)
                self._load_titles(r)
                break

    def _on_edit_title(self):
        it_rec = self.list_records.currentItem()
        if not it_rec:
            QMessageBox.information(self, "اطلاع", "ابتدا یک رکورد را انتخاب کنید.")
            return
        rec = it_rec.data(Qt.UserRole) or {}
        rid = rec.get("id", "")

        target = self.list_titles.currentItem()
        if not target:
            for i in range(self.list_titles.count()):
                it = self.list_titles.item(i)
                if it.checkState() == Qt.Checked:
                    target = it
                    break
        if not target:
            QMessageBox.information(self, "اطلاع", "یک عنوان را انتخاب یا فقط یکی را تیک بزنید.")
            return

        old_text = (target.data(Qt.UserRole) or {}).get("seed") or target.text()
        new_text, ok = QInputDialog.getText(self, "ویرایش عنوان", "عنوان جدید:", text=old_text)
        if not ok or not (new_text or "").strip():
            return
        new_text = new_text.strip()
        if new_text == old_text:
            return

        if update_title_in_record(rid, old_text, new_text):
            target.setText(new_text)
            ud = target.data(Qt.UserRole) or {}
            ud["seed"] = new_text
            target.setData(Qt.UserRole, ud)
            self._refresh_records(preserve_id=rid)
            QMessageBox.information(self, "موفق", "عنوان ویرایش شد.")
        else:
            QMessageBox.warning(self, "خطا", "ویرایش عنوان انجام نشد.")

    def _on_send(self):
        it = self.list_records.currentItem()
        if not it:
            QMessageBox.information(self, "اطلاع", "ابتدا یک رکورد را انتخاب کنید.")
            return
        rec = it.data(Qt.UserRole) or {}
        rid = rec.get("id", "")
        if not rid:
            QMessageBox.warning(self, "خطا", "شناسه رکورد نامعتبر است.")
            return

        selected_payloads = []
        for i in range(self.list_titles.count()):
            item = self.list_titles.item(i)
            if item.checkState() == Qt.Checked:
                seed = (item.data(Qt.UserRole) or {}).get("seed") or item.text()
                if seed:
                    selected_payloads.append({"seed": seed})

        if not selected_payloads:
            QMessageBox.information(self, "اطلاع", "حداقل یک عنوان را تیک بزنید.")
            return

        delay_sec = -1  # فقط صف؛ تولید در تب مقاله
        self.sigQueueArticles.emit(rid, selected_payloads, delay_sec)
        QMessageBox.information(self, "ثبت شد", "عناوین به تب تولید مقاله صف شدند. از همان تب «شروع تولید» را بزنید.")

    # ---------- Helpers ----------
    def _on_open_dir(self):
        it = self.list_records.currentItem()
        if not it:
            QMessageBox.information(self, "اطلاع", "ابتدا یک رکورد را انتخاب کنید.")
            return
        rec = it.data(Qt.UserRole) or {}
        out_dir = rec.get("out_dir", "")
        if out_dir and os.path.isdir(out_dir):
            import webbrowser
            webbrowser.open('file://' + os.path.abspath(out_dir))
        else:
            QMessageBox.information(self, "اطلاع", "پوشهٔ خروجی موجود نیست.")

    def _on_export(self):
        it = self.list_records.currentItem()
        if not it:
            QMessageBox.information(self, "اطلاع", "ابتدا یک رکورد را انتخاب کنید.")
            return
        rec = it.data(Qt.UserRole) or {}
        titles = (rec or {}).get("titles") or []
        if not titles:
            QMessageBox.information(self, "اطلاع", "عنوانی برای خروجی وجود ندارد.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره CSV", "titles.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("title\n")
                for t in titles:
                    f.write(f"{str(t).replace(',', '،')}\n")
            QMessageBox.information(self, "موفق", "فایل CSV ذخیره شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

    # فراخوانی از تب مقاله پس از تولید موفق
    def on_article_generated(self, record_id: str, seed: str):
        seed = (seed or "").strip()
        if not seed:
            return
        rid = (record_id or "").strip()
        try:
            remove_titles_from_record(rid, [seed])
        except Exception:
            pass
        try:
            for i in range(self.list_titles.count() - 1, -1, -1):
                it = self.list_titles.item(i)
                data = it.data(Qt.UserRole) or {}
                s = (data.get("seed") or it.text() or "").strip()
                if s == seed:
                    self.list_titles.takeItem(i)
                    break
        except Exception:
            pass
        try:
            cur = self.list_records.currentItem()
            if cur:
                rec = cur.data(Qt.UserRole) or {}
                cnt = int(rec.get("count", 0))
                if cnt > 0:
                    rec["count"] = cnt - 1
                    cur.setData(Qt.UserRole, rec)
                    topic = rec.get("topic","")
                    cur.setText(f"{topic}  —  {rec.get('count',0)}")
        except Exception:
            pass

    # ---------- تست سرور (پینگ سبک بدون Retry) ----------
    def _on_test_gemini(self):
        api_key = self._get_api_key()
        if not api_key:
            self.sigToast.emit("کلید Gemini را در تنظیمات ذخیره کنید.", "warn")
            return

        # جلوگیری از چند تست هم‌زمان
        if self._test_thread and self._test_thread.is_alive():
            self.sigToast.emit("تست در حال اجراست…", "info")
            return

        self._test_abort = False
        self.btn_test.setEnabled(False)

        def worker():
            try:
                # Endpoint سبک: لیست مدل‌ها
                url = "https://generativelanguage.googleapis.com/v1beta/models"
                req = urllib.request.Request(url, method="GET", headers={
                    "x-goog-api-key": api_key,
                    "accept": "application/json",
                    "user-agent": "QuikNote/1.0 (TitleTab Test)"
                })
                with urllib.request.urlopen(req, timeout=7) as resp:
                    code = resp.getcode()
                    if 200 <= code < 300:
                        self.sigToast.emit("اتصال برقرار است.", "info")
                    else:
                        self.sigToast.emit(f"پاسخ غیرمنتظره از سرور: HTTP {code}", "warn")
            except urllib.error.HTTPError as he:
                # 4xx/5xx
                if he.code == 403:
                    self.sigToast.emit("عدم دسترسی (HTTP 403). کلید/دسترسی را بررسی کنید.", "error")
                elif he.code == 401:
                    self.sigToast.emit("Unauthorized (HTTP 401). کلید نامعتبر است.", "error")
                else:
                    self.sigToast.emit(f"HTTP {he.code}", "error")
            except urllib.error.URLError as ue:
                self.sigToast.emit(f"عدم‌دسترسی به اینترنت/سرور: {ue.reason}", "error")
            except Exception as e:
                self.sigToast.emit(str(e), "error")
            finally:
                QTimer.singleShot(0, lambda: self.btn_test.setEnabled(True))

        self._test_thread = threading.Thread(target=worker, daemon=True)
        self._test_thread.start()
