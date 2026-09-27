import json, concurrent.futures
from urllib.parse import urlparse
from curl_cffi import requests

PROD="https://phimhd-upos.onrender.com"
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"

def get_json(u):
    last=None
    for i in range(5):
        try:
            r=requests.get(u,headers={"User-Agent":UA,"Accept":"application/json","Cache-Control":"no-cache"},timeout=30,impersonate="chrome",allow_redirects=True)
            if r.status_code<500:
                r.raise_for_status()
                return r.json()
            last=RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last=e
        import time; time.sleep(2*(i+1))
    raise last

man=get_json(PROD+"/manifest.json")
cats=[c for c in man.get("catalogs",[]) if str(c.get("id","")).startswith("ivy_home_")]
cards=[]
for c in cats:
    d=get_json(f"{PROD}/catalog/{c.get('type','movie')}/{c['id']}.json")
    for i,m in enumerate(d.get("metas") or []):
        cards.append({"catalog":c["id"],"name":c.get("name"),"index":i,"title":m.get("name"),"poster":m.get("poster"),"website":m.get("website")})

def check(x):
    u=str(x.get("poster") or "")
    if not u.startswith(("http://","https://")) or "\\" in u:
        return {**x,"ok":False,"reason":"malformed","status":None,"contentType":None}
    try:
        r=requests.get(u,headers={"User-Agent":UA,"Referer":"https://rophims.team/","Range":"bytes=0-2047","Accept":"image/avif,image/webp,image/apng,image/*,*/*;q=0.8"},timeout=15,impersonate="chrome",allow_redirects=True)
        ct=(r.headers.get("content-type") or "").lower()
        ok=r.status_code in (200,206) and (ct.startswith("image/") or len(r.content)>500)
        return {**x,"ok":ok,"reason":"" if ok else "http_or_content","status":r.status_code,"contentType":ct,"bytes":len(r.content)}
    except Exception as e:
        return {**x,"ok":False,"reason":type(e).__name__,"status":None,"contentType":None}

with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
    rows=list(ex.map(check,cards))
bad=[x for x in rows if not x["ok"]]
report={"productionVersion":man.get("version"),"cardsChecked":len(rows),"healthy":len(rows)-len(bad),"unhealthy":len(bad),"bad":bad}
json.dump(report,open("visible_poster_health.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({"productionVersion":report["productionVersion"],"cardsChecked":report["cardsChecked"],"healthy":report["healthy"],"unhealthy":report["unhealthy"]},ensure_ascii=False))
for x in bad[:100]:
    print("BAD",x["catalog"],x["index"],x["title"],x["status"],x["reason"],x["poster"])
# rerun after catalog reload 1.12.2
