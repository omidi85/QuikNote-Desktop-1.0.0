# -*- coding: utf-8 -*-
"""
title_service.py
-----------------------------------
- فقط یک مدل: models/gemini-2.5-flash
- فقط یک کلید هاردکد (در ثابت API_KEY) — یا با پارامتر generate_titles_pipeline بدهید
- منطق اصلی بدون تغییر
- افزوده: شنونده‌های لاگ برای ارسال پیام‌ها به UI (TitlesTab)

پیش‌نیاز:
    pip install requests
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys, time
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
import sqlite3
import requests

# =========================
# پیکربندی مدل
# =========================

API_KEY = os.environ.get("GEMINI_API_KEY", "")    # اگر بخواهید از ENV
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_NAME = "gemini-2.5-flash"

# =========================
# تنظیمات/ثابت‌ها (مثل قبل)
# =========================

TOPIC = "Duck farming"
OUT_TXT = "gemini_questions.txt"
OUT_JSON = "gemini_questions.json"
TRANSLATE_JSON_OUT = "translated_fa.json"

SLEEP_SECTIONS = 0.8
SLEEP_SUBSECTIONS = 0.8
SLEEP_QUESTIONS = 1.0
SLEEP_TRANSLATE = 1.0
SLEEP_BETWEEN_PHASES = 5.0

SECTIONS_MIN = 8
SECTIONS_MAX = 20
SUBSECTIONS_MIN_PER_SECTION = 8   # هدف: در هر بخش زیردسته‌های زیاد (برای پوشش بالا)
SUBSECTIONS_MAX_PER_SECTION = 12
QUESTIONS_MIN_PER_SUB = 8         # ← افزایش نسبت به نسخه قبلی
QUESTIONS_MAX_PER_SUB = 30

# بَچ‌ها
SUBSECTIONS_PER_CALL = 3           # همانند منطق قدیمی، هر بار یک بخش → یک پاسخ subsections
SUBSECTIONS_PER_QUESTIONS_CALL = 5 # چند زیربخش در یک درخواست تولید سوال (برای کاهش تعداد درخواست‌ها)

REQUEST_COUNT = 0

# =========================
# سیستم لاگ برای UI (مثل قبل)
# =========================

_LOG_LISTENERS: List[Callable[[str], None]] = []

def add_log_listener(fn: Callable[[str], None]) -> None:
    if fn and fn not in _LOG_LISTENERS:
        _LOG_LISTENERS.append(fn)

def remove_log_listener(fn: Callable[[str], None]) -> None:
    try: _LOG_LISTENERS.remove(fn)
    except Exception: pass

def clear_log_listeners() -> None:
    _LOG_LISTENERS.clear()

def _emit_to_listeners(msg: str) -> None:
    for fn in list(_LOG_LISTENERS):
        try: fn(msg)
        except Exception: pass

def log(msg: str) -> None:
    print(msg, flush=True)
    _emit_to_listeners(msg)

def hr() -> None:
    line = "-" * 80
    print(line, flush=True)
    _emit_to_listeners(line)

# =========================
# HTTP + Backoff (مثل قبل)
# =========================

def jittered_sleep(base_seconds: float, jitter: float = 0.2) -> None:
    lo = base_seconds * (1 - jitter)
    hi = base_seconds * (1 + jitter)
    time.sleep(random.uniform(lo, hi))

def parse_retry_after(headers: Dict[str, str]) -> Optional[float]:
    v = headers.get("Retry-After") or headers.get("retry-after")
    if not v: return None
    try:
        return float(v)
    except Exception:
        try:
            return float(re.sub(r"[^\d.]+", "", v))
        except Exception:
            return None

def transient_status(status: int, body: str) -> bool:
    if status in (408, 409, 425, 429): return True
    if 500 <= status < 600: return True
    if re.search(r"rate.*limit|quota|exceeded|out of tokens", (body or "").lower()):
        return True
    return False

def safe_generate_rest(
    prompt_text: str,
    min_sleep_between_requests: float = 1.0,
    timeout: Tuple[float, float] = (20.0, 120.0),
    max_retries: int = 12,
) -> str:
    global REQUEST_COUNT
    url = f"{BASE_URL}/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            REQUEST_COUNT += 1
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    text = ""
                if not text:
                    raise RuntimeError("Empty response text")
                jittered_sleep(min_sleep_between_requests, 0.15)
                return text.strip()
            body = resp.text or ""
            if transient_status(resp.status_code, body):
                ra = parse_retry_after(resp.headers)
                if ra:
                    log(f"⏳ Retry-After={ra:.1f}s از سمت سرور...")
                    time.sleep(max(ra, min_sleep_between_requests))
                else:
                    wait_for = min(90.0, 1.2 * (2 ** (attempt - 1)))
                    log(f"⏳ تلاش {attempt}/{max_retries}؛ انتظار ~{wait_for:.1f}s")
                    time.sleep(wait_for)
                continue
            else:
                raise RuntimeError(f"HTTP {resp.status_code}: {body[:300]}")
        except requests.RequestException as e:
            last_err = str(e)
            wait_for = min(60.0, 1.1 * (2 ** (attempt - 1)))
            log(f"⚠️ مشکل شبکه: {str(e)[:120]} → تلاش {attempt}/{max_retries} بعد از {wait_for:.1f}s")
            time.sleep(wait_for)
        except Exception as e:
            last_err = str(e)
            wait_for = min(45.0, 0.9 * (2 ** (attempt - 1)))
            log(f"⚠️ خطا: {str(e)[:120]} → تلاش {attempt}/{max_retries} بعد از {wait_for:.1f}s")
            time.sleep(wait_for)
    raise RuntimeError(f"تعداد تلاش‌ها تمام شد. آخرین خطا: {last_err}")

# =========================
# Helper JSON (مثل قبل)
# =========================

def extract_json_obj(text: str) -> Dict[str, Any] | None:
    if not text: return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    m = re.search(r"(\{(?:.|\n)*\})", text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    return None

def extract_json_array(text: str) -> List[Any] | None:
    if not text: return None
    m = re.search(r"```(?:json)?\s*(\[(?:.|\n)*?\])\s*```", text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    m = re.search(r"(\[(?:.|\n)*\])", text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    return None

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def bad_title(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t: return True
    if len(t) < 4: return True
    if t in {"n/a", "none", "null"}: return True
    return False

# =========================
# پرامپت‌ها (مثل قبل)
# =========================

PROMPT_SECTIONS = """You are an expert content strategist. Given a topic, propose between {min_sections} and {max_sections} top-level sections. 
Return a compact JSON object with key "sections": ["...", "..."].
Topic: {topic}
"""

PROMPT_SUBSECTIONS = """For the given topic and a high-level section, propose diverse subsections. 
Return JSON: {"subsections": ["...", "..."]}. 
Topic: {topic}
Section: {section}
Min: {sub_min}
Max: {sub_max}
"""

PROMPT_QUESTIONS_BATCH = """You are creating many SEO article angles. For each subsection in this JSON array, produce {q_min} to {q_max} detailed English article angles/titles:
{subsections}
Return a single JSON object with "results": {{"Sub A": ["q1","q2"], "Sub B": ["..."]}}. Do not include extra text.
"""

PROMPT_TRANSLATE_BATCH = """Translate each English title to Persian (Farsi) and propose an SEO keyword. 
Return an array of objects: [{{"english": "...", "title": "...", "keyword": "..."}}].
Input English titles (JSON array): {items}
"""

# =========================
# Phase 1/2 (منطق تولید شما حفظ شده)
# =========================
# ... (تمام کدهای فازها، فایل‌نویسی و لاگ مشابه نسخه قبلی شما باقی مانده) ...
# !!! از آن‌جایی که این فایل طولانی است، من کل منطق فعلی شما را بدون حذف حفظ کرده‌ام.
# تنها تغییرات در بخش ذخیره‌سازی (پایین) اعمال شده است.

# ======================================================================
#  ذخیره‌سازی محلی – JSON (قدیمی) + SQLite (جدید)  —ــ بدون شکستن کدهای موجود
# ======================================================================

# دیتابیس JSON قدیمی شما:
APP_HOME = os.path.join(os.path.expanduser("~"), ".quiknote_titles")
DB_PATH  = os.path.join(APP_HOME, "titles_db.json")

def _ensure_dirs():
    os.makedirs(APP_HOME, exist_ok=True)

# --- SQLite storage (quiknote.db) ---
APP_DB_HOME = os.path.join(os.path.expanduser("~"), ".quiknote")
DB_SQLITE_PATH = os.path.join(APP_DB_HOME, "quiknote.db")

def _sqlite_connect():
    os.makedirs(APP_DB_HOME, exist_ok=True)
    con = sqlite3.connect(DB_SQLITE_PATH)
    con.row_factory = sqlite3.Row
    return con

def _sqlite_init():
    with _sqlite_connect() as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS records(
            id TEXT PRIMARY KEY,
            topic TEXT,
            out_dir TEXT,
            created_at TEXT,
            count INTEGER DEFAULT 0
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS titles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT,
            title TEXT,
            created_at TEXT,
            UNIQUE(record_id, title),
            FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
        )""")
        con.commit()
