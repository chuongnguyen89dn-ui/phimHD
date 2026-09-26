import json,re,html,sys,time,collections
from curl_cffi import requests

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
AUD=sys.argv[2] if len(sys.argv)>2 else "poster_duplicate_audit.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def fetch(url,referer="https://rophims.team/"):
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9,vi;q=0.8","Referer":referer},timeout=25,impersonate="chrome",allow_redirects=True)
    if r.status_code>=400:return ""
    return r.text.replace("\\/","/")

def page_tmdb_id(url):
    try:t=fetch(url)
    except:return None
    m=re.search(r'var\s+tmdbData\s*=\s*(\{.*?\});',t,re.I|re.S)
    if not m:return None
    try:d=json.loads(m.group(1))
    except:return None
    if d.get("type")=="tv" and d.get("id"):return int(d["id"])
    return None

def tmdb_season_poster(tid,season):
    try:
        u=f"https://www.themoviedb.org/tv/{int(tid)}/season/{int(season)}/images/posters"
        t=fetch(u,"https://www.themoviedb.org/")
        urls=re.findall(r'https://image\.tmdb\.org/t/p/original/[^"\'<>\s]+',t,re.I)
        if not urls:
            urls=re.findall(r'https://image\.tmdb\.org/t/p/[^"\'<>\s]+',t,re.I)
        # de-dupe while preserving page order
        seen=[]
        for x in urls:
            x=html.unescape(x)
            if x not in seen:seen.append(x)
        return seen[0] if seen else None
    except:return None

cat=json.load(open(CAT,encoding="utf-8"))
aud=json.load(open(AUD,encoding="utf-8"))
by={str(x.get("url") or "").rstrip("/"):x for x in cat.get("movies",[]) if isinstance(x,dict)}

targets={}
for group in aud.get("multiSeasonSamePoster",[]):
    for item in group.get("items",[]):
        u=str(item.get("url") or "").rstrip("/")
        s=item.get("season")
        if u and s:
            targets[u]=int(s)

print("TARGET_URLS",len(targets),flush=True)

changed=0;missing_tmdb=[];missing_poster=[];resolved_urls=[];tid_cache={}
for i,(u,s) in enumerate(targets.items(),1):
    x=by.get(u)
    if not x: continue
    tid=tid_cache.get(u)
    if tid is None:
        tid=page_tmdb_id(u)
        tid_cache[u]=tid
    if not tid:
        missing_tmdb.append({"url":u,"title":x.get("title"),"season":s})
        print(f"[{i}/{len(targets)}] NO_TMDB s{s} {x.get('title')}",flush=True)
        continue
    p=tmdb_season_poster(tid,s)
    if not p:
        missing_poster.append({"url":u,"title":x.get("title"),"season":s,"tmdbId":tid})
        print(f"[{i}/{len(targets)}] NO_POSTER tmdb={tid} s{s} {x.get('title')}",flush=True)
        continue
    if x.get("poster")!=p:
        print(f"[{i}/{len(targets)}] PATCH tmdb={tid} s{s} {x.get('title')} -> {p}",flush=True)
        x["poster"]=p;changed+=1
    resolved_urls.append(u)
    time.sleep(0.03)

cat["seasonPosterBulkRepair"]={
    "targetUrls":len(targets),
    "changed":changed,
    "resolvedUrls":len(resolved_urls),
    "missingTmdb":len(missing_tmdb),
    "missingSeasonPoster":len(missing_poster),
    "missingTmdbExamples":missing_tmdb[:100],
    "missingPosterExamples":missing_poster[:100],
}
json.dump(cat,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(cat["seasonPosterBulkRepair"],ensure_ascii=False),flush=True)
