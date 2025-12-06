# -*- coding: utf-8 -*-
import requests, json, time, random
from .utils import looks_like_markdown
try:
    import markdown as md
except Exception:
    md = None

API_BASE="https://generativelanguage.googleapis.com/v1beta"
DEFAULT_PROMPT=(
    "فقط و فقط HTML معتبر خروجی بده. هیچ متن اضافی غیر از تگ‌های HTML ننویس. "
    "ساختار مقاله را داخل تگ <article> قرار بده. "
    "با کلمه کلیدی «{keyword}» یک مقاله فارسی حداقل 1200 کلمه با سرفصل‌های منظم "
    "(با <h2>/<h3>)، مقدمه، تیترهای فرعی، لیست‌ها (<ul><li>...</li></ul>) و جمع‌بندی تولید کن. "
    "از استایل inline استفاده نکن. هیچ مارک‌داونی ننویس."
)
class GeminiError(Exception): pass
def _post_json(url, body, timeout=60):
    return requests.post(url, headers={"Content-Type":"application/json"}, data=json.dumps(body), timeout=timeout)
def _extract_text(data):
    try: return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception: return json.dumps(data, ensure_ascii=False)
def _should_retry(status): return status in (429,500,502,503,504)
def generate_article(keyword, api_key, prompt_template=None, *, prefer_model="gemini-2.5-flash", max_retries=6) -> str:
    if not api_key: raise GeminiError("Gemini API key خالی است")
    prompt=(prompt_template or DEFAULT_PROMPT).format(keyword=keyword)
    body={"contents":[{"parts":[{"text":prompt}]}]}
    model_chain=[prefer_model, "gemini-2.5-flash", "gemini-pro"] if prefer_model!="gemini-pro" else ["gemini-pro","gemini-2.5-flash"]
    last_err=None
    for model in model_chain:
        url=f"{API_BASE}/models/{model}:generateContent?key={api_key}"
        for attempt in range(max_retries):
            try:
                r=_post_json(url, body, timeout=90)
                if r.status_code < 400:
                    txt=_extract_text(r.json()) or ""
                    # اگر اشتباهاً مارک‌داون بود، به HTML تبدیل کن
                    if looks_like_markdown(txt) and md:
                        try:
                            txt = md.markdown(txt, extensions=['extra','sane_lists','nl2br'])
                        except Exception:
                            pass
                    return txt
                if r.status_code in (400,401,403):
                    try: msg=r.json().get("error",{}).get("message") or r.text
                    except Exception: msg=r.text
                    raise GeminiError(f"Gemini {r.status_code}: {msg}")
                if _should_retry(r.status_code):
                    base=0.8*(2**attempt); time.sleep(min(base+random.uniform(0,0.6),10)); continue
                try: msg=r.json().get("error",{}).get("message") or r.text
                except Exception: msg=r.text
                raise GeminiError(f"Gemini {r.status_code}: {msg}")
            except requests.RequestException as e:
                last_err=e; base=0.8*(2**attempt); time.sleep(min(base+random.uniform(0,0.6),10)); continue
        last_err = last_err or GeminiError(f"Model {model} unavailable")
    raise GeminiError(f"مدل‌های درخواستی در دسترس نبودند یا خطا دادند: {last_err}")