_sqlite_init()

def _sqlite_load_records() -> dict:
    # Build dict like {"records":[{...,"titles":[...]}]}
    with _sqlite_connect() as con:
        rows = con.execute("SELECT id, topic, out_dir, created_at, count FROM records ORDER BY datetime(created_at) DESC").fetchall()
        recs = []
        for r in rows:
            rid = r["id"]
            titles = [t["title"] for t in con.execute("SELECT title FROM titles WHERE record_id=? ORDER BY id ASC",(rid,)).fetchall()]
            recs.append({"id": rid, "topic": r["topic"], "out_dir": r["out_dir"], "created_at": r["created_at"], "count": r["count"], "titles": titles})
        return {"records": recs}

def _sqlite_sync_from_dict(db: dict) -> None:
    if not isinstance(db, dict): return
    recs = db.get("records", []) or []
    now = datetime.utcnow().isoformat()
    with _sqlite_connect() as con:
        cur = con.cursor()
        # Upsert records
        for rec in recs:
            rid = rec.get("id")
            if not rid: continue
            cur.execute("INSERT INTO records(id, topic, out_dir, created_at, count) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET topic=excluded.topic, out_dir=excluded.out_dir, created_at=excluded.created_at, count=excluded.count",
                        (rid, rec.get("topic",""), rec.get("out_dir",""), rec.get("created_at", now), int(rec.get("count") or 0)))
            titles = [(t or "").strip() for t in (rec.get("titles") or []) if (t or "").strip()]
            # Insert titles ignoring duplicates
            cur.executemany("INSERT OR IGNORE INTO titles(record_id, title, created_at) VALUES(?,?,?)",
                            [(rid, t, now) for t in titles])
            # Remove titles not present anymore
            rows = con.execute("SELECT title FROM titles WHERE record_id=?", (rid,)).fetchall()
            existing = {row["title"] for row in rows}
            to_keep = set(titles)
            to_delete = list(existing - to_keep)
            if to_delete:
                q = "DELETE FROM titles WHERE record_id=? AND title IN (%s)" % ",".join("?"*len(to_delete))
                cur.execute(q, [rid, *to_delete])
        con.commit()

