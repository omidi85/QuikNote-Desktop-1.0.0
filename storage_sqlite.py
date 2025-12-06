# -*- coding: utf-8 -*-
"""
storage_sqlite.py
لایهٔ ذخیره‌سازی مرکزی روی SQLite برای QuikNote

- مسیر DB: پیش‌فرض ~/.quiknote/quiknote.db (قابل تغییر با ENV: QUIKNOTE_DB_PATH)
- جداول: settings, records, titles, articles, tickets, ticket_messages, logs
- توابع کاربردی که تب‌ها و سرویس‌ها استفاده می‌کنند.
"""

from __future__ import annotations
import os, json, sqlite3, time, random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# ---------------------------
# مسیر دیتابیس
# ---------------------------
def _default_db_path() -> str:
    env = os.environ.get("QUIKNOTE_DB_PATH")
    if env:
        Path(env).parent.mkdir(parents=True, exist_ok=True)
        return env
    base = Path.home() / ".quiknote"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "quiknote.db")

DB_PATH = _default_db_path()

def _connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    # برای پایداری بهتر: foreign keys
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def _now() -> str:
    return datetime.utcnow().isoformat()

# ---------------------------
# ساخت جداول
# ---------------------------
def _init_db():
    with _connect() as con:
        cur = con.cursor()
        # تنظیمات
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        # رکورد و عناوین
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
            english TEXT,
            keyword TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(record_id, title),
            FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
        )""")
        # مقالات تولیدشده/منتشرشده
        cur.execute("""
        CREATE TABLE IF NOT EXISTS articles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT,
            seed TEXT,
            title TEXT,
            html TEXT,
            status TEXT,           -- 'generated' | 'published' | 'failed'
            wp_post_id TEXT,
            wp_url TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE SET NULL
        )""")
        # لاگ‌ها (در صورت نیاز آینده)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT,
            level TEXT,
            message TEXT,
            created_at TEXT
        )""")
        # پشتیبانی (در صورت وجود ماژول‌های مربوطه)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT UNIQUE,
            subject TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT,
            last_sync_at TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ticket_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            server_msg_id TEXT,
            by_admin INTEGER DEFAULT 0,
            body TEXT,
            created_at TEXT,
            UNIQUE(ticket_id, server_msg_id)
        )""")
        con.commit()
_init_db()

# ---------------------------
# Settings
# ---------------------------
def set_setting(key: str, value: Any) -> None:
    with _connect() as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False))
        )
        con.commit()

def get_setting(key: str, default: Any=None) -> Any:
    with _connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

# ---------------------------
# Records & Titles
# ---------------------------
def _make_rid() -> str:
    return f"rec_{int(time.time())}_{random.randint(1000,9999)}"

def add_record(topic: str, out_dir: str, titles: List[str]) -> str:
    rid = _make_rid()
    now = _now()
    titles = [(t or "").strip() for t in (titles or []) if (t or "").strip()]
    with _connect() as con:
        con.execute("INSERT INTO records(id,topic,out_dir,created_at,count) VALUES(?,?,?,?,?)",
                    (rid, topic, out_dir or "", now, len(titles)))
        if titles:
            con.executemany(
                "INSERT OR IGNORE INTO titles(record_id,title,english,keyword,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                [(rid, t, None, None, "new", now, now) for t in titles]
            )
        con.commit()
    return rid

def list_records() -> List[dict]:
    with _connect() as con:
        rows = con.execute("SELECT id,topic,out_dir,created_at,count FROM records ORDER BY datetime(created_at) DESC").fetchall()
        out: List[dict] = []
        for r in rows:
            rid = r["id"]
            titles = [x["title"] for x in con.execute("SELECT title FROM titles WHERE record_id=? ORDER BY id ASC", (rid,)).fetchall()]
            out.append({
                "id": rid,
                "topic": r["topic"],
                "out_dir": r["out_dir"],
                "created_at": r["created_at"],
                "count": r["count"],
                "titles": titles,
            })
        return out

def remove_record(record_id: str, delete_output_dir: bool=False) -> bool:
    with _connect() as con:
        cur = con.execute("DELETE FROM records WHERE id=?", (record_id,))
        con.commit()
        return cur.rowcount > 0

def remove_records(record_ids: List[str], delete_output_dir: bool=False) -> int:
    if not record_ids:
        return 0
    with _connect() as con:
        q = "DELETE FROM records WHERE id IN (%s)" % ",".join("?"*len(record_ids))
        cur = con.execute(q, record_ids)
        con.commit()
        return cur.rowcount

def remove_titles_from_record(record_id: str, titles_to_remove: List[str]) -> int:
    titles_to_remove = [(t or "").strip() for t in (titles_to_remove or []) if (t or "").strip()]
    if not (record_id and titles_to_remove):
        return 0
    with _connect() as con:
        q = "DELETE FROM titles WHERE record_id=? AND title IN (%s)" % ",".join("?"*len(titles_to_remove))
        cur = con.execute(q, [record_id, *titles_to_remove])
        cnt = con.execute("SELECT COUNT(*) AS c FROM titles WHERE record_id=?", (record_id,)).fetchone()["c"]
        con.execute("UPDATE records SET count=? WHERE id=?", (cnt, record_id))
        con.commit()
        return cur.rowcount

def update_title_in_record(record_id: str, old_title: str, new_title: str) -> bool:
    old_title = (old_title or "").strip()
    new_title = (new_title or "").strip()
    if not (record_id and old_title and new_title and old_title != new_title):
        return False
    now = _now()
    with _connect() as con:
        exists = con.execute("SELECT 1 FROM titles WHERE record_id=? AND title=?", (record_id, new_title)).fetchone()
        if exists:
            con.execute("DELETE FROM titles WHERE record_id=? AND title=?", (record_id, old_title))
        else:
            con.execute("UPDATE titles SET title=?, updated_at=? WHERE record_id=? AND title=?",
                        (new_title, now, record_id, old_title))
        cnt = con.execute("SELECT COUNT(*) AS c FROM titles WHERE record_id=?", (record_id,)).fetchone()["c"]
        con.execute("UPDATE records SET count=? WHERE id=?", (cnt, record_id))
        con.commit()
        return True

# ---------------------------
# Articles
# ---------------------------
def add_article(record_id: str, seed: str, title: str, html: str,
                status: str = "generated", wp_post_id: Optional[str] = None, wp_url: Optional[str] = None) -> int:
    now = _now()
    with _connect() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO articles(record_id, seed, title, html, status, wp_post_id, wp_url, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (record_id or "", seed or "", title or "", html or "", status, wp_post_id, wp_url, now, now))
        con.commit()
        return int(cur.lastrowid)

def update_article_status(article_id: int, status: str, *, wp_post_id: Optional[str] = None, wp_url: Optional[str] = None) -> None:
    now = _now()
    with _connect() as con:
        con.execute("""
            UPDATE articles
               SET status=?, wp_post_id=COALESCE(?, wp_post_id), wp_url=COALESCE(?, wp_url), updated_at=?
             WHERE id=?
        """, (status, wp_post_id, wp_url, now, int(article_id)))
        con.commit()

def list_articles(status: Optional[str] = None, search: Optional[str] = None, limit: int = 500) -> List[dict]:
    q = "SELECT id, record_id, seed, title, status, wp_post_id, wp_url, created_at, updated_at FROM articles"
    args, where = [], []
    if status:
        where.append("status=?"); args.append(status)
    if search:
        where.append("(title LIKE ? OR seed LIKE ?)"); args += [f"%{search}%", f"%{search}%"]
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY datetime(created_at) DESC LIMIT ?"; args.append(int(limit))
    with _connect() as con:
        rows = con.execute(q, args).fetchall()
        return [dict(r) for r in rows]

def get_article(article_id: int) -> Optional[dict]:
    with _connect() as con:
        r = con.execute("SELECT * FROM articles WHERE id=?", (int(article_id),)).fetchone()
        return dict(r) if r else None

def delete_article(article_id: int) -> None:
    with _connect() as con:
        con.execute("DELETE FROM articles WHERE id=?", (int(article_id),))
        con.commit()
