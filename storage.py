# -*- coding: utf-8 -*-
import json, os
CONFIG_PATH=os.path.join(os.path.expanduser('~'), '.quiknote_config.json')
DEFAULTS={
  'central_url':'','central_email':'','central_password':'',
  'gemini_api_key':'','gemini_model':'gemini-2.5-flash',
  'user_wp_url':'','user_wp_username':'','user_wp_app_password':'',
  'news_url':'','shop_url':'',
  'seo_plugin':'none'  # 'none' | 'yoast' | 'rankmath'
}
def load():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH,'r',encoding='utf-8') as f:
                d=json.load(f)
                for k,v in DEFAULTS.items(): d.setdefault(k,v)
                return d
    except: pass
    return DEFAULTS.copy()
def save(d):
    with open(CONFIG_PATH,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2)