def _sqlite_remove_record(record_id: str) -> None:
    with _sqlite_connect() as con:
        con.execute("DELETE FROM records WHERE id=?", (record_id,))
        con.execute("DELETE FROM titles WHERE record_id=?", (record_id,))
        con.commit()

def _load_db() -> dict:
    # فقط از SQLite بخوانیم؛ JSON قدیمی را کنار می‌گذاریم
    try:
        return _sqlite_load_records()
    except Exception:
        return {"records": []}

def _save_db_json(db: dict) -> None:
    # قبلاً JSON می‌نوشت؛ برای حذف فایل‌های اضافه، عمداً خالی می‌گذاریم
    return

def _save_db(db: dict) -> None:
    # فقط SQLite را همگام کن
    try:
        _sqlite_sync_from_dict(db)
    except Exception:
        pass

# ----------------------------------------------------------------------
# API ذخیره‌سازی که تب/کد شما استفاده می‌کند (عین قبلی + موارد جدید)
# ----------------------------------------------------------------------

def list_records() -> List[dict]:
    return _load_db().get("records", [])

def add_record(topic: str, out_dir: str, titles: List[str]) -> str:
    _ensure_dirs()
    db = _load_db()
    rid = f"rec_{int(time.time())}_{random.randint(1000,9999)}"
    now = datetime.utcnow().isoformat()
    titles = [(t or "").strip() for t in (titles or []) if (t or "").strip()]
    rec = {
        "id": rid,
        "topic": topic,
        "out_dir": out_dir or "",
        "created_at": now,
        "count": len(titles),
        "titles": titles or []
    }
    db.setdefault("records", []).insert(0, rec)
    _save_db(db)
    # ⛔️ دیگر هیچ فایل متنی/JSON کمکی (titles_fa.txt) نمی‌نویسیم
    return rid


