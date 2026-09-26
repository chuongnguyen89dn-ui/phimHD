import os,json,time
os.environ["IVY_CATALOG"]="rophim_catalog.json"
os.environ["ROPHIM_CATALOG"]="rophim_catalog.json"
os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"
import app_full as core

d=json.load(open("rophim_catalog.json",encoding="utf-8"))
core._catalog_cache.update(at=time.time(),data=d)
x=next(x for x in d.get("movies",[]) if "Giới Quý Tộc" in (x.get("title") or ""))
iid=core.mid(x)
with core.app.app_context():
    data=core.stream("movie",iid).get_json()
assert data.get("streams"), data
print("ROPHIM_WATCH_RESOLVER_PASS",data["streams"][0]["url"])
