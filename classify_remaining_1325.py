import json,urllib.parse,collections,os
AUD="full_playback_audit.json"
CAT="rophim_catalog.json"
a=json.load(open(AUD,encoding="utf-8"))
c=json.load(open(CAT,encoding="utf-8"))
by={str(x.get("url","")).rstrip("/"):x for x in c.get("movies",[]) if isinstance(x,dict)}
bad=[r for r in a.get("results",[]) if not r.get("ok")]
out=collections.Counter(); samples=collections.defaultdict(list)

def classify(x):
    h=x.get("playbackHints") or {}
    urls=[]
    urls += [u for u in (h.get("direct") or []) if u]
    for e in (h.get("episodeSources") or []):
        if isinstance(e,dict):
            urls += [u for u in [e.get("link_m3u8"),e.get("link_embed"),e.get("url")] if u]
    lu=[str(u).lower() for u in urls]
    if any("streamc.xyz" in u for u in lu): return "streamc"
    if any("streamvsmov.com/video/" in u or "streamvsmov.com/embed/" in u for u in lu): return "streamvsmov"
    if any(".m3u8" in u for u in lu): return "direct_m3u8"
    if any("rophims.team/xem-phim/" in u for u in lu): return "rophim_watch_only"
    if urls: return "other_player"
    return "no_cached_source"

for r in bad:
    x=by.get(str(r.get("url","")).rstrip("/")) or {}
    k=classify(x); out[k]+=1
    if len(samples[k])<20:samples[k].append({"title":r.get("title"),"url":r.get("url")})
res={"failedTitles":len(bad),"groups":dict(out),"samples":samples}
json.dump(res,open("remaining_1325_groups.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(res["groups"],ensure_ascii=False))
