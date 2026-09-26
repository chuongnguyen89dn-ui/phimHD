import json,re,html,collections,sys,time
from curl_cffi import requests

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def season_no(title):
    m=re.search(r"(?i)(?:phần|season)\s*(\d+)",str(title or ""))
    return int(m.group(1)) if m else None

def family_key(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    s=re.sub(r"\s+"," ",s).strip(" -–—:()")
    return s

def fetch(url):
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"vi-VN,vi;q=0.9,en;q=0.8","Referer":"https://rophims.team/"},timeout=20,impersonate="chrome",allow_redirects=True)
    if r.status_code>=400:return ""
    return r.text.replace("\\/","/")

def source_poster_and_tmdb(page):
    pm=re.search(r'''var\s+moviePosterUrl\s*=\s*["']([^"']+)''',page,re.I)
    poster=html.unescape(pm.group(1)).strip() if pm else None
    tm=None
    m=re.search(r'var\s+tmdbData\s*=\s*(\{.*?\});',page,re.I|re.S)
    if m:
        try:tm=json.loads(m.group(1))
        except:pass
    return poster,tm

def tmdb_season_poster(tid,season):
    if not tid or not season:return None
    try:
        u=f"https://www.themoviedb.org/tv/{int(tid)}/season/{int(season)}/images/posters"
        t=fetch(u)
        urls=re.findall(r'https://image\.tmdb\.org/t/p/original/[^"\'<>\s]+',t,re.I)
        if not urls:urls=re.findall(r'https://image\.tmdb\.org/t/p/[^"\'<>\s]+',t,re.I)
        return html.unescape(urls[0]).strip() if urls else None
    except:return None

d=json.load(open(CAT,encoding="utf-8"))
rows=[x for x in d.get("movies",[]) if isinstance(x,dict)]
fams=collections.defaultdict(list)
for x in rows:
    s=season_no(x.get("title"))
    if s:fams[family_key(x.get("title"))].append(x)

targets=[]
for k,g in fams.items():
    if len(g)<2:continue
    ps=[str(x.get("poster") or "") for x in g]
    non=[p for p in ps if p]
    if len(non)>=2 and len(set(non))<len(non):
        targets.append((k,g))

print("DUPLICATE_FAMILIES_BEFORE",len(targets),flush=True)
changed=0;resolved=0;unresolved=[]
for idx,(k,g) in enumerate(targets,1):
    info=[]
    # 1) refetch exact source page for each season
    for x in g:
        page=""
        try:page=fetch(x.get("url") or "")
        except:pass
        sp,tm=source_poster_and_tmdb(page)
        info.append((x,page,sp,tm))
    # Apply source-specific poster first
    for x,page,sp,tm in info:
        if sp and sp!=x.get("poster"):
            x["poster"]=sp;changed+=1
    after=[str(x.get("poster") or "") for x in g if x.get("poster")]
    # 2) if still duplicated, use exact TMDB season poster
    if len(after)>=2 and len(set(after))<len(after):
        tids=[]
        for x,page,sp,tm in info:
            if isinstance(tm,dict) and tm.get("type")=="tv" and tm.get("id"):tids.append(tm.get("id"))
        tid=tids[0] if tids else None
        if tid:
            for x,page,sp,tm in info:
                s=season_no(x.get("title"))
                tp=tmdb_season_poster(tid,s)
                if tp and tp!=x.get("poster"):
                    x["poster"]=tp;changed+=1
                    time.sleep(0.05)
    final=[str(x.get("poster") or "") for x in g if x.get("poster")]
    ok=len(final)>=2 and len(set(final))==len(final)
    if ok:resolved+=1
    else:unresolved.append({"family":k,"titles":[x.get("title") for x in g],"posters":final})
    print(f"[{idx}/{len(targets)}] {k} unique={len(set(final))}/{len(final)} resolved={ok}",flush=True)

d["posterRepair"]={
    "duplicateFamiliesBefore":len(targets),
    "familiesResolved":resolved,
    "familiesUnresolved":len(unresolved),
    "postersChanged":changed,
    "unresolved":unresolved[:100],
}
json.dump(d,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(d["posterRepair"],ensure_ascii=False),flush=True)
