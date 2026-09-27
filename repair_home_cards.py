import json,re,sys
from collections import defaultdict
from datetime import datetime,timezone
from urllib.parse import urlparse
from rophim_catalog_crawler_taxonomy_v5 import parse_detail,norm

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.staging.json"
SITEMAP=sys.argv[2] if len(sys.argv)>2 else "ivy_sitemap.staging.json"
LIMIT=int(sys.argv[3]) if len(sys.argv)>3 else 24
CURRENT=datetime.now(timezone.utc).year

def family(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    s=re.sub(r"\((?:19|20)\d{2}\)"," ",s)
    return " ".join(re.sub(r"[^a-z0-9à-ỹ]+"," ",s).split())

def bad_year(x):
    y=x.get("year")
    if y in (None,""): return True
    try:y=int(y)
    except:return True
    return not (1900<=y<=CURRENT+1)

def copy_fresh(old,fresh):
    keep={k:old.get(k) for k in ("taxonomy","categoryMembership","genres","countries","sections","schedules","categories","sourceLatestRank","playbackHints") if k in old}
    for k in ("title","originalTitle","poster","backdrop","description","year","duration","durationRaw","quality","type","slug","source"):
        if k in fresh:
            old[k]=fresh[k]
    old.update(keep)

cat=json.load(open(CAT,encoding="utf-8"))
sm=json.load(open(SITEMAP,encoding="utf-8"))
rows=cat.get("movies") or []
by={norm(x.get("url") or ""):x for x in rows if isinstance(x,dict) and x.get("url")}

targets=[]
seen=set()
for sec in sm.get("sections") or []:
    for u in (sec.get("urls") or sec.get("home") or [])[:LIMIT]:
        k=norm(u)
        if k and k not in seen and k in by:
            seen.add(k);targets.append(k)

poster_groups=defaultdict(list)
for k in targets:
    p=str(by[k].get("poster") or "").strip()
    if p:poster_groups[p].append(k)
dup_targets=set()
for p,ks in poster_groups.items():
    if len(ks)>1:
        fams={family(by[k].get("title")) for k in ks}
        if len(fams)>1 or len(ks)>1:
            dup_targets.update(ks)

suspect=set()
for k in targets:
    x=by[k]
    if not x.get("poster") or bad_year(x):suspect.add(k)
suspect.update(dup_targets)

changed=0;refreshed=0;failed=[]
for i,k in enumerate(sorted(suspect),1):
    old=by[k]
    before=(old.get("title"),old.get("poster"),old.get("year"))
    try:
        fresh=parse_detail(k)
        if bad_year(fresh):
            fresh["year"]=None
        copy_fresh(old,fresh)
        refreshed+=1
        after=(old.get("title"),old.get("poster"),old.get("year"))
        if after!=before:changed+=1
        print(f"[{i}/{len(suspect)}] refresh {k} before={before} after={after}",flush=True)
    except Exception as e:
        failed.append({"url":k,"error":str(e)})
        print(f"[{i}/{len(suspect)}] FAIL {k} {e}",flush=True)

# Final safety: impossible future years must never be published.
future_cleared=0
for x in rows:
    if bad_year(x) and x.get("year") not in (None,""):
        x["year"]=None;future_cleared+=1

cat["homeCardRepair"]={
    "generatedAt":datetime.now(timezone.utc).isoformat(),
    "visibleTargets":len(targets),
    "suspectTargets":len(suspect),
    "duplicatePosterTargets":len(dup_targets),
    "refreshed":refreshed,
    "changed":changed,
    "futureYearsCleared":future_cleared,
    "failed":failed[:50]
}
json.dump(cat,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(cat["homeCardRepair"],ensure_ascii=False),flush=True)
