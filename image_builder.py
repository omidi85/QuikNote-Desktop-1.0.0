# -*- coding: utf-8 -*-
"""
ساخت تصویر شاخص از Pixabay:
- متن روی عکس = عنوان پست (فارسی) با arabic_reshaper + bidi
- واترمارک پایین راست با بک‌گراند مشکی ~70% شفاف
- لوگو پایین چپ (اختیاری)
- نام فایل خروجی = عبارت جستجوی انگلیسی (sanitize)
- فونت: اگر کاربر مسیر ندهد یا فونت انتخابی نامعتبر باشد، از quiknote/assets/fonts استفاده می‌شود.
"""
import os, re, io, sys, requests
from typing import Optional, Sequence, Callable
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

LogFn = Optional[Callable[[str], None]]

def _log(log: LogFn, msg: str):
    try:
        if log:
            log(msg)
    except Exception:
        pass

def _sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "_", name.strip())
    name = re.sub(r"\s+", "_", name)
    return name or "image"

def _try_paths(candidates: Sequence[str]) -> Optional[str]:
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None

def _assets_root() -> str:
    # تلاش برای یافتن پوشه assets در سناریوهای مختلف (PyInstaller/پکیج/اجرا از سورس)
    cands = []
    if getattr(sys, '_MEIPASS', None):  # PyInstaller bundle
        cands += [
            os.path.join(sys._MEIPASS, "quiknote", "assets"),  # type: ignore
            os.path.join(sys._MEIPASS, "assets"),              # type: ignore
        ]
    cands += [
        os.path.join(os.getcwd(), "quiknote", "assets"),
        os.path.join(os.getcwd(), "assets"),
        os.path.join(os.path.dirname(__file__), "assets"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"),
    ]
    for p in cands:
        if os.path.isdir(p):
            return p
    return os.getcwd()

def _is_supported_font_ext(path: str) -> bool:
    ext = os.path.splitext(path.lower())[1]
    return ext in (".ttf", ".otf", ".ttc", ".otc")

def _is_webfont_ext(path: str) -> bool:
    ext = os.path.splitext(path.lower())[1]
    return ext in (".woff", ".woff2")

def _load_font(font_path: Optional[str], size=40, log: LogFn = None) -> ImageFont.FreeTypeFont:
    """
    ترتیب تلاش:
    1) اگر کاربر مسیر داد و فرمت پشتیبانی‌شده بود → همان.
    2) اگر کاربر WOFF/WOFF2 داد → هشدار و می‌رویم سراغ assets.
    3) assets: quiknote/assets/fonts/{Vazir-Bold.ttf,Vazirmatn-Bold.ttf}
    4) کنار برنامه: Vazir-Bold.ttf / Vazirmatn-Bold.ttf
    5) در نهایت fallback: ImageFont.load_default()
    """
    # 1) فونت کاربر
    if font_path:
        if _is_webfont_ext(font_path):
            _log(log, "⚠️ فرمت انتخاب‌شده وب‌فونت است (WOFF/WOFF2) و توسط Pillow پشتیبانی نمی‌شود؛ از فونت پیش‌فرض برنامه استفاده می‌شود.")
        elif not _is_supported_font_ext(font_path):
            _log(log, "⚠️ فرمت فونت انتخاب‌شده پشتیبانی نمی‌شود؛ لطفاً TTF/OTF بدهید. از فونت پیش‌فرض برنامه استفاده می‌شود.")
        else:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                _log(log, f"⚠️ بارگذاری فونت انتخابی ناموفق بود: {e} — از فونت پیش‌فرض برنامه استفاده می‌شود.")

    # 2) assets
    assets = _assets_root()
    cand = [
        os.path.join(assets, "fonts", "Vazir-Bold.ttf"),
        os.path.join(assets, "fonts", "Vazirmatn-Bold.ttf"),
    ]
    fp = _try_paths(cand)
    if fp:
        try:
            _log(log, f"ℹ️ استفاده از فونت برنامه: {os.path.basename(fp)}")
            return ImageFont.truetype(fp, size)
        except Exception as e:
            _log(log, f"⚠️ بارگذاری فونت assets ناموفق بود: {e}")

    # 3) کنار برنامه
    for name in ("Vazir-Bold.ttf", "Vazirmatn-Bold.ttf"):
        if os.path.isfile(name):
            try:
                _log(log, f"ℹ️ استفاده از فونت کنار برنامه: {name}")
                return ImageFont.truetype(name, size)
            except Exception:
                pass

    # 4) آخرین چاره
    _log(log, "⚠️ هیچ فونت معتبری یافت نشد؛ از فونت پیش‌فرض Pillow استفاده می‌شود (ممکن است فارسی را ناقص نمایش دهد).")
    return ImageFont.load_default()

def compose_feature_image(
    pixabay_api_key: str,
    search_query_en: str,
    title_fa: str,
    logo_path: Optional[str],
    site_watermark: str,
    output_dir: str,
    font_text_size: int = 40,
    font_wm_size: int = 22,
    font_path: Optional[str] = None,
    log: LogFn = None,  # ← اختیاری: برای ارسال پیام به UI
) -> str:
    if not pixabay_api_key: raise RuntimeError("Pixabay API Key تنظیم نشده است.")
    if not search_query_en: raise RuntimeError("عبارت جستجوی تصویر خالی است.")
    if not title_fa: raise RuntimeError("عنوان (برای متن روی تصویر) خالی است.")

    # 1) جستجو در Pixabay
    url = f"https://pixabay.com/api/?key={pixabay_api_key}&q={requests.utils.quote(search_query_en)}&image_type=photo&per_page=3"
    r = requests.get(url, timeout=20); r.raise_for_status()
    data = r.json(); hits = data.get('hits') or []
    if not hits: raise RuntimeError("عکسی از Pixabay پیدا نشد.")
    image_url = hits[0].get('largeImageURL') or hits[0].get('webformatURL')
    if not image_url: raise RuntimeError("URL تصویر نامعتبر است.")
    ir = requests.get(image_url, timeout=30); ir.raise_for_status()

    # 2) کار روی تصویر
    im = Image.open(io.BytesIO(ir.content)).convert("RGBA")
    draw = ImageDraw.Draw(im); W, H = im.size

    # عنوان فارسی (با reshaper + bidi)
    reshaped = arabic_reshaper.reshape(title_fa); bidi = get_display(reshaped)
    font_title = _load_font(font_path, size=font_text_size, log=log)
    bbox = draw.textbbox((0,0), bidi, font=font_title)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx = (W - tw) // 2; ty = H - th - 60

    # بک‌گراند نیمه‌شفاف زیر عنوان
    pad = 20
    rect_y1 = max(0, ty - 10); rect_y2 = min(H, ty + th + 10)
    rect_x1 = max(0, tx - pad); rect_x2 = min(W, tx + tw + pad)
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle([rect_x1, rect_y1, rect_x2, rect_y2], fill=(0,0,0,128))
    im = Image.alpha_composite(im, overlay); draw = ImageDraw.Draw(im)

    # خود متن
    draw.text((tx, ty), bidi, font=font_title, fill=(255,255,255,255))

    # واترمارک پایین راست با بک‌گراند ~70%
    wm_text = (site_watermark or "").strip()
    if wm_text:
        reshaped_wm = arabic_reshaper.reshape(wm_text); bidi_wm = get_display(reshaped_wm)
        font_wm = _load_font(font_path, size=font_wm_size, log=log)
        wbb = draw.textbbox((0,0), bidi_wm, font=font_wm)
        ww, wh = wbb[2]-wbb[0], wbb[3]-wbb[1]
        wx = W - ww - 24; wy = H - wh - 24
        overlay2 = Image.new("RGBA", (W, H), (0,0,0,0)); d2 = ImageDraw.Draw(overlay2)
        pad2 = 10
        d2.rectangle([wx - pad2, wy - pad2, wx + ww + pad2, wy + wh + pad2], fill=(0,0,0,178))
        im = Image.alpha_composite(im, overlay2); draw = ImageDraw.Draw(im)
        draw.text((wx, wy), bidi_wm, font=font_wm, fill=(255,255,255,220))

    # لوگو پایین چپ (اختیاری)
    if logo_path and os.path.isfile(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            lw, lh = logo.size; ratio = 100.0 / float(lw) if lw else 1.0
            logo = logo.resize((int(lw*ratio), int(lh*ratio)))
            im.paste(logo, (20, H - logo.height - 20), logo)
        except Exception as e:
            _log(log, f"⚠️ خطا در درج لوگو: {e}")

    os.makedirs(output_dir, exist_ok=True)
    base = _sanitize_filename(search_query_en)
    out_path = os.path.join(output_dir, f"{base}.jpg")
    im.convert("RGB").save(out_path, format="JPEG", quality=92, optimize=True, progressive=True)
    _log(log, f"✅ تصویر ساخته شد: {out_path}")
    return out_path