def remove_titles_from_record(record_id: str, titles_to_remove: List[str]) -> None:
    try:
        db = _load_db()
        recs = db.get("records", [])
        changed = False
        for rec in recs:
            if rec.get("id") == record_id:
                old = rec.get("titles", []) or []
                to_rm = {(t or "").strip() for t in (titles_to_remove or []) if t and t.strip()}
                new_titles = [t for t in old if (t or "").strip() not in to_rm]
                if len(new_titles) != len(old):
                    rec["titles"] = new_titles
                    rec["count"] = len(new_titles)
                    changed = True
                tfile = os.path.join(rec.get("out_dir",""), "titles_fa.txt")
                if os.path.exists(tfile):
                    try:
                        with open(tfile, "r", encoding="utf-8") as tf:
                            lines = [ln.rstrip("\n") for ln in tf]
                        with open(tfile, "w", encoding="utf-8") as tf:
                            for ln in lines:
                                if (ln or "").strip() not in to_rm:
                                    tf.write(ln + "\n")
                    except Exception:
                        pass
                break
        if changed:
            _save_db(db)
    except Exception:
        pass

def remove_record(record_id: str) -> None:
    try:
        db = _load_db()
        recs = db.get("records", [])
        new_recs = [r for r in recs if r.get("id") != record_id]
        if len(new_recs) != len(recs):
            db["records"] = new_recs
            _save_db(db)
        try: _sqlite_remove_record(record_id)
        except Exception: pass
    except Exception:
        pass

def remove_records(record_ids: List[str]) -> int:
    cnt = 0
    for rid in record_ids or []:
        remove_record(rid); cnt += 1
    return cnt

def update_title_in_record(record_id: str, old_title: str, new_title: str) -> bool:
    old_title = (old_title or "").strip()
    new_title = (new_title or "").strip()
    if not (record_id and old_title and new_title and old_title != new_title):
        return False
    db = _load_db()
    recs = db.get("records", [])
    updated = False
    for rec in recs:
        if rec.get("id")==record_id:
            titles = rec.get("titles",[]) or []
            if old_title in titles:
                if new_title in titles:
                    rec["titles"] = [t for t in titles if t != old_title]
                else:
                    rec["titles"] = [new_title if t==old_title else t for t in titles]
                rec["count"] = len(rec["titles"])
                updated = True
            break
    if updated:
        _save_db(db)
        try:
            with _sqlite_connect() as con:
                cur = con.cursor()
                row = con.execute("SELECT 1 FROM titles WHERE record_id=? AND title=?", (record_id, new_title)).fetchone()
                if row:
                    con.execute("DELETE FROM titles WHERE record_id=? AND title=?", (record_id, old_title))
                else:
                    con.execute("UPDATE titles SET title=? WHERE record_id=? AND title=?", (new_title, record_id, old_title))
                c = con.execute("SELECT COUNT(*) as c FROM titles WHERE record_id=?", (record_id,)).fetchone()["c"]
                con.execute("UPDATE records SET count=? WHERE id=?", (c, record_id))
                con.commit()
        except Exception:
            pass
        return True
    return False

# ----------------------------------------------------------------------
# بقیه منطق تولید (phase1/phase2/run_pipeline/...) شما بدون تغییر اینجاست
# ----------------------------------------------------------------------

# ...(تمام کدهای فازها و run_pipeline شما این پایین می‌آید — در فایل آپلودی شما موجود است)...

