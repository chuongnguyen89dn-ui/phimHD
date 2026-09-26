import os,json,time
os.environ["IVY_CATALOG"]="rophim_catalog.json"; os.environ["ROPHIM_CATALOG"]="rophim_catalog.json"; os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"
import app_full as core
d=json.load(open("rophim_catalog.json",encoding="utf-8")); core._catalog_cache.update(at=time.time(),data=d)
targets=[
"https://rophims.team/phim/sat-thu-john-wick-phan-4",
"https://rophims.team/phim/wicked-phan-2",
"https://rophims.team/phim/mouse-ke-san-nguoi-ban-dien-anh",
"https://rophims.team/phim/wicked-phan-2-178974807758772",
"https://rophims.team/phim/lam-cha-me-phan-2",
"https://rophims.team/phim/rebel-moon-phan-mot-nguoi-con-cua-lua",
]
by={x.get("url"):x for x in d.get("movies",[]) if isinstance(x,dict)}
for u in targets:
    x=by.get(u); print("\nTITLE",x.get("title") if x else u)
    if not x: continue
    h=x.get("playbackHints") or {}; print("TYPE",core.typ(x)); print("HINTS",json.dumps(h,ensure_ascii=False)[:8000])
    vals=[]
    vals += h.get("direct") or []
    for e in h.get("episodeSources") or []:
        if isinstance(e,dict): vals += [v for v in (e.get("link_m3u8"),e.get("link_embed"),e.get("url")) if v]
    for v in dict.fromkeys(vals):
        try: print("RESOLVE",v,"=>",core.resolve_media_url(v,x.get("url")))
        except Exception as e: print("ERR",v,repr(e))
    iid=core.mid(x)
    with core.app.app_context():
        if core.typ(x)=="series":
            m=core.base_meta(x,True)
            vids=(m.get("videos") or [])
            print("VIDEOS",len(vids),vids[:2])
            if vids:
                target_season=core.infer_season(x)
                vv=next((v for v in vids if v.get("season")==target_season),vids[0])
                print("TARGET_VIDEO",vv)
                rr=core.stream("series",vv["id"]).get_json()
            else: rr={"streams":[]}
        else: rr=core.stream("movie",iid).get_json()
        print("STREAM",json.dumps(rr,ensure_ascii=False)[:6000])
