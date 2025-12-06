# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict
from collections import deque

class NotificationManager:
    """
    صف نوتیف‌ها برای نمایش پشت‌سرهم در یک بنر (تا وقتی کاربر ببندد).
    """
    def __init__(self):
        self._q: deque[Dict] = deque()
        self._active = False
        self._banner = None

    def attach_banner(self, banner):
        self._banner = banner
        banner.closed.connect(self._on_closed)

    def enqueue(self, notifs: List[Dict], base_url: str = ""):
        if not notifs: return
        for n in notifs:
            if not isinstance(n, dict): continue
            n = dict(n)
            cta = n.get("cta") or {}
            url = cta.get("url")
            if url and url.startswith("/") and base_url:
                cta = dict(cta)
                cta["url"] = base_url.rstrip("/") + url
                n["cta"] = cta
            self._q.append(n)
        self._try_show_next()

    def _try_show_next(self):
        if self._active or not self._banner: return
        if not self._q:
            self._banner.hide()
            return
        self._active = True
        item = self._q.popleft()
        self._banner.set_notification(item)
        self._banner.show()

    def _on_closed(self):
        self._active = False
        self._try_show_next()
