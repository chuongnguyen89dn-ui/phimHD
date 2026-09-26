import json,re,html,collections,sys
from curl_cffi import requests
CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def key(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")
def sno(t):
    m=re.search(r"(?i)(?:phần|season)\s*(\d+)",str(t or ""))
    return int(m.group(1)) if m else None

d=json.load(open(CAT,encoding="utf-8")); fam=collections.defaultdict(list)
for x in d.get("movies",[]):
    if sno(x.get("title")): fam[key(x.get("title"))].append(x)
bad=[]
for k,g in fam.items():
    ps=[x.get("poster") for x in g if x.get("poster")]
    if len(g)>=2 and len(ps)>=2 and len(set(ps))<len(ps):
        rows=[]
        for x in g:
            row={"title":x.get("title"),"url":x.get("url"),"poster":x.get("poster"),"season":sno(x.get("title"))}
            try:
                r=requests.get(x.get("url"),headers={"User-Agent":UA,"Referer":"https://rophims.team/"},timeout=20,impersonate="chrome")
                t=r.text.replace("\\/","/")
                def one(p):
                    m=re.search(p,t,re.I|re.S); return html.unescape(m.group(1)).strip() if m else None
                row["moviePosterUrl"]=one(r'''var\s+moviePosterUrl\s*=\s*["']([^"']+)''')
                row["movieThumbUrl"]=one(r'''var\s+movieThumbUrl\s*=\s*["']([^"']+)''')
                imgs=re.findall(r'https?://vsmov\.com/storage/images/[A-Za-z0-9._-]+',t,re.I)
                row["allVsmovImages"]=list(dict.fromkeys(imgs))[:80]
                tm=[]
                for m in re.finditer(r"tmdb|season|poster_path",t,re.I):
                    sn=t[max(0,m.start()-250):m.start()+550]
                    if "poster" in sn.lower() or "season" in sn.lower():tm.append(sn)
                row["tmdbSeasonSnippets"]=tm[:30]
            except Exception as e: row["error"]=repr(e)
            rows.append(row)
        bad.append({"family":k,"rows":rows})
json.dump({"unresolvedFamilies":len(bad),"families":bad},open("unresolved_poster_sources.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({"unresolvedFamilies":len(bad),"names":[x["family"] for x in bad]},ensure_ascii=False))
