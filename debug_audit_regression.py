import os,json,time
os.environ["IVY_CATALOG"]="rophim_catalog.json"
os.environ["ROPHIM_CATALOG"]="rophim_catalog.json"
os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"
import app_full as core

d=json.load(open("rophim_catalog.json",encoding="utf-8"))
core._catalog_cache.update(at=time.time(),data=d)
rows=[x for x in d.get("movies",[]) if isinstance(x,dict) and x.get("url")]
for x in rows[:5]:
    iid=core.mid(x)
    decoded=core.dec(iid[4:])
    found=next((y for y in core.load().get("movies",[]) if y.get("url")==decoded),None)
    print("TITLE",x.get("title"))
    print("URL",x.get("url"))
    print("IID",iid[:100],"DECODED",decoded,"FOUND",bool(found),"TYPE",core.typ(x))
    with core.app.app_context():
        r=core.stream("series" if core.typ(x)=="series" else "movie",iid)
        try: data=r.get_json()
        except Exception as e: data={"json_error":repr(e),"repr":repr(r)}
    print("RESULT",json.dumps(data,ensure_ascii=False)[:1000])
