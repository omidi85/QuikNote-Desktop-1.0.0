# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional
import webbrowser

from PySide6.QtCore import Qt, QObject, QEvent, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

from .widgets.notification_banner import NotificationBanner
from .notifications import NotificationManager


# ========================= Top Warning (بالای صفحه) =========================

class _TopWarningBar(QWidget):
    """
    نوار هشدار بالاسری: متن قرمز + دکمه‌ی خرید/تمدید (اختیاری).
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TopWarningBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignCenter)

        self.lbl = QLabel("")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("""
            QLabel {
                color: #e31b23;              /* قرمز خوانا */
                font-weight: 600;
                font-size: 12px;
                background: transparent;
            }
        """)

        self.btn = QPushButton("خرید/تمدید")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet("""
            QPushButton {
                background: #20c997;
                color: #fff;
                border: none;
                border-radius: 12px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QPushButton:hover { filter: brightness(1.05); }
        """)
        self.btn.clicked.connect(self._open_url)
        self._url: str = ""

        lay.addWidget(self.btn, 0, Qt.AlignVCenter)
        lay.addWidget(self.lbl, 1, Qt.AlignVCenter)

        self.hide()

    def show_text(self, text: str, buy_url: str = ""):
        self.lbl.setText(text or "")
        self._url = buy_url or ""
        self.btn.setVisible(bool(self._url))
        self.setVisible(bool(text))

    def _open_url(self):
        if self._url:
            webbrowser.open(self._url)


# =========================== Overlay Container ==============================

class _OverlayContainer(QWidget):
    """
    ظرف شفافِ بالاسری که کل پنجره‌ی میزبان را می‌پوشاند.
    - کلیک‌ها را عبور می‌دهد (مزاحم دکمه‌های زیرین نمی‌شود).
    - فقط برای نگه داشتن نوار هشدار و محاسبه‌ی جای‌گذاری بنر استفاده می‌شود.
    - خودِ بنر «فرزندِ پنجره‌ی میزبان» است (نه این کانتینر) تا کلیک‌پذیر باشد.
    """
    def __init__(self, host_window: QWidget):
        super().__init__(host_window)
        self.setObjectName("OverlayContainer")

        # ظرفِ اوورلی کلیک‌ها را عبور دهد تا UI اصلی از کار نیفتد
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # نوار هشدار بالاسری
        self.top_warning = _TopWarningBar(self)
        lay.addWidget(self.top_warning, 0, Qt.AlignHCenter | Qt.AlignTop)

        # بنر نوتیف اینجا فقط مرجعش نگه داشته می‌شود
        self.banner: Optional[NotificationBanner] = None

        self.hide()

    def attach_banner(self, banner: NotificationBanner):
        """فقط مرجع بنر را نگه می‌داریم؛ بنر روی host parent شده است."""
        self.banner = banner

    def reposition(self):
        """
        ظرف را هم‌اندازه‌ی پنجره‌ی میزبان می‌کنیم و اگر بنر وجود/مرئی بود،
        آن را بالا-وسط (یا راست) می‌چینیم.
        """
        host = self.parentWidget()
        if not host:
            return

        # کل پنجره
        self.setGeometry(host.rect())
        self.raise_()

        # بنر را بالا نگه داریم (روی همه‌چیز)
        if self.banner and self.banner.isVisible():
            self.banner.raise_()
            # --- جای‌گذاری بنر (بالا-وسط) ---
            x = (host.width() - self.banner.width()) // 2
            y = 10
            # اگر می‌خواهی سمت راست بچسبد، به‌جای خط بالا:
            # x = host.width() - self.banner.width() - 16
            self.banner.move(max(0, x), max(0, y))


# ============================= Overlay Manager ==============================

class OverlayManager(QObject):
    """
    مدیریت اوورلی/نوتیف‌ها:
      - top_warning: متن قرمز + دکمه‌ی خرید/تمدید
      - banner: بنر صفی برای پیام‌های عمومی (نمایش با NotificationBanner)
    """
    def __init__(self, host_window: QWidget):
        super().__init__(host_window)
        self.host = host_window

        # ظرف شفاف بالاسری
        self.container = _OverlayContainer(host_window)

        # بنر به‌صورت «فرزند host_window» ساخته می‌شود تا کلیک‌پذیر بماند
        self.banner = NotificationBanner(host_window)
        self.banner.hide()

        # ⬇⬇⬇ اینجا عرض/ارتفاع بنر را خودت تنظیم کن ⬇⬇⬇
        # نمونه:
        self.set_banner_size(width=600, height=300)
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

        # بنر را به کانتینر معرفی می‌کنیم (برای reposition)
        self.container.attach_banner(self.banner)

        # صف نوتیف‌ها
        self.notifs = NotificationManager()
        self.notifs.attach_banner(self.banner)

        # اگر بنر بسته شد و هشدار هم مخفی بود، ظرف را پنهان کن
        self.banner.closed.connect(self._maybe_hide_container)

        # تغییرات پنجره را گوش می‌دهیم تا اوورلی/بنر را دوباره بچینیم
        self.host.installEventFilter(self)

    # ----------- اندازه‌ی بنر را اینجا تنظیم کن (هر زمان خواستی) -----------
    def set_banner_size(self, *, width: Optional[int] = None, height: Optional[int] = None):
        """
        call example:
            overlay.set_banner_size(width=820, height=500)
        """
        self.banner.set_fixed_size(width=width, height=height)
        self.container.reposition()

    # --------------------------- Event handling ------------------------------
    def eventFilter(self, obj, ev):
        if obj is self.host and ev.type() in (
            QEvent.Resize, QEvent.Move, QEvent.Show,
            QEvent.LayoutRequest, QEvent.WindowStateChange
        ):
            try:
                self.container.reposition()
            except Exception:
                pass
        return False

    def _ensure_visible_soon(self):
        QTimer.singleShot(0, lambda: (self.container.show(), self.container.reposition(), self.banner.raise_()))

    def _maybe_hide_container(self):
        # اگر بنر مخفی است و هشدار هم نیست، ظرف را پنهان کنیم
        if self.banner.isHidden() and not self.container.top_warning.isVisible():
            self.container.hide()

    # --------------------------------- API ----------------------------------
    def enqueue(self, items: List[Dict], base_url: str = ""):
        """
        بنر صفی برای پیام‌های عمومی.
        """
        self._ensure_visible_soon()
        self.notifs.enqueue(items, base_url)
        self.banner.show()
        self.container.reposition()
        self.banner.raise_()

    def show_top_warning(self, text: str, base_url: str = ""):
        """نمایش/بروزرسانی متن قرمز بالاسری + لینک خرید/تمدید."""
        buy_url = (base_url.rstrip("/") + "/shop/") if base_url else ""
        self._ensure_visible_soon()
        self.container.top_warning.show_text(text, buy_url)
        self.container.reposition()

    def clear_top_warning(self):
        self.container.top_warning.show_text("", "")
        self.container.reposition()
        self._maybe_hide_container()


__all__ = ["OverlayManager"]
