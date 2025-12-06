# -*- coding: utf-8 -*-
"""quiknote.utils package

Exports common helpers used across the app:

- is_hex64(s: str) -> bool
- clean_url(u: str) -> str
- looks_like_markdown(text: str) -> bool

Re-exports async helpers:
- Worker, thread_pool  (from .threads)

This keeps backward compatibility with older code that did:
    from .utils import clean_url, looks_like_markdown
"""

from __future__ import annotations
import re
from typing import Optional

# ---- small helpers kept for backward-compatibility -------------------------
def is_hex64(s: Optional[str]) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", (s or "")))

def clean_url(u: Optional[str]) -> str:
    u = (u or '').strip().rstrip('/')
    if not u:
        return ''
    if not u.lower().startswith(('http://','https://')):
        u = 'https://' + u
    return u

# ---- Markdown heuristic -----------------------------------------------------
_md_cues = [
    re.compile(r"(^|\n)\s{0,3}#{1,6}\s+\S"),   # headings
    re.compile(r"(^|\n)\s{0,3}[-*+]\s+\S"),   # unordered lists
    re.compile(r"(^|\n)\s{0,3}\d+\.\s+\S"), # ordered lists
    re.compile(r"```[\s\S]+?```"),              # fenced code
    re.compile(r"\*\*[^*\n]+?\*\*"),         # **bold**
    re.compile(r"__[^_\n]+?__"),                 # __bold__
    re.compile(r"`[^`\n]+?`"),                   # `code`
    re.compile(r"\[[^\]]+?\]\([^)]+?\)"),    # [text](url)
]
_html_like = re.compile(r"</?[a-zA-Z][^>]*>")

def looks_like_markdown(text: Optional[str]) -> bool:
    if not text or not isinstance(text, str):
        return False
    s = text.strip()
    if not s:
        return False
    # If it's pure HTML-ish without markdown cues, treat as not-markdown
    if _html_like.search(s) and not any(p.search(s) for p in _md_cues):
        return False
    hits = 0
    for p in _md_cues:
        if p.search(s):
            hits += 1
            if hits >= 2:
                return True
    return hits >= 2

# ---- Re-export Worker & thread_pool from .threads ---------------------------
try:
    from .threads import Worker, thread_pool  # noqa: F401
except Exception:
    Worker = None
    thread_pool = None

__all__ = [
    'is_hex64',
    'clean_url',
    'looks_like_markdown',
    'Worker',
    'thread_pool',
]
