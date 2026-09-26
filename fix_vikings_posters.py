import json,re,sys
from curl_cffi import requests

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
TMDB_ID=44217
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def tmdb_season_poster(season):
    u=f"https://www.themoviedb.org/tv/{TMDB_ID}/season/{season}/images/posters"
    r=requests.get(u,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"},timeout=25,impersonate="chrome",allow_redirects=True)
    r.raise_for_status()
    t=r.text.replace("\\/","/")
    urls=re.findall(r'https://image\.tmdb\.org/t/p/original/[^"\'<>\s]+',t,re.I)
    if not urls:
        urls=re.findall(r'https://image\.tmdb\.org/t/p/[^"\'<>\s]+',t,re.I)
    return urls[0] if urls else None

d=json.load(open(CAT,encoding="utf-8"))
posters={}
for s in range(1,7):
    p=tmdb_season_poster(s)
    print("SEASON",s,p,flush=True)
    if p:posters[s]=p

changed=0
for x in d.get("movies",[]):
    u=x.get("url") or ""
    m=re.search(r"huyen-thoai-vikings-phan-(\d+)$",u)
    if not m: continue
    s=int(m.group(1))
    p=posters.get(s)
    if p and x.get("poster")!=p:
        print("PATCH",x.get("title"),"->",p,flush=True)
        x["poster"]=p
        changed+=1

json.dump(d,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
assert changed==6, f"expected 6 poster changes, got {changed}"
assert len(set(posters.values()))==6, f"season posters not unique: {posters}"
print({"changed":changed,"uniquePosters":len(set(posters.values()))})
