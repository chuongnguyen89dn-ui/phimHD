import os,json,time
os.environ["IVY_CATALOG"]="rophim_catalog.json"
os.environ["ROPHIM_CATALOG"]="rophim_catalog.json"
os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"
import app_full as core

d=json.load(open("rophim_catalog.json",encoding="utf-8"))
core._catalog_cache.update(at=time.time(),data=d)
title="100 nỗi sợ của tôi"
x=next(x for x in d.get("movies",[]) if title.lower() in (x.get("title") or "").lower())
print("TITLE",x.get("title"))
print("URL",x.get("url"))
print("TYPE",core.typ(x))
print("HINTS",json.dumps(x.get("playbackHints"),ensure_ascii=False)[:12000])
for src in (x.get("playbackHints") or {}).get("direct",[]) + [v for e in ((x.get("playbackHints") or {}).get("episodeSources") or []) if isinstance(e,dict) for v in [e.get("link_m3u8"),e.get("link_embed"),e.get("url")] if v]:
    try:
        print("SRC",src)
        print("RES",core.resolve_media_url(src,x.get("url")))
    except Exception as e:
        print("ERR",src,repr(e))
iid=core.mid(x)
with core.app.app_context():
    r=core.stream("series" if core.typ(x)=="series" else "movie",iid)
    print("STREAM",r.get_json(silent=True))
