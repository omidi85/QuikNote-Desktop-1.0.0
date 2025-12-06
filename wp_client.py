# -*- coding: utf-8 -*-
import requests, json, re
from .utils import clean_url

class UserWP:
    def __init__(self, site_url, username, app_password, seo_plugin='none'):
        self.base = clean_url(site_url)
        self.username = username
        self.app_password = app_password
        self.seo = (seo_plugin or 'none').lower()

    # ---- SEO meta builder ----
    def _build_meta(self, focus_keyword='', meta_desc=''):
        meta = {}
        if self.seo == 'rankmath':
            if focus_keyword: meta['rank_math_focus_keyword'] = focus_keyword
            if meta_desc:     meta['rank_math_description']   = meta_desc
        elif self.seo == 'yoast':
            if focus_keyword: meta['_yoast_wpseo_focuskw']    = focus_keyword
            if meta_desc:     meta['_yoast_wpseo_metadesc']   = meta_desc
        return meta

    # ---- robust requests helpers (with SSL fallback) ----
    def _safe_post(self, url, payload):
        try:
            return requests.post(
                url,
                auth=(self.username, self.app_password),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                json=payload,
                timeout=60
            )
        except requests.exceptions.SSLError:
            return requests.post(
                url,
                auth=(self.username, self.app_password),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                json=payload,
                timeout=60,
                verify=False
            )

    def _safe_patch(self, url, payload):
        try:
            return requests.patch(
                url,
                auth=(self.username, self.app_password),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                json=payload,
                timeout=60
            )
        except requests.exceptions.SSLError:
            return requests.patch(
                url,
                auth=(self.username, self.app_password),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                json=payload,
                timeout=60,
                verify=False
            )

    def _safe_get(self, url):
        try:
            return requests.get(
                url,
                auth=(self.username, self.app_password),
                headers={'Accept': 'application/json'},
                timeout=60
            )
        except requests.exceptions.SSLError:
            return requests.get(
                url,
                auth=(self.username, self.app_password),
                headers={'Accept': 'application/json'},
                timeout=60,
                verify=False
            )

    # ---- tolerant JSON loader ----
    def _try_json(self, resp):
        if resp is None:
            return None
        try:
            return resp.json()
        except Exception:
            text = resp.text or ''
            # تلاش برای تمیزسازی: اولین { تا آخرین } را بردار
            s = text.find('{'); e = text.rfind('}')
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(text[s:e+1])
                except Exception:
                    return None
            return None

    # اگر بدنه JSON نداشت ولی Location header برگشته بود، JSON پست را می‌گیریم
    def _fetch_by_location(self, resp):
        loc = None
        try:
            loc = resp.headers.get('Location') or resp.headers.get('location')
        except Exception:
            loc = None
        if loc:
            r2 = self._safe_get(loc)
            j2 = self._try_json(r2)
            if isinstance(j2, dict):
                return j2
            # سعی کن id را از URL لوکیشن دربیاری
            m = re.search(r'/posts/(\d+)', loc)
            if m:
                pid = m.group(1)
                r3 = self._safe_get(f"{self.base}/wp-json/wp/v2/posts/{pid}")
                j3 = self._try_json(r3)
                if isinstance(j3, dict):
                    return j3
        return None

    def create_post(self, title, html_content, status='draft', focus_keyword='', meta_desc=''):
        posts_url = f"{self.base}/wp-json/wp/v2/posts"
        payload = {'title': title, 'content': html_content, 'status': status}

        meta = self._build_meta(focus_keyword, meta_desc)
        if meta:
            payload['meta'] = meta

        r = self._safe_post(posts_url, payload)
        j = self._try_json(r)

        # در بعضی هاست‌ها بدنه خالی است ولی 200/201 می‌آید → از Location بگیر
        if (not isinstance(j, dict) or 'id' not in j) and r is not None and r.status_code in (200, 201):
            j2 = self._fetch_by_location(r)
            if isinstance(j2, dict):
                j = j2

        # خطاهای واقعی
        if r is None or r.status_code >= 400:
            msg = None
            if isinstance(j, dict):
                msg = j.get('message') or j.get('data', {}).get('message')
            raise Exception(msg or (r.text if r is not None else 'No response') or f"HTTP {getattr(r,'status_code',None)}")

        # اگر هنوز dict نداریم، خطا بده (برای جلوگیری از NoneType)
        if not isinstance(j, dict):
            raise Exception("Empty / non-JSON response from WP after create_post")

        # تضمین اعمال متا (بعضی ستاپ‌ها فقط با PATCH می‌پذیرند)
        try:
            post_id = j.get('id')
            if post_id and meta:
                patch_url = f"{self.base}/wp-json/wp/v2/posts/{post_id}"
                self._safe_patch(patch_url, {'meta': meta})
        except Exception:
            pass  # اگر PATCH شکست خورد، پست ساخته شده و ادامه می‌دهیم

        return j
