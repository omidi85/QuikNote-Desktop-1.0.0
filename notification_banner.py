# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict
import re, webbrowser

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSizePolicy, QWidget, QScrollArea, QBoxLayout
)


class NotificationBanner(QFrame):
    """
    بنر نوتیف راست‌چین با بدنه‌ی اسکرول‌دار (برای متن‌های بلند).
    - CTA اختیاری + دکمه بستن قرمز/سفید
    - متن «قطعی» راست‌چین: هم PlainText هم HTML
    - set_fixed_size(width, height) برای تنظیم دستی ابعاد در OverlayManager
    """

    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("NotificationBanner")
        self.setProperty("kind", "info")
        self.setFrameShape(QFrame.StyledPanel)

        # بنر کلیک‌پذیر بماند
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # راست‌چین
        self.setLayoutDirection(Qt.RightToLeft)

        # استایل
        self.setStyleSheet("""
        QFrame#NotificationBanner {
            border-radius: 10px;
            border: 1px solid #cfe2ff;
            background: #e9f2ff;
        }
        QFrame#NotificationBanner[kind="warning"] { background: #fff4e5; border-color: #ffd8a8; }
        QFrame#NotificationBanner[kind="success"] { background: #e6fcf5; border-color: #c3fae8; }

        QLabel#Title { font-weight: 700; color: #0b132b; font-size: 15px; }
        QLabel#Message, QTextBrowser#Message { color: #111; font-size: 14px; }

        QPushButton#CTA {
            background: #0d6efd; color: #fff;
            padding: 8px 14px; border-radius: 6px; border: none;
            font-weight: 700;
        }
        QPushButton#CTA:hover { filter: brightness(1.06); }

        QPushButton#Close {
            background: #dc3545; color: #fff;
            padding: 6px 12px; border-radius: 6px; border: none;
            font-weight: 700;
        }
        QPushButton#Close:hover { filter: brightness(1.06); }
        """)

        # حداقل ارتفاع تا صفر نشود
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # ریشه
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # هدر
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr.setDirection(QBoxLayout.RightToLeft)

        self._close = QPushButton("✕");
        self._close.setObjectName("Close")
        self._close.clicked.connect(self._on_close)

        self._cta = QPushButton("مشاهده");
        self._cta.setObjectName("CTA")
        self._cta.clicked.connect(self._open_url)
        self._cta.setVisible(False)

        self._title = QLabel("اطلاع‌رسانی");
        self._title.setObjectName("Title")
        self._title.setWordWrap(False)
        self._title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        hdr.addWidget(self._close, 0, Qt.AlignVCenter)
        hdr.addWidget(self._cta, 0, Qt.AlignVCenter)
        hdr.addStretch(1)
        hdr.addWidget(self._title, 0, Qt.AlignRight | Qt.AlignVCenter)
        root.addLayout(hdr)

        # بدنه: ScrollArea
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea{background: transparent; border: none;}"
            "QScrollArea>viewport{background: transparent;}"
        )
        self._scroll.setLayoutDirection(Qt.RightToLeft)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._scroll.setMinimumHeight(80)  # محتوا دیده شود

        # هاست متن داخل اسکرول
        self._text_host = QWidget();
        self._text_host.setObjectName("NotifTextHost")
        self._text_host.setLayoutDirection(Qt.RightToLeft)
        self._text_host.setStyleSheet("#NotifTextHost{background: transparent;}")
        self._text_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        text_col = QVBoxLayout(self._text_host)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(6)

        # ✅ پیام: QTextBrowser (HTML کامل)
        from PySide6.QtWidgets import QTextBrowser
        self._msg = QTextBrowser(self);
        self._msg.setObjectName("Message")
        self._msg.setReadOnly(True)
        self._msg.setOpenExternalLinks(True)
        self._msg.setFrameShape(QFrame.NoFrame)
        self._msg.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._msg.setStyleSheet("QTextBrowser#Message{background: transparent;}")
        self._msg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._msg.setMinimumHeight(60)

        text_col.addWidget(self._msg, 1)
        self._scroll.setWidget(self._text_host)
        root.addWidget(self._scroll, 1)

        # لینک CTA و regex تشخیص HTML
        self._url: Optional[str] = None
        self._html_tag = re.compile(r"<[a-zA-Z][^>]*>")


    # اگر خواستی بیرون اندازه را ست کنی: banner.set_fixed_size(width=820, height=500)
    def set_fixed_size(self, width: Optional[int] = None, height: Optional[int] = None):
        if width is not None:
            self.setFixedWidth(int(width))
        if height is not None:
            self.setFixedHeight(int(height))

    # ---------- API ----------
    def set_notification(self, notif: Dict):
        """
        notif: {type,title,message, message_html?, cta:{label,url}}
        """
        # نوع/استایل
        t = (notif.get("type") or "info").lower()
        if "success" in t or "offer" in t:
            self.setProperty("kind", "success")
        elif "warning" in t:
            self.setProperty("kind", "warning")
        else:
            self.setProperty("kind", "info")
        self.style().unpolish(self);
        self.style().polish(self)

        # عنوان
        self._title.setText(str(notif.get("title") or "اطلاع‌رسانی"))
        try:
            self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._title.setStyleSheet("qproperty-alignment: AlignLeft; text-align: left;")
        except Exception:
            pass

        # متن: HTML-first
        raw_msg_html = notif.get("message_html")
        raw_msg = str(notif.get("message") or "")

        if raw_msg_html and str(raw_msg_html).strip():
            inner_html = str(raw_msg_html)
        elif self._html_tag.search(raw_msg):
            inner_html = raw_msg
        else:
            try:
                import html as _html
                inner_html = _html.escape(raw_msg).replace("\n", "<br/>")
            except Exception:
                inner_html = raw_msg.replace("\n", "<br/>")

        # رندر HTML
        self._msg.setHtml(inner_html)

        # CTA
        cta = notif.get("cta") or {}
        self._url = cta.get("url")
        self._cta.setText(cta.get("label") or "مشاهده")
        self._cta.setVisible(bool(self._url))

        # اسکرول بالا و تضمین نمایش
        try:
            self._scroll.verticalScrollBar().setValue(0)
        except Exception:
            pass

        # اگر قبلاً hide شده بود (مثلاً با Close)، دوباره نشان بده
        self.setVisible(True)
        self.show()

    # ---------- Actions ----------
    def _open_url(self):
        if self._url:
            webbrowser.open(self._url)

    def _on_close(self):
        self.hide()
        self.closed.emit()