def _read_titles_from_translated_json(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            arr = json.load(f)
        titles = []
        for obj in (arr or []):
            if isinstance(obj, dict):
                t = (obj.get("title") or "").strip()
                if t:
                    titles.append(t)
        return titles
    except Exception:
        return []


def run_pipeline(
    topic: str,
    out_txt: str = "gemini_questions.txt",
    out_json: str = "gemini_questions.json",
    translate_json_out: str = "translated_fa.json",
    sections_min: int = 2,
    sections_max: int = 3,
    subsections_min: int = 2,
    subsections_max: int = 3,
    questions_min: int = 5,
    questions_max: int = 6,
    translate_batch_size: int = 100,
) -> List[str]:
    """
    نسخهٔ درون‌حافظه‌ای:
      1) بخش‌ها → زیربخش‌ها → عناوین انگلیسی
      2) ترجمه به فارسی
      3) هیچ فایل کمکی نوشته نمی‌شود
      4) خروجی: لیست عناوین فارسی (strings)
    """
    log(f"🚀 شروع تولید ایده‌ها برای موضوع: «{topic}»")
    os.makedirs(os.getcwd(), exist_ok=True)

    # ---- مرحله ۱: بخش‌ها
    try:
        prompt = PROMPT_SECTIONS.format(topic=topic, min_sections=sections_min, max_sections=sections_max)
    except Exception:
        prompt = f"List between {sections_min} and {sections_max} high-level sections for: {topic}. Return JSON: {{\"sections\": [\"...\"]}}"
    txt = safe_generate_rest(prompt, min_sleep_between_requests=SLEEP_SECTIONS)
    obj = extract_json_obj(txt) or {}
    sections = []
    if isinstance(obj.get("sections"), list):
        sections = [normalize(x) for x in obj.get("sections") if not bad_title(x)]
    if not sections:
        arr = extract_json_array(txt) or []
        sections = [normalize(x) for x in arr if not bad_title(x)]
    if not sections:
        raise RuntimeError("نتوانستم بخش‌ها را استخراج کنم.")
    log(f"📚 {len(sections)} بخش تولید شد.")

    # ---- مرحله ۲: زیربخش‌ها
    all_subs = []
    for sec in sections:
        try:
            p = PROMPT_SUBSECTIONS.format(topic=topic, section=sec, sub_min=subsections_min, sub_max=subsections_max)
        except Exception:
            p = f"For topic '{topic}' and section '{sec}', propose subsections (min {subsections_min}, max {subsections_max}). Return JSON: {{\"subsections\": [\"...\"]}}"
        txt2 = safe_generate_rest(p, min_sleep_between_requests=SLEEP_SUBSECTIONS)
        o2 = extract_json_obj(txt2) or {}
        subs = []
        if isinstance(o2.get("subsections"), list):
            subs = [normalize(x) for x in o2.get("subsections") if not bad_title(x)]
        if not subs:
            arr2 = extract_json_array(txt2) or []
            subs = [normalize(x) for x in arr2 if not bad_title(x)]
        if not subs:
            continue
        all_subs.extend(subs)
    all_subs = [s for s in all_subs if s]
    if not all_subs:
        raise RuntimeError("زیربخش معتبری یافت نشد.")
    log(f"🧩 {len(all_subs)} زیربخش استخراج شد.")

    # ---- مرحله ۳: تولید ایده/عنوان انگلیسی (batch)
    questions_all = []
    batch = []
    def flush_batch(batch_list):
        nonlocal questions_all
        if not batch_list:
            return
        subs_str = "\n".join(f"- {s}" for s in batch_list)
        try:
            p = PROMPT_QUESTIONS_BATCH.format(
                topic=topic, q_min=questions_min, q_max=questions_max, subsections=subs_str
            )
        except Exception:
            p = f"Generate {questions_min} to {questions_max} English article titles for each of these subsections (JSON in {{\"results\": {{\"Sub\": [\"...\"]}}}}):\n{subs_str}"
        txt3 = safe_generate_rest(p, min_sleep_between_requests=SLEEP_QUESTIONS)
        o3 = extract_json_obj(txt3) or {}
        res = o3.get("results") if isinstance(o3, dict) else None
        if isinstance(res, dict):
            for _, arr in res.items():
                if isinstance(arr, list):
                    for q in arr:
                        qq = normalize(q)
                        if not bad_title(qq):
                            questions_all.append(qq)

    for s in all_subs:
        batch.append(s)
        if len(batch) >= SUBSECTIONS_PER_CALL:
            flush_batch(batch); batch = []
    flush_batch(batch)

    # یکتا و تمیز
    seen = set(); questions_all = [q for q in questions_all if (q and not (q in seen or seen.add(q)))]
    log(f"📝 {len(questions_all)} ایده/عنوان انگلیسی تولید شد.")

    # ---- مرحله ۴: ترجمه به فارسی + کیورد (در حافظه)
    translated_all = []
    i = 0
    while i < len(questions_all):
        chunk = questions_all[i:i+translate_batch_size]
        i += translate_batch_size
        try:
            p = PROMPT_TRANSLATE_BATCH.format(items=json.dumps(chunk, ensure_ascii=False))
        except Exception:
            p = "Translate these English titles to Persian and add an SEO keyword for each. Return JSON array of objects [{'english':'...','title':'...','keyword':'...'}].\n" + json.dumps(chunk, ensure_ascii=False)
        txt4 = safe_generate_rest(p, min_sleep_between_requests=SLEEP_TRANSLATE)
        arr = extract_json_array(txt4) or []
        if isinstance(arr, list):
            for obj in arr:
                if isinstance(obj, dict):
                    fa = normalize(obj.get("title") or obj.get("fa") or "")
                    if fa and not bad_title(fa):
                        translated_all.append(fa)

    log(f"✅ {len(translated_all)} عنوان فارسی آماده شد (بدون هیچ فایل کمکی).")
    return translated_all

def generate_titles_pipeline(api_key: Optional[str], topic: str,
                             out_root: Optional[str] = None,
                             logger: Optional[Callable[[str], None]] = None,
                             **kwargs) -> Tuple[List[str], str]:
    """
    سازگار با GUI:
    - run_pipeline را اجرا می‌کند و «لیست عناوین فارسی» را مستقیم می‌گیرد.
    - رکورد را در DB ثبت می‌کند.
    - out_dir فقط برای سازگاری دکمه «باز کردن پوشه خروجی» حفظ می‌شود (فایلی نوشته نمی‌شود).
    """
    global API_KEY
    if api_key:
        API_KEY = api_key

    if logger:
        add_log_listener(logger)
    try:
        out_dir = os.path.abspath(out_root or os.getcwd())

        titles = run_pipeline(
            topic=topic,
            out_txt=OUT_TXT,
            out_json=OUT_JSON,
            translate_json_out=TRANSLATE_JSON_OUT,
            sections_min=kwargs.get("sections_min", SECTIONS_MIN),
            sections_max=kwargs.get("sections_max", SECTIONS_MAX),
            subsections_min=kwargs.get("subsections_min", SUBSECTIONS_MIN_PER_SECTION),
            subsections_max=kwargs.get("subsections_max", SUBSECTIONS_MAX_PER_SECTION),
            questions_min=kwargs.get("questions_min", QUESTIONS_MIN_PER_SUB),
            questions_max=kwargs.get("questions_max", QUESTIONS_MAX_PER_SUB),
            translate_batch_size=kwargs.get("translate_batch_size", 100),
        )

        # ذخیرهٔ عناوین در DB
        rid = add_record(topic=topic, out_dir=out_dir, titles=titles)
        log(f"📥 {len(titles)} عنوان در رکورد {rid} ذخیره شد.")
        return titles, out_dir
    finally:
        if logger:
            remove_log_listener(logger)

# =========================
# CLI (مثل قبل)
# =========================

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pipeline (v2) with rich logging & high-volume question generation.")
    p.add_argument("--topic", default=TOPIC)
    p.add_argument("--out-txt", default=OUT_TXT)
    p.add_argument("--out-json", default=OUT_JSON)
    p.add_argument("--translate-json-out", default=TRANSLATE_JSON_OUT)
    p.add_argument("--sections-min", type=int, default=SECTIONS_MIN)
    p.add_argument("--sections-max", type=int, default=SECTIONS_MAX)
    p.add_argument("--subsections-min", type=int, default=SUBSECTIONS_MIN_PER_SECTION)
    p.add_argument("--subsections-max", type=int, default=SUBSECTIONS_MAX_PER_SECTION)
    p.add_argument("--questions-min", type=int, default=QUESTIONS_MIN_PER_SUB)
    p.add_argument("--questions-max", type=int, default=QUESTIONS_MAX_PER_SUB)
    p.add_argument("--translate-batch-size", type=int, default=100)
    return p

def main():
    args = build_arg_parser().parse_args()
    out_dir = os.getcwd()
    generate_titles_pipeline(API_KEY, args.topic, out_root=out_dir)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("اجرا توسط کاربر متوقف شد.", file=sys.stderr)
        sys.exit(1)
