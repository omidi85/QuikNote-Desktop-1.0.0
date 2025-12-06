# -*- coding: utf-8 -*-
from __future__ import annotations
import webbrowser
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QFont

from .storage import load, save
from .api import CentralAPI
from .hwid import get_hwid  # used in settings tab

# --- modular tabs ---
"""
برای بهبود سرعت لود اولیه:
 - تب‌ها را Lazy-load می‌کنیم (فقط داشبورد در شروع ساخته می‌شود)
 - درخواست شبکه هدر (profile) را به پس‌زمینه منتقل می‌کنیم
"""

# فقط داشبورد را ابتدا می‌سازیم
from .tabs.dashboard_tab import DashboardTab

# منبع واحد اعتبار
from .credits import get as credits_get
from .widgets.notification_banner import NotificationBanner
from .notifications import NotificationManager


# === Original theming (Light/Dark) ===
def _apply_theme(app, mode: str = "dark"):
    if app is None: return
    from PySide6.QtGui import QPalette, QColor
    mode = (mode or "dark").lower()
    if mode == "light":
        bg = QColor("#f0f4f8"); text = QColor("#333333"); panel = QColor("#ffffff")
        accent = QColor("#007bff"); success = QColor("#28a745")
        p = QPalette()
        p.setColor(QPalette.Window, bg)
        p.setColor(QPalette.WindowText, text)
        p.setColor(QPalette.Base, panel)
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, panel)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, accent)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(p)
        app.setStyleSheet("""
QLabel, QTextEdit, QLineEdit { background-color: transparent; }

QWidget { 
    background-color: #ffffff; 
    color: #1a1d21; 
    font-family: 'Segoe UI', sans-serif; 
}

QLabel, QTextEdit, QLineEdit {
    background-color: transparent;
}
            QLabel { color: #333333; }
            QLineEdit, QTextEdit { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 4px; padding: 8px; min-height: 30px; }
            QPushButton { background-color: #007bff; color: white; border: none; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #0069d9; }
            QPushButton:pressed { background-color: #005cbf; }
            QProgressBar { background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #007bff; }
            QComboBox { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 4px; padding: 8px; min-height: 30px; }
            QComboBox::drop-down { subcontrol-position: right; width: 20px; border-left: 1px solid #ced4da; }
            QToolButton { background: transparent; border: none; color: #333333; }
            QToolButton:checked { background: #e2e6ea; border-radius: 4px; }
            QToolButton:hover { background: #dee2e6; border-radius: 4px; }
            .credit-label { background-color: #28a745; color: white; border-radius: 20px; padding: 5px 10px; font-weight: bold; }
            QGroupBox { border: 1px solid #ced4da; border-radius: 4px; padding: 10px; background-color: #ffffff; }
            .support-ticket { border: 1px solid #ced4da; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
            .support-ticket-admin { background-color: #e6f4ea; }
        """)
    else:
        bg = QColor(""); text = QColor("#d1d5da"); panel = QColor("#212529")
        accent = QColor("#0366d6"); success = QColor("#28a745")
        p = QPalette()
        p.setColor(QPalette.Window, bg)
        p.setColor(QPalette.WindowText, text)
        p.setColor(QPalette.Base, panel)
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, panel)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, accent)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(p)
        app.setStyleSheet("""
QLabel, QTextEdit, QLineEdit { background-color: transparent; }

QWidget { 
    background-color: #1a1d21; 
    color: #d1d5da; 
    font-family: 'Segoe UI', sans-serif; 
}

/* برای متن‌ها بکگراند نذار */
QLabel, QTextEdit, QLineEdit {
    background-color: transparent;
}
            QLabel { color: #d1d5da; }
            QLineEdit, QTextEdit { background-color: #212529; border: 1px solid #343a40; border-radius: 4px; padding: 8px; min-height: 30px; color: #d1d5da; }
            QPushButton { background-color: #0366d6; color: white; border: none; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #0353b3; }
            QPushButton:pressed { background-color: #03408f; }
            QProgressBar { background-color: #343a40; border: 1px solid #495057; border-radius: 4px; text-align: center; color: #d1d5da; }
            QProgressBar::chunk { background-color: #0366d6; }
            QComboBox { background-color: #212529; border: 1px solid #343a40; border-radius: 4px; padding: 8px; min-height: 30px; color: #d1d5da; }
            QComboBox::drop-down { subcontrol-position: right; width: 20px; border-left: 1px solid #343a40; }
            QToolButton { background: transparent; border: none; color: #d1d5da; }
            QToolButton:checked { background: #2c313a; border-radius: 4px; }
            QToolButton:hover { background: #343a40; border-radius: 4px; }
            .credit-label { background-color: #28a745; color: white; border-radius: 20px; padding: 5px 10px; font-weight: bold; }
            QGroupBox { border: 1px solid #495057; border-radius: 4px; padding: 10px; background-color: #212529; }
            .support-ticket { border: 1px solid #495057; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
            .support-ticket-admin { background-color: #2d4739; }
        """)


class QuikNoteApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('QuikNote')
        self.setMinimumSize(980, 600)
        self.setLayoutDirection(Qt.RightToLeft)

        self.state = load()
        self._theme = 'light'
        _apply_theme(QApplication.instance(), self._theme)

        # --- TABS (content) ---
        self.tabs = QTabWidget()
        self.tabs.tabBar().setVisible(False)  # hide tab bar; navigate via sidebar
        self._init_tabs()

        # --- Header (top bar) ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)

        # Credits badge (ظاهر قبلی)
        self.lbl_user_credits = QPushButton('0 اعتبار')
        self.lbl_user_credits.setFlat(True)
        self.lbl_user_credits.setStyleSheet("background-color: #28a745; color: white; border-radius: 20px; padding: 5px 10px; font-weight: bold;")

        self.lbl_user_email = QLabel(self.state.get('central_email', 'user@example.com'))
        self.lbl_user_name = QLabel(self.state.get('display_name', 'کاربر'))

        header_layout.addWidget(self.lbl_user_credits)
        header_layout.addWidget(self.lbl_user_email)
        header_layout.addWidget(self.lbl_user_name)
        header_layout.addStretch()

        app_title = QLabel('QuikNote')
        app_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(app_title)

        # --- Main content with right sidebar ---
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setDirection(QBoxLayout.RightToLeft)

        # content
        main_layout.addWidget(self.tabs, 1)

        # sidebar (دقیقاً مثل قبل)
        sidebar = QGroupBox("منو")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)
        sidebar.setFixedWidth(200)

        names = [
            ('داشبورد', 0),
            ('ایده یابی تولید محتوا', 1),
            ('مقاله با کلمه کلیدی', 2),
            ('تنظیمات', 3),
            ('پشتیبانی', 4),
            ('خرید اشتراک', 5),
            ('اخبار و اطلاعیه ها', 6),
            ('منتشر شده‌ها', 7),  # 🆕 اضافه شد
        ]
        self._sidebar_btns = []
        for label, idx in names:
            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setStyleSheet("text-align: right; padding: 10px; border-radius: 4px;")
            btn.clicked.connect(lambda checked=False, i=idx: self.tabs.setCurrentIndex(i))
            sidebar_layout.addWidget(btn)
            self._sidebar_btns.append(btn)

        sidebar_layout.addStretch()

        footer_box = QGroupBox()
        fl = QVBoxLayout(footer_box)
        fl.setContentsMargins(5, 5, 5, 5)
        fl.setSpacing(5)
        fl.addWidget(QLabel('Version 1.1.0'))
        fl.addWidget(QLabel('©QuikNote'))
        theme_btn = QPushButton('حالت روشن' if self._theme == 'dark' else 'حالت تیره')
        theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn = theme_btn
        fl.addWidget(theme_btn)
        sidebar_layout.addWidget(footer_box)

        main_layout.addWidget(sidebar)

        # --- Root layout ---
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(header)
        root.addWidget(main_content, 1)
        self.setLayout(root)

        # اتصالات اعتبار به نشان سبز
        self._connect_credit_signals()

        # initial refresh
        QTimer.singleShot(0, self._refresh_header_async)
        QTimer.singleShot(0, self._center_on_screen)

        # متغیرهای صف تولید مقاله (seed-only، سازگاری قدیمی)
        self._article_queue = []
        self._queue_delay = 0
        self._current_rec_id = ""
        self._current_seed = ""
        self._article_ready_hook_connected = False

        # اتصال یک‌بارهٔ سیگنال آماده‌شدن مقاله (نسخه جدید)
        self._article_ready_wired = False

    # ---------- Tabs / Lazy-load ----------
    def _init_tabs(self):
        # فقط داشبورد را می‌سازیم
        self.tab_dashboard = DashboardTab(self.state, self)
        self.tabs.addTab(self.tab_dashboard, 'داشبورد')

        # تب‌های دیگر را به صورت placeholder اضافه می‌کنیم و بعداً بارگذاری می‌کنیم
        self._lazy_tabs = {
            1: 'titles',    # ایده یابی تولید محتوا
            2: 'article',   # مقاله با کلمه کلیدی
            3: 'settings',  # تنظیمات
            4: 'support',   # پشتیبانی
            5: 'billing',   # خرید اشتراک
            6: 'news',      # اخبار و اطلاعیه ها
            7: 'published',  # 🆕 تب منتشر شده‌ها

        }

        for idx in range(1, 8):
            placeholder = QLabel('در حال بارگذاری...')
            placeholder.setAlignment(Qt.AlignCenter)
            self.tabs.addTab(placeholder, [
                'داشبورد',
                'ایده یابی تولید محتوا',
                'مقاله با کلمه کلیدی',
                'تنظیمات',
                'پشتیبانی',
                'خرید اشتراک',
                'اخبار و اطلاعیه ها',
                'منتشر شده‌ها',   # 🆕 عنوان تب جدید

            ][idx])

        # بارگذاری تنبل هنگام تغییر تب
        self.tabs.currentChanged.connect(self._ensure_tab_loaded)

    def _ensure_tab_loaded(self, index: int):
        key = getattr(self, '_lazy_tabs', {}).get(index)
        if not key:
            return  # داشبورد یا قبلاً لود شده

        # اگر قبلاً ساخته شده باشد، عبور کن
        if key == 'titles' and hasattr(self, 'tab_titles'):    return
        if key == 'article' and hasattr(self, 'tab_article'):   return
        if key == 'settings' and hasattr(self, 'tab_settings'):  return
        if key == 'support' and hasattr(self, 'tab_support'):   return
        if key == 'billing' and hasattr(self, 'tab_billing'):   return
        if key == 'news' and hasattr(self, 'tab_news'):      return
        if key == 'published' and hasattr(self, 'tab_published'): return  # 🆕

        try:
            if key == 'titles':
                from .tabs.titles_tab import TitlesTab
                self.tab_titles = TitlesTab(self.state, self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_titles, 'ایده یابی تولید محتوا')

            elif key == 'article':
                from .tabs.article_tab import ArticleTab
                self.tab_article = ArticleTab(self.state, self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_article, 'مقاله با کلمه کلیدی')
                self._connect_credit_signals()
                self._wire_article_ready_once()

            elif key == 'settings':
                from .tabs.settings_tab import SettingsTab
                self.tab_settings = SettingsTab(self.state, self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_settings, 'تنظیمات')
                try:
                    self.tab_settings.sigSaved.connect(self._on_settings_saved)
                except Exception:
                    pass

            elif key == 'support':
                from .tabs.support_tab import SupportTab
                self.tab_support = SupportTab(self.state, self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_support, 'پشتیبانی')

            elif key == 'billing':
                from .tabs.billing_tab import BillingTab
                self.tab_billing = BillingTab(self.state, self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_billing, 'خرید اشتراک')

            elif key == 'news':
                from .tabs.news_tab import NewsTab
                self.tab_news = NewsTab(self.state, self)
                self.tabs.removeTab(index)
                # ⚠️ قبلاً این خط نبود؛ به همین خاطر Published می‌لغزید جای این تب
                self.tabs.insertTab(index, self.tab_news, 'اخبار و اطلاعیه ها')

            elif key == 'published':
                from .tabs.published_tab import PublishedTab
                self.tab_published = PublishedTab(self)
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self.tab_published, 'منتشر شده‌ها')

        finally:
            try:
                self.tabs.setCurrentIndex(index)
            except Exception:
                pass

    # ---------- اعتبار در هدر ----------
    def _connect_credit_signals(self):
        try:
            if hasattr(self, "tab_article") and hasattr(self.tab_article, "sigCreditsChanged"):
                self.tab_article.sigCreditsChanged.connect(self._on_credits_changed)
        except Exception:
            pass
        try:
            if hasattr(self, "tab_settings") and hasattr(self.tab_settings, "sigCreditsChanged"):
                self.tab_settings.sigCreditsChanged.connect(self._on_credits_changed)
        except Exception:
            pass

    def _on_credits_changed(self, val: int):
        # بلافاصله نشان سبز را آپدیت کن
        try:
            self.lbl_user_credits.setText(f"{int(val)} اعتبار")
        except Exception:
            self.lbl_user_credits.setText(f"{credits_get(self.state)} اعتبار")

    def _on_settings_saved(self):
        save(self.state)
        # اگر قبلاً به مدل اشاره‌ای بود، بی‌اثر بماند
        try:
            if hasattr(self, "tab_article") and hasattr(self.tab_article, "inp_model"):
                self.tab_article.inp_model.setCurrentText(self.state.get('gemini_model','gemini-2.5-flash'))
        except Exception:
            pass
        self._refresh_header_async()

    def _refresh_header_async(self):
        """آپدیت هدر بدون قفل کردن UI (شبکه در تردِ پس‌زمینه)."""
        # نشانِ اعتبار را سریع از state به‌روزرسانی کن
        try:
            from .credits import get as credits_get
            self.lbl_user_credits.setText(f"{credits_get(self.state)} اعتبار")
        except Exception:
            pass

        def worker():
            """
            نخِ پس‌زمینه:
              1) auth_check → فقط ورود/HWID
              2) اگر رد شد: پیام را در state می‌گذارد و جلو نمی‌رود
              3) اگر قبول شد: profile/get را می‌خواند
            خروجی: ('OK', (dn, em)) یا ('BLOCK', (dn, em, msg)) یا ('ERR', (dn, em, err))
            """
            try:
                api = CentralAPI(
                    self.state.get('central_url', ''),
                    self.state.get('central_email', ''),
                    self.state.get('central_password', '')
                )

                email_arg = self.state.get('central_email', '')
                pass_arg = self.state.get('central_password', '')

                # 1) ورود / چک HWID
                auth = api.auth_check(email_arg, pass_arg) or {}

                # تشخیص «رد شدن» از طرف سرور
                rejected = False
                if isinstance(auth, dict):
                    if auth.get('ok') is False:
                        rejected = True
                    elif str(auth.get('error') or '').strip():
                        rejected = True
                    elif isinstance(auth.get('code'), str) and auth.get('code'):
                        rejected = True

                if rejected:
                    msg = auth.get('message') or 'ورود با این دستگاه مجاز نیست. لطفاً با همان حساب قبلی وارد شوید.'
                    existing = auth.get('existing_user') or ''
                    if existing:
                        # ایمیل پیشنهاد شود
                        self.state['central_email'] = existing
                        self.state['central_password'] = ''
                    self.state['last_login_error'] = msg
                    save(self.state)
                    dn = self.state.get('display_name', 'کاربر')
                    em = self.state.get('central_email', 'user@example.com')
                    # 🚫 به profile نمی‌رویم
                    return ('BLOCK', (dn, em, msg))

                # 2) فقط وقتی قبول شد: خواندن پروفایل
                prof = api.profile_get() or {}
                user = prof.get('user') if isinstance(prof, dict) else None

                dn = self.state.get('display_name', 'کاربر')
                em = self.state.get('central_email', 'user@example.com')

                if isinstance(user, dict):
                    dn = user.get('display_name') or user.get('name') or dn
                    em = user.get('email') or em
                    # چند فیلد متداول را در state ذخیره کن (اختیاری)
                    for k in ('plan', 'plan_name', 'credits', 'article_credits', 'credits_articles',
                              'expire_at', 'expiry_date', 'days_left', 'expiry_days_left',
                              'referral_link', 'referral_credits', 'referred_count',
                              'referral_count', 'hwid'):
                        if k in user and user.get(k) not in (None, ''):
                            self.state[k] = user.get(k)

                # ورود موفق → پیام خطا را پاک کن
                self.state['last_login_error'] = ''
                save(self.state)
                return ('OK', (dn, em))

            except Exception as e:
                dn = self.state.get('display_name', 'کاربر')
                em = self.state.get('central_email', 'user@example.com')
                return ('ERR', (dn, em, str(e)))

        def apply(res):
            """این تابع در نخِ اصلی (UI) اجرا می‌شود."""
            try:
                kind, data = res
            except Exception:
                return

            try:
                if kind == 'OK':
                    dn, em = data
                    self.lbl_user_name.setText(dn)
                    self.lbl_user_email.setText(em)

                elif kind == 'BLOCK':
                    dn, em, msg = data
                    # برچسب‌ها را با state فعلی آپدیت نگه می‌داریم
                    self.lbl_user_name.setText(dn)
                    self.lbl_user_email.setText(em)
                    # پیام فقط در نخ اصلی:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, 'ورود - دستگاه', msg)

                elif kind == 'ERR':
                    dn, em, err = data
                    self.lbl_user_name.setText(dn)
                    self.lbl_user_email.setText(em)
                    # اختیاری: لاگ خطا در کنسول
                    print(f"[UI] network error: {err}")

            except Exception:
                pass

        # اجرای واقعی: کار شبکه در نخ Worker و سپس اعمال در UI
        def runner():
            res = worker()  # ← Worker thread (هیچ UI/دیالوگی اینجا نیست)
            QTimer.singleShot(0, lambda: apply(res))  # ← back to UI (نمایش پیام)

        t = threading.Thread(target=runner, daemon=True)
        t.start()

    def _toggle_theme(self):
        self._theme = 'light' if self._theme == 'dark' else 'dark'
        _apply_theme(QApplication.instance(), self._theme)
        try:
            self._theme_btn.setText('حالت روشن' if self._theme == 'dark' else 'حالت تیره')
        except Exception:
            pass
        # 🆕 هماهنگ‌سازی استایل تب منتشر شده‌ها با تم جدید

        try:
            if hasattr(self, "tab_published") and self.tab_published is not None:
                self.tab_published.refresh_theme()
        except Exception:
            pass
    def _center_on_screen(self):
        try:
            scr = QApplication.primaryScreen()
            if not scr:
                return
            cp = scr.availableGeometry().center()
            fg = self.frameGeometry()
            fg.moveCenter(cp)
            self.move(fg.topLeft())
        except Exception:
            pass

    # ------------- اتصال امن آماده‌شدن مقاله (فقط یک‌بار) -------------
    def _on_article_ready_from_article_tab(self, payload: dict):
        """
        وقتی ArticleTab گفت مقاله آماده شد → همان عنوان را از TitlesTab پاک کن (DB+UI).
        """
        try:
            rec_id = str((payload or {}).get("record_id") or "")
            seed   = ((payload or {}).get("seed") or "").strip()
            if hasattr(self, "tab_titles") and hasattr(self.tab_titles, "on_article_generated"):
                self.tab_titles.on_article_generated(rec_id, seed)
        except Exception:
            pass

    def _wire_article_ready_once(self):
        """
        اتصال سیگنال فقط یک‌بار؛ بدون disconnect().
        """
        if getattr(self, "_article_ready_wired", False):
            return
        try:
            if hasattr(self, "tab_article") and hasattr(self.tab_article, "sigArticleReady"):
                self.tab_article.sigArticleReady.connect(self._on_article_ready_from_article_tab)
                self._article_ready_wired = True
        except Exception:
            pass

    # ------------- Article Queue (ارسال «یک‌جا» از TitlesTab) -------------
    def _queue_articles(self, record_id: str, rows: list, delay_sec: int):
        """
        rows: list of dicts like {"seed": "..."}
        همه‌ی موارد را «یک‌جا» به تب تولید مقاله می‌فرستد و اتصال حذف را برقرار می‌کند.
        """
        # مطمئن شو تب مقاله لود شده
        try:
            if not hasattr(self, 'tab_article') or self.tab_article is None:
                self._ensure_tab_loaded(2)  # index تب مقاله
        except Exception:
            pass

        # ساخت payloads تمیز
        payloads = []
        for r in (rows or []):
            s = ""
            if isinstance(r, dict):
                s = (r.get("seed") or "").strip()
            elif isinstance(r, str):
                s = r.strip()
            if s:
                payloads.append({"seed": s})

        # ارسال یک‌جا به تب مقاله (اول همه در باکس چندخطی دیده می‌شوند)
        try:
            self.tab_article.add_to_queue(record_id, payloads, delay_sec=-1)
        except Exception:
            pass

        # اتصال سیگنال فقط یک‌بار به اسلات نام‌دار (بدون disconnect)
        self._wire_article_ready_once()

        # سوییچ به تب تولید مقاله تا کاربر «یک‌بار» Start را بزند
        try:
            self.tabs.setCurrentIndex(self.tabs.indexOf(self.tab_article))
        except Exception:
            pass

    # ------------- مسیر قدیمیِ صف (برای سازگاری) -------------
    def _drain_queue(self):
        if not self._article_queue:
            return
        rec_id, data = self._article_queue.pop(0)
        self._current_rec_id = rec_id
        self._current_seed   = (data.get("seed") or "").strip()

        # سوییچ به تب مقاله (ظاهر ثابت) + اطمینان از لود بودن تب مقاله
        try:
            idx = self.tabs.indexOf(self.tab_article)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
        except Exception:
            try:
                article_index = 2  # طبق آرایش تب‌ها
                self._ensure_tab_loaded(article_index)
                self.tabs.setCurrentIndex(article_index)
            except Exception:
                pass

        # گیرندهٔ یک‌بارمصرف؛ اتصال‌های داخلی ArticleTab را دست نمی‌زنیم
        self._setup_article_ready_catcher()

        # پرکردن فیلد و شروع تولید
        self._start_article_generation(seed=self._current_seed)

    def _setup_article_ready_catcher(self):
        try:
            if self._article_ready_hook_connected:
                self.tab_article.sigArticleReady.disconnect(self._catch_article_ready)
        except Exception:
            pass
        try:
            self.tab_article.sigArticleReady.connect(self._catch_article_ready)
            self._article_ready_hook_connected = True
        except Exception:
            pass

    def _teardown_article_ready_catcher(self):
        try:
            if self._article_ready_hook_connected:
                self.tab_article.sigArticleReady.disconnect(self._catch_article_ready)
        except Exception:
            pass
        self._article_ready_hook_connected = False

    def _catch_article_ready(self, *_):
        """پس از آماده شدن مقاله: آیتم انتخابی در تب عناوین حذف و آیتم بعدی پردازش شود."""
        self._teardown_article_ready_catcher()
        try:
            if hasattr(self.tab_titles, "on_article_generated"):
                self.tab_titles.on_article_generated(self._current_rec_id, self._current_seed)
        finally:
            if self._article_queue:
                QTimer.singleShot(max(1, self._queue_delay) * 1000, self._drain_queue)

    # ------------- سازگاری با فراخوانی‌های قدیمی -------------
    def _start_article_generation(self, seed=None):
        """
        Compatibility shim:
        - تب مقاله را لود و فعال می‌کند
        - اگر seed داده شده باشد، آن را از مسیر رسمی add_to_queue به تب مقاله پاس می‌دهد
        - تولید خودکار را شروع نمی‌کند؛ کاربر خودش دکمه «شروع تولید» را می‌زند.
        """
        try:
            # مطمئن شو تب مقاله لود شده
            if not hasattr(self, 'tab_article') or self.tab_article is None:
                try:
                    self._ensure_tab_loaded(2)
                except Exception:
                    pass

            # سوییچ به تب مقاله
            try:
                idx = self.tabs.indexOf(self.tab_article)
                if idx != -1:
                    self.tabs.setCurrentIndex(idx)
            except Exception:
                pass

            # عنوان را واقعاً در باکس چندخطی تب مقاله اضافه کن
            try:
                record_id = getattr(self, "_current_rec_id", "") or ""
                if seed:
                    self.tab_article.add_to_queue(record_id, [{"seed": str(seed)}], -1)
            except Exception:
                pass

            # اتصال سیگنال آماده‌شدن (قدیمی)
            try:
                self._setup_article_ready_catcher()
            except Exception:
                pass

        except Exception:
            pass
