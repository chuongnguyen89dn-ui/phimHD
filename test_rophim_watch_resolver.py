import os,json,time
os.environ["IVY_CATALOG"]="rophim_catalog.json"
os.environ["ROPHIM_CATALOG"]="rophim_catalog.json"
os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"
import app_full as core

d=json.load(open("rophim_catalog.json",encoding="utf-8"))
core._catalog_cache.update(at=time.time(),data=d)
x=next(x for x in d.get("movies",[]) if (x.get("url") or "")=="https://rophims.team/phim/wicked-phan-2")
watch=(x.get("playbackHints") or {}).get("watchUrl")
pairs=core.resolve_media_url(watch,x.get("url"))
assert pairs, (watch,pairs)
assert "streamvsmov.com/stream/" in pairs[0][0] or "streamc.xyz" in pairs[0][0], pairs
print("ROPHIM_WATCH_RESOLVER_PASS",pairs[0][0])
