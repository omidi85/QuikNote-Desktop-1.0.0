# quiknote/utils/threads.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication

# اگر هنگام خروجِ برنامه Worker هنوز در حال emit باشد،
# RuntimeError: "Signal source has been deleted" رخ می‌دهد.
# با این فلگ و emit ایمن مانع خطا می‌شویم.
_APP_QUITTING = False

def _install_quit_hook_once():
    """اتصال aboutToQuit برای خاموش‌کردن امنِ emit ها."""
    global _APP_QUITTING
    app = QApplication.instance()
    if app is not None:
        # فقط یک‌بار وصل شود
        try:
            # اگر چند بار صدا بخورد هم مشکلی نیست؛ اسلات idempotent است.
            app.aboutToQuit.connect(lambda: _set_quitting())
        except Exception:
            pass

def _set_quitting():
    global _APP_QUITTING
    _APP_QUITTING = True

def _safe_emit_done(signals: "WorkerSignals", result: Any, error: BaseException | None):
    """emit امن: اگر گیرنده پاک شده باشد یا برنامه در حال خروج باشد، ساکت رد می‌شود."""
    if _APP_QUITTING or signals is None:
        return
    try:
        signals.done.emit(result, error)
    except RuntimeError:
        # گیرنده یا خود signals نابود شده؛ نیازی به گزارش نیست
        pass
    except Exception:
        # هر خطای غیرمنتظره‌ی دیگری هم نباید باعث کرش شود
        pass


class WorkerSignals(QObject):
    """
    سیگنال‌های Worker.
    - done(result, error): در پایان کار صدا می‌شود. اگر error None نباشد یعنی خطا رخ داده.
    """
    done = Signal(object, object)  # (result, error)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class Worker(QRunnable):
    """
    اجرای تابع سبک در استخر نخ‌ها.
    مثال:
        w = Worker(fn, *args, **kwargs)
        w.signals.done.connect(on_done)
        thread_pool.start(w)
    """
    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

        # نگه داشتن سیگنال‌ها با والدِ پایدار (QApplication) تا پایان عمر برنامه
        parent_for_signals = QApplication.instance()
        self.signals = WorkerSignals(parent=parent_for_signals)

        # در PySide6، QRunnable شیء QObject نیست؛ parent شدن سیگنال‌ها به خودِ Runner ممکن نیست.
        # اتو-دیلیت را روشن می‌گذاریم تا بعد از اتمام کار توسط QThreadPool آزاد شود.
        try:
            self.setAutoDelete(True)
        except Exception:
            pass

        # نصب هوک خروج (اگر تا حالا نصب نشده)
        _install_quit_hook_once()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs) if callable(self.fn) else None
            _safe_emit_done(self.signals, res, None)
        except Exception as e:
            _safe_emit_done(self.signals, None, e)


# استخر نخِ سراسری (همان الگوی قبلی)
thread_pool: QThreadPool = QThreadPool.globalInstance()


def run_in_thread(fn: Callable[..., Any], *args, **kwargs) -> Worker:
    """
    میان‌بُر: تابع را در پس‌زمینه اجرا می‌کند و Worker را برمی‌گرداند.
    استفاده:
        w = run_in_thread(do_work, x, y)
        w.signals.done.connect(lambda res, err: ...)
    """
    w = Worker(fn, *args, **kwargs)
    thread_pool.start(w)
    return w
