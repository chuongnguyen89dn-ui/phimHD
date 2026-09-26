import json,collections
AUD="full_playback_audit.json"
OLD="browser_full_verification.json"
CAT="rophim_catalog.json"
a=json.load(open(AUD,encoding="utf-8"))
b=json.load(open(OLD,encoding="utf-8"))
c=json.load(open(CAT,encoding="utf-8"))
confirmed={str(x.get("url","")).rstrip("/") for x in b.get("confirmedResolverBugs",[])}
by={str(x.get("url","")).rstrip("/"):x for x in c.get("movies",[]) if isinstance(x,dict)}
cnt=collections.Counter(); samples=collections.defaultdict(list)
for r in a.get("results",[]):
    if r.get("ok"): continue
    u=str(r.get("url","")).rstrip("/")
    if u not in confirmed: continue
    x=by.get(u) or {}; h=x.get("playbackHints") or {}
    urls=list(h.get("direct") or [])
    for e in h.get("episodeSources") or []:
        if isinstance(e,dict):
            urls += [v for v in (e.get("link_m3u8"),e.get("link_embed"),e.get("url")) if v]
    lu=[str(v).lower() for v in urls]
    if any("streamc.xyz" in v for v in lu): k="streamc"
    elif any("streamvsmov.com/video/" in v or "streamvsmov.com/embed/" in v for v in lu): k="streamvsmov"
    elif any("rophims.team/xem-phim/" in v for v in lu): k="rophim_watch_only"
    else: k="other"
    cnt[k]+=1
    if len(samples[k])<15:samples[k].append({"title":r.get("title"),"url":r.get("url")})
out={"oldBrowserChecked":b.get("checked"),"oldConfirmed":b.get("webPlayableAddonFailed"),"currentConfirmedResidualTotal":sum(cnt.values()),"groups":dict(cnt),"samples":samples}
json.dump(out,open("current_confirmed_residual.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False))
