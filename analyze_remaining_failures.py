import json,re,urllib.parse,collections,os

AUDIT="full_playback_audit.json"
CAT=os.environ.get("ROPHIM_CATALOG","rophim_catalog.json")
OUT="remaining_failure_analysis.json"

a=json.load(open(AUDIT,encoding="utf-8"))
c=json.load(open(CAT,encoding="utf-8"))
movies=[x for x in c.get("movies",[]) if isinstance(x,dict)]
by={str(x.get("url","")).rstrip("/"):x for x in movies}

def host(u):
    try:return urllib.parse.urlparse(str(u or "")).netloc.lower()
    except:return ""

def family_key(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")

def collect_sources(x):
    h=x.get("playbackHints") or {}
    vals=[]
    for v in h.get("direct") or []: vals.append(v)
    for s in h.get("episodeSources") or []:
        if isinstance(s,dict):
            vals += [s.get("link_m3u8"),s.get("link_embed"),s.get("url")]
    return [v for v in vals if v]

bad=[r for r in a.get("results",[]) if not r.get("ok")]
kind=collections.Counter(r.get("kind") for r in bad)
reasons=collections.Counter()
source_hosts=collections.Counter()
source_shapes=collections.Counter()
examples=collections.defaultdict(list)

for r in bad:
    reasons[r.get("reason") or ("series_episode_failures" if r.get("failedEpisodes") else "empty_stream")]+=1
    x=by.get(str(r.get("url","")).rstrip("/")) or {}
    srcs=collect_sources(x)
    if not srcs:
        source_shapes["no_cached_source"]+=1
    for u in srcs:
        h=host(u); source_hosts[h or "(none)"]+=1
        lu=str(u).lower()
        if "streamvsmov.com/video/" in lu: k="streamvsmov_video"
        elif "streamvsmov.com/embed/" in lu: k="streamvsmov_embed"
        elif "streamvsmov.com/stream/" in lu and ".m3u8" in lu: k="streamvsmov_hls"
        elif ".m3u8" in lu: k="direct_m3u8"
        elif "/xem-phim/" in lu: k="rophim_watch"
        elif "/video/" in lu or "/embed/" in lu: k="other_player"
        else: k="other_url"
        source_shapes[k]+=1
        if len(examples[k])<8: examples[k].append({"title":r.get("title"),"url":u})

# Poster families with 2+ seasons and duplicate poster URL
fams=collections.defaultdict(list)
for x in movies:
    title=x.get("title") or ""
    if re.search(r"(?i)(?:phần|season)\s*\d+",title):
        fams[family_key(title)].append(x)
dup=[]
for k,rows in fams.items():
    if len(rows)<2: continue
    posters=[str(x.get("poster") or "") for x in rows]
    non=[p for p in posters if p]
    if len(non)>=2 and len(set(non))<len(non):
        dup.append({
            "family":k,
            "count":len(rows),
            "uniquePosters":len(set(non)),
            "seasons":[{"title":x.get("title"),"url":x.get("url"),"poster":x.get("poster")} for x in rows]
        })

out={
    "audit":{"checkedTitles":a.get("checkedTitles"),"failedTitles":a.get("failedTitles"),"failedSeriesEpisodes":a.get("failedSeriesEpisodes")},
    "remainingByKind":dict(kind),
    "remainingReasons":reasons.most_common(),
    "sourceHosts":source_hosts.most_common(30),
    "sourceShapes":source_shapes.most_common(),
    "sourceExamples":examples,
    "duplicatePosterFamilies":len(dup),
    "duplicatePosterExamples":dup[:80]
}
json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({
    "audit":out["audit"],
    "remainingByKind":out["remainingByKind"],
    "topShapes":out["sourceShapes"][:10],
    "duplicatePosterFamilies":out["duplicatePosterFamilies"]
},ensure_ascii=False))
