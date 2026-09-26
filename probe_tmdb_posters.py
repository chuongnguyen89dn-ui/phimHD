import json,re,html,collections
from curl_cffi import requests

CAT="rophim_catalog.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"
def key(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")
def sno(t):
    m=re.search(r"(?i)(?:phần|season)\s*(\d+)",str(t or ""))
    return int(m.group(1)) if m else None

d=json.load(open(CAT,encoding="utf-8"))
f=collections.defaultdict(list)
for x in d.get("movies",[]):
    if sno(x.get("title")):f[key(x.get("title"))].append(x)
out=[]
for k,g in f.items():
    ps=[x.get("poster") for x in g if x.get("poster")]
    if len(g)<2 or len(ps)<2 or len(set(ps))==len(ps):continue
    rr=[]
    for x in g:
        row={"title":x.get("title"),"url":x.get("url"),"season":sno(x.get("title")),"poster":x.get("poster")}
        try:
            r=requests.get(x["url"],headers={"User-Agent":UA},timeout=20,impersonate="chrome")
            t=r.text.replace("\\/","/")
            m=re.search(r'var\s+tmdbData\s*=\s*(\{.*?\});',t,re.I|re.S)
            td=json.loads(m.group(1)) if m else {}
            row["tmdbData"]=td
            tid=td.get("id"); season=row["season"]
            if tid and td.get("type")=="tv" and season:
                tu=f"https://www.themoviedb.org/tv/{tid}/season/{season}/images/posters"
                tr=requests.get(tu,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"},timeout=20,impersonate="chrome",allow_redirects=True)
                body=tr.text.replace("\/","/")
                imgs=re.findall(r'https://image\.tmdb\.org/t/p/[^"\'<>\s]+',body,re.I)
                # also relative poster paths in srcset/data-src
                paths=re.findall(r'(?:src|data-src)=["\'](https://image\.tmdb\.org/t/p/[^"\']+)',body,re.I)
                row["tmdbPageStatus"]=tr.status_code
                row["tmdbPosterUrls"]=list(dict.fromkeys(imgs+paths))[:20]
                row["tmdbPageLen"]=len(body)
        except Exception as e:row["error"]=repr(e)
        rr.append(row)
    out.append({"family":k,"rows":rr})
json.dump({"families":out},open("poster_tmdb_probe.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False)[:12000])
