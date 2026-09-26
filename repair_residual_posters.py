import json,re,html,sys,time,collections
from curl_cffi import requests

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
AUD=sys.argv[2] if len(sys.argv)>2 else "poster_duplicate_audit.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def fetch(url,referer="https://rophims.team/"):
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9,vi;q=0.8","Referer":referer},timeout=25,impersonate="chrome",allow_redirects=True)
    if r.status_code>=400:return ""
    return r.text.replace("\\/","/")

def parse_source(url):
    try:t=fetch(url)
    except:return {},None
    tm={}
    m=re.search(r'var\s+tmdbData\s*=\s*(\{.*?\});',t,re.I|re.S)
    if m:
        try:tm=json.loads(m.group(1))
        except:tm={}
    pm=re.search(r'''var\s+moviePosterUrl\s*=\s*["']([^"']+)''',t,re.I)
    sp=html.unescape(pm.group(1)).strip() if pm else None
    return tm,sp

def tmdb_candidates(tm, title_season):
    if not isinstance(tm,dict) or not tm.get("id"):return []
    tid=int(tm["id"]); typ=tm.get("type")
    out=[]
    def add_from(url):
        try:t=fetch(url,"https://www.themoviedb.org/")
        except:return
        pats=[
            r'https://image\.tmdb\.org/t/p/original/[^"\'<>\s]+',
            r'https://image\.tmdb\.org/t/p/w600_and_h900_bestv2/[^"\'<>\s]+',
            r'https://image\.tmdb\.org/t/p/w500/[^"\'<>\s]+'
        ]
        for pat in pats:
            for x in re.findall(pat,t,re.I):
                x=html.unescape(x)
                if x not in out:out.append(x)
    if typ=="tv":
        mapped=tm.get("season")
        try:mapped=int(mapped) if mapped not in (None,"") else None
        except:mapped=None
        seasons=[]
        if mapped is not None:seasons.append(mapped)
        if title_season is not None and int(title_season) not in seasons:seasons.append(int(title_season))
        for s in seasons:
            add_from(f"https://www.themoviedb.org/tv/{tid}/season/{s}/images/posters")
            add_from(f"https://www.themoviedb.org/tv/{tid}/season/{s}")
        # show poster as last resort, still sourced to exact title
        add_from(f"https://www.themoviedb.org/tv/{tid}/images/posters")
    elif typ=="movie":
        add_from(f"https://www.themoviedb.org/movie/{tid}/images/posters")
        add_from(f"https://www.themoviedb.org/movie/{tid}")
    return out

cat=json.load(open(CAT,encoding="utf-8"))
aud=json.load(open(AUD,encoding="utf-8"))
by={str(x.get("url") or "").rstrip("/"):x for x in cat.get("movies",[]) if isinstance(x,dict)}

groups=[]
# Work on every duplicated-poster group surfaced by audit categories.
for key in ("multiSeasonSamePoster","topCrossFamilyPosterReuse","topSameFamilyPosterReuse"):
    for g in aud.get(key,[]) or []:
        items=g.get("items") or []
        if len(items)>=2:groups.append((key,g))

# dedupe groups by poster+urls
seen=set();uniq=[]
for kind,g in groups:
    sig=(g.get("poster"),tuple(sorted(str(i.get("url") or "") for i in (g.get("items") or []))))
    if sig in seen:continue
    seen.add(sig);uniq.append((kind,g))

changed=0;groups_resolved=0;records_examined=0;unresolved=[]
for gi,(kind,g) in enumerate(uniq,1):
    items=g.get("items") or []
    recs=[]
    for it in items:
        u=str(it.get("url") or "").rstrip("/")
        x=by.get(u)
        if not x:continue
        tm,srcp=parse_source(u)
        cands=[]
        if srcp:cands.append(srcp)
        for p in tmdb_candidates(tm,it.get("season")):
            if p not in cands:cands.append(p)
        recs.append({"x":x,"u":u,"title":it.get("title"),"season":it.get("season"),"tm":tm,"cands":cands})
        records_examined+=1
    used=set()
    # Prefer current posters only if unique; otherwise pick sourced unique candidate.
    for r in recs:
        cur=str(r["x"].get("poster") or "")
        choice=None
        for p in r["cands"]:
            if p and p not in used:
                choice=p;break
        if choice is None and cur and cur not in used:choice=cur
        if choice:
            used.add(choice)
            if choice!=cur:
                r["x"]["poster"]=choice;changed+=1
                print(f"PATCH [{kind}] {r['title']} -> {choice}",flush=True)
    finals=[str(r["x"].get("poster") or "") for r in recs]
    ok=len(finals)>=2 and len(set(finals))==len(finals)
    if ok:groups_resolved+=1
    else:
        unresolved.append({
            "kind":kind,"poster":g.get("poster"),
            "titles":[r["title"] for r in recs],
            "finalPosters":finals,
            "tmdb":[r["tm"] for r in recs],
            "candidateCounts":[len(r["cands"]) for r in recs]
        })
    print(f"[{gi}/{len(uniq)}] {kind} items={len(recs)} unique={len(set(finals))}/{len(finals)} resolved={ok}",flush=True)
    time.sleep(0.02)

cat["posterResidualRepair"]={
    "groupsTargeted":len(uniq),
    "groupsResolved":groups_resolved,
    "groupsUnresolved":len(unresolved),
    "recordsExamined":records_examined,
    "postersChanged":changed,
    "unresolved":unresolved[:100]
}
json.dump(cat,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(cat["posterResidualRepair"],ensure_ascii=False),flush=True)
