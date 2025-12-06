# -*- coding: utf-8 -*-
"""
credits.py — مدیریت اعتبار فقط بر اساس سرور مرکزی (بدون pending محلی)

ویژگی‌ها:
- کاهش اعتبار «فقط» اگر سرور موفق برگرداند.
- کش محلی صرفاً برای نمایش و فقط پس از پاسخ موفق سرور به‌روزرسانی می‌شود.
- سازگار با importهای قبلی: get / set / consume / display / sync_from_server
"""

from __future__ import annotations
from typing import Any, Dict, Optional

# ذخیره‌سازی سبک برای کش نمایش
try:
    from .storage import save  # type: ignore
except Exception:
    def save(state: Dict[str, Any]) -> None:  # type: ignore
        pass

# API مرکزی
try:
    from .api import CentralAPI  # type: ignore
except Exception:
    CentralAPI = None  # type: ignore

# کلیدهای ممکن برای مقدار اعتبار در پاسخ سرور
_KEYS = ["articles_remaining", "article_credits", "credits_articles", "credits"]

# کلیدهای تنظیمات اتصال
_SERVER_URL_KEY = "central_url"
_EMAIL_KEY = "central_email"
_PASS_KEY = "central_password"

# کلید کش نمایش (فقط UI)
_DISPLAY_KEY = "credits_display"


# ---------- ابزارهای داخلی ----------

def _extract_from_profile(resp: Any) -> Optional[int]:
    """از آبجکت پاسخ، مقدار اعتبار را (در کلیدهای شناخته‌شده) استخراج می‌کند."""
    if not isinstance(resp, dict):
        return None
    # بازکردن لایه‌های معمول
    for wrap_key in ("user", "profile", "data"):
        if wrap_key in resp and isinstance(resp[wrap_key], dict):
            v = _extract_from_profile(resp[wrap_key])
            if isinstance(v, int):
                return v
    for k in _KEYS:
        v = resp.get(k)
        try:
            iv = int(v)
            if iv >= 0:
                return iv
        except Exception:
            pass
    return None


def _make_api(state: Dict[str, Any]) -> "CentralAPI":
    if CentralAPI is None:
        raise RuntimeError("CentralAPI در دسترس نیست")
    base = (state or {}).get(_SERVER_URL_KEY) or ""
    email = (state or {}).get(_EMAIL_KEY) or ""
    password = (state or {}).get(_PASS_KEY) or ""
    if not (base and email and password):
        raise RuntimeError("تنظیمات اتصال به سرور مرکزی ناقص است (آدرس/ایمیل/پسورد).")
    api = CentralAPI(base_url=base, email=email, password=password)
    # Auto-authenticate
    try:
        api.auth_check(email, password)
    except Exception:
        pass
    return api


def _update_display_cache(state: Dict[str, Any], value: int) -> int:
    try:
        value = max(0, int(value))
    except Exception:
        value = 0
    if isinstance(state, dict):
        state[_DISPLAY_KEY] = value
        save(state)
    return value


# ---------- رابط عمومی ----------

def get(state: Dict[str, Any]) -> int:
    """مقدار کش نمایش (برای UI). برای عدد واقعی، از sync_from_server استفاده کنید."""
    try:
        v = int((state or {}).get(_DISPLAY_KEY) or 0)
        return max(0, v)
    except Exception:
        return 0


def set(state: Dict[str, Any], value: int) -> int:
    """
    فقط کش نمایش را تنظیم می‌کند (برای سازگاری با کدهای قدیمی).
    هیچ تغییری در اعتبار واقعی نمی‌دهد.
    """
    return _update_display_cache(state, value)


def sync_from_server(state: Dict[str, Any]) -> int:
    """اعتبار واقعی را فقط از سرور می‌خواند و کش را به‌روزرسانی می‌کند."""
    api = _make_api(state)

    # 1) endpoint اختصاصی اعتبار (اگر باشد)
    try:
        raw = api.credits_get()
        remained = _extract_from_profile(raw)
        if remained is not None:
            return _update_display_cache(state, remained)
    except Exception:
        pass

    # 2) جایگزین: از پروفایل
    try:
        prof = api.profile_get()
        remained = _extract_from_profile(prof)
        if remained is not None:
            return _update_display_cache(state, remained)
    except Exception:
        pass

    # اگر چیزی برنگشت، کش را دست نمی‌زنیم
    return get(state)


def credits_consume(state: Dict[str, Any], amount: int = 1) -> int:
    """
    تنها مسیر مجاز برای «کاهش اعتبار».
    - تماس با سرور مرکزی.
    - اگر موفق بود، عدد جدید را از پاسخ خوانده و کش را به‌روزرسانی می‌کند.
    - اگر خطا بود، هیچ تغییری در کش نمی‌دهد و استثناء می‌اندازد
      تا UI پیام خطا نمایش دهد و دوگانگی ایجاد نشود.
    """
    if amount is None:
        amount = 1
    try:
        amount = max(1, int(amount))
    except Exception:
        amount = 1

    api = _make_api(state)
    resp: Dict[str, Any] = api.credits_consume(amount=amount)  # روی خطا باید exception بدهد

    remained = _extract_from_profile(resp)
    if remained is None:
        raise RuntimeError("پاسخ سرور معتبر نیست: مقدار اعتبار پیدا نشد.")

    return _update_display_cache(state, remained)


# سازگاری با نام‌های قبلی
def display(state: Dict[str, Any]) -> int:
    return get(state)

def consume(state: Dict[str, Any], amount: int = 1) -> int:
    return credits_consume(state, amount)
