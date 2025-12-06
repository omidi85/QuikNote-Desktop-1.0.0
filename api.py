# -*- coding: utf-8 -*-
from __future__ import annotations
import json, logging
from typing import Any, Dict, Optional, Union, Mapping
import requests

# --- HWID providers ---
try:
    from .hwid import get_hwid as _get_hwid, get_hwid_legacy as _get_hwid_legacy  # type: ignore
except Exception:
    def _get_hwid() -> str: return ""
    def _get_hwid_legacy() -> str: return ""

# --- Exceptions ---
class APIError(RuntimeError):
    def __init__(self, code: str, status: int = 200, payload: Optional[dict] = None) -> None:
        super().__init__(code); self.code = code; self.status = status; self.payload = payload or {}
class HWIDInUseError(APIError): pass
class TransportError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message); self.status = status

# --- Helpers ---
def _clean_url(u: str) -> str:
    u = (u or "").strip().rstrip("/")
    if not u.lower().startswith(("http://", "https://")):
        raise ValueError("Base URL must include scheme, e.g. https://example.com")
    return u
def _join(base: str, path: str) -> str:
    base = _clean_url(base); path = (path or "").strip()
    if path.startswith("/"): path = path[1:]
    return f"{base}/{path}"

class CentralAPI:
    def __init__(self, *args, **kwargs) -> None:
        base_url = kwargs.pop("base_url", None)
        email    = kwargs.pop("email", None)
        timeout  = kwargs.pop("timeout", 15.0)
        logger   = kwargs.pop("logger", None)
        session  = kwargs.pop("session", None)

        if len(args) >= 1 and base_url is None: base_url = args[0]
        if len(args) >= 2 and email    is None: email    = args[1]
        if len(args) >= 3 and isinstance(args[2], (int, float)): timeout = args[2]

        self.base_url = (base_url or "").strip()
        self.email    = (email or "")
        self.timeout  = float(timeout)

        self._password: str   = ""
        self.session_token: str = ""
        self._logged_in: bool = False  # ← بدون True شدن، درخواست حساس مجاز نیست

        self.s = session or requests.Session()
        self.log = logger or logging.getLogger("CentralAPI")
        if not self.log.handlers:
            h = logging.StreamHandler(); h.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s"))
            self.log.addHandler(h); self.log.setLevel(logging.INFO)

    # ---------- internal request ----------
    def _post(self, route: str, payload: Optional[Mapping[str, Any]] = None,
              headers: Optional[Mapping[str, str]] = None,
              allow_200_ok_false: bool = False, sensitive: bool = True) -> Dict[str, Any]:

        if not self.base_url:
            raise TransportError("Missing base_url; set CentralAPI('https://...') before calling.")

        url  = _join(self.base_url, route.lstrip("/"))
        body: Dict[str, Any] = {}
        if payload: body.update(dict(payload))

        # Always inject HWID
        if not body.get("hwid"): body["hwid"] = _get_hwid()
        if "hwid_legacy" not in body: body["hwid_legacy"] = _get_hwid_legacy()
        if self.email and "email" not in body: body["email"] = self.email

        # For sensitive routes, enforce auth flow
        if sensitive:
            if not self._logged_in:
                raise TransportError("not_authenticated: call auth_check() successfully first", status=0)
            if self.session_token and "session" not in body:
                body["session"] = self.session_token
            if not self.session_token and self._password and "password" not in body:
                # Compat with MU v3.1.2: use password if server doesn't provide session
                body["password"] = self._password

        hdrs = {"Content-Type": "application/json"}
        if headers: hdrs.update(headers)

        r = self.s.post(url, json=body, headers=hdrs, timeout=self.timeout)

        # Debug (optional): uncomment for tracing
        # print(">>> POST", route, "payload:", json.dumps(body, ensure_ascii=False), "STATUS:", r.status_code, "RAW:", r.text[:300])

        if r.status_code < 200 or r.status_code >= 300:
            try: data = r.json()
            except Exception: data = None
            if r.status_code == 403 and isinstance(data, dict):
                code = str(data.get("code") or data.get("error") or "")
                if code == "hwid_in_use": raise HWIDInUseError(code="hwid_in_use", status=403, payload=data)
            if r.status_code == 400 and isinstance(data, dict):
                code = str(data.get("code") or "")
                # تبدیل به خطای واضح برای اپ
                raise APIError(code or "bad_request", status=400, payload=data)
            raise TransportError(f"HTTP {r.status_code}", status=r.status_code)

        try:
            data = r.json()
        except ValueError:
            txt = r.content.decode("utf-8-sig", errors="replace").strip()
            try: data = json.loads(txt)
            except Exception: raise TransportError("invalid_json_response", status=r.status_code)

        if isinstance(data, dict) and (data.get("ok") is False) and not allow_200_ok_false:
            err_code = str(data.get("error") or data.get("code") or "request_failed")
            if err_code == "hwid_in_use": raise HWIDInUseError(err_code, status=r.status_code, payload=data)
            raise APIError(err_code, status=r.status_code, payload=data)

        return data

    # ---------- high-level ----------
    def auth_check(self, email: str, password: str) -> Dict[str, Any]:
        """Must be called before any sensitive route. Raises on failure."""
        self.email = email
        self._password = password or ""
        data = self._post("/wp-json/quiknote/v1/auth/check",
                          payload={"email": email, "password": password},
                          sensitive=False)
        # سرور شما ممکن است ok/session برنگرداند؛ ولی اگر 200 داده یعنی اعتبار درست بوده.
        if isinstance(data, dict) and data.get("ok") is False:
            raise APIError(str(data.get("error") or "login_failed"), payload=data)
        # اگر session هست نگه دار
        if isinstance(data, dict) and data.get("session"):
            self.session_token = str(data.get("session"))
        # علامت موفقیت؛ از اینجا به بعد sensitive مجاز است
        self._logged_in = True
        return data

    def profile_get(self) -> Dict[str, Any]:
        """Canonical. Requires prior auth_check()."""
        return self._post("/wp-json/quiknote/v1/profile/get", payload={}, sensitive=True)

    def credits_get(self) -> Dict[str, Any]:
        """Try /credits/get else fallback to profile_get()."""
        try:
            return self._post("/wp-json/quiknote/v1/credits/get", payload={}, sensitive=True)
        except TransportError as e:
            if e.status == 404:
                prof = self.profile_get()
                return {"ok": True, "credits": int(prof.get("credits", 0)), "source": "profile_get"}
            raise

    def credits_consume(self, amount: int, reason: str = "") -> Dict[str, Any]:
        try:
            return self._post("/wp-json/quiknote/v1/credits/consume",
                              payload={"amount": int(amount), "reason": reason or ""},
                              sensitive=True)
        except TransportError as e:
            if e.status == 404:
                raise APIError("credits_consume_route_missing", status=404, payload={"amount": amount})
            raise

    def support_thread(self, thread_id: Union[int, str]) -> Dict[str, Any]:
        return self._post("/wp-json/quiknote/v1/support/thread", payload={"thread_id": thread_id}, sensitive=True)

    def notifications(self) -> Dict[str, Any]:
        return self._post("/wp-json/quiknote/v1/notifications", payload={}, sensitive=True)
