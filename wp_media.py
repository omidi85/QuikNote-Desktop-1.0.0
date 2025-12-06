# -*- coding: utf-8 -*-
"""
آپلود رسانه به وردپرس و ست‌کردن Featured Image (با پچ BOM برای JSON)
"""
import os, requests, mimetypes, base64, json
from typing import Optional

def _auth_header(user: str, app: str) -> dict:
    token = base64.b64encode(f"{user}:{app}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}

def _safe_json(resp: requests.Response):
    """
    JSON امن: BOM/Whitespace ابتدایی را حذف می‌کند و پیام خطای خوانا می‌دهد.
    """
    text = resp.text.lstrip("\ufeff").strip()
    try:
        return json.loads(text)
    except Exception as e:
        short = text[:300]
        raise RuntimeError(f"پاسخ JSON نامعتبر ({resp.status_code}): {e}; body: {short}")

def upload_media(site: str, user: str, app: str, file_path: str, alt_text: Optional[str] = None) -> int:
    if not os.path.isfile(file_path):
        raise RuntimeError("فایل تصویر وجود ندارد.")
    url = site.rstrip("/") + "/wp-json/wp/v2/media"
    headers = _auth_header(user, app)
    headers["Accept"] = "application/json"

    filename = os.path.basename(file_path)
    mime, _ = mimetypes.guess_type(filename)
    if not mime: mime = "image/jpeg"

    with open(file_path, "rb") as f:
        files = {'file': (filename, f, mime)}
        r = requests.post(url, headers=headers, files=files, timeout=40)
    if r.status_code not in (200,201):
        raise RuntimeError(f"آپلود ناموفق: {r.status_code} - {r.text.lstrip(chr(0xfeff))[:200]}")
    data = _safe_json(r)
    media_id = int(data.get('id') or 0)
    if not media_id:
        raise RuntimeError("شناسه رسانه برنگشت.")

    if alt_text:
        u2 = site.rstrip("/") + f"/wp-json/wp/v2/media/{media_id}"
        jbody = {"alt_text": alt_text}
        hdr = {**headers, "Content-Type":"application/json", "Accept":"application/json"}
        r2 = requests.post(u2, headers=hdr, json=jbody, timeout=20)
        if r2.status_code not in (200,201):
            r2 = requests.put(u2, headers=hdr, json=jbody, timeout=20)
        try: _ = _safe_json(r2)
        except Exception: pass

    return media_id

def set_featured_image(site: str, user: str, app: str, post_id: int, media_id: int) -> None:
    url = site.rstrip("/") + f"/wp-json/wp/v2/posts/{post_id}"
    headers = {**_auth_header(user, app), "Content-Type":"application/json", "Accept":"application/json"}
    r = requests.post(url, headers=headers, json={"featured_media": int(media_id)}, timeout=20)
    if r.status_code not in (200,201):
        r = requests.put(url, headers=headers, json={"featured_media": int(media_id)}, timeout=20)
    if r.status_code not in (200,201):
        raise RuntimeError(f"ثبت Featured Image ناموفق: {r.status_code} - {r.text.lstrip(chr(0xfeff))[:200]}")
    try: _ = _safe_json(r)
    except Exception: pass
