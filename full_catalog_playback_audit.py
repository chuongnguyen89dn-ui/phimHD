import os, json, time, traceback

CATALOG=os.environ.get("ROPHIM_CATALOG","rophim_catalog.json")
OUT=os.environ.get("IVY_FULL_AUDIT_OUT","full_playback_audit_part.json")
SHARD=int(os.environ.get("IVY_AUDIT_SHARD_INDEX","0"))
SHARDS=max(1,int(os.environ.get("IVY_AUDIT_SHARD_TOTAL","1")))

# Force app_full to use the downloaded catalog snapshot and avoid production Render.
os.environ["IVY_CATALOG"]=CATALOG
os.environ["ROPHIM_CATALOG"]=CATALOG
os.environ["IVY_REMOTE_CATALOG"]="http://127.0.0.1:9/disabled"

import app_full as core

def load_catalog():
    with open(CATALOG,encoding="utf-8") as f:
        d=json.load(f)
    core._catalog_cache.update(at=time.time(),data=d)
    return d

def resp_json(resp):
    try:return resp.get_json(silent=True) or {}
    except:return {}

def audit_movie(x):
    iid=core.mid(x)
    with core.app.app_context():
        r=core.stream("movie",iid)
        data=resp_json(r)
    streams=data.get("streams") or []
    return {
        "kind":"movie","title":x.get("title"),"url":x.get("url"),
        "id":iid,"ok":bool(streams),"streamCount":len(streams),
        "streams":[s.get("url") for s in streams[:4] if isinstance(s,dict)]
    }

def audit_series(x):
    iid=core.mid(x)
    out={
        "kind":"series","title":x.get("title"),"url":x.get("url"),"id":iid,
        "ok":True,"videos":0,"failedEpisodes":[],"resolvedEpisodes":0
    }
    try:
        with core.app.app_context():
            meta=core.base_meta(x,True)
        videos=meta.get("videos") or []
        out["videos"]=len(videos)
        if not videos:
            out["ok"]=False
            out["reason"]="no_videos_discovered"
            return out
        for v in videos:
            vid=v.get("id")
            if not vid:continue
            try:
                with core.app.app_context():
                    r=core.stream("series",vid)
                    data=resp_json(r)
                streams=data.get("streams") or []
                if streams:
                    out["resolvedEpisodes"]+=1
                else:
                    out["ok"]=False
                    out["failedEpisodes"].append({
                        "videoId":vid,"season":v.get("season"),"episode":v.get("episode"),
                        "title":v.get("title"),"reason":"empty_stream"
                    })
            except Exception as e:
                out["ok"]=False
                out["failedEpisodes"].append({
                    "videoId":vid,"season":v.get("season"),"episode":v.get("episode"),
                    "title":v.get("title"),"reason":"exception","error":repr(e)
                })
        return out
    except Exception as e:
        out["ok"]=False
        out["reason"]="meta_exception"
        out["error"]=repr(e)
        return out

def main():
    d=load_catalog()
    movies=[x for x in (d.get("movies") or []) if isinstance(x,dict) and x.get("url")]
    subset=[x for i,x in enumerate(movies) if i%SHARDS==SHARD]
    print(f"FULL_AUDIT shard={SHARD}/{SHARDS} catalog={len(movies)} subset={len(subset)}",flush=True)
    results=[];bad=0
    for n,x in enumerate(subset,1):
        started=time.time()
        try:
            r=audit_series(x) if core.typ(x)=="series" else audit_movie(x)
        except Exception as e:
            r={"kind":core.typ(x),"title":x.get("title"),"url":x.get("url"),"ok":False,"reason":"audit_exception","error":repr(e)}
        r["elapsedSec"]=round(time.time()-started,2)
        results.append(r)
        if not r.get("ok"): bad+=1
        if not r.get("ok") or n%25==0:
            print(f"[{n}/{len(subset)}] {'OK' if r.get('ok') else 'FAIL'} {r.get('title','')} {r.get('elapsedSec')}s",flush=True)
    out={
        "generatedAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "shardIndex":SHARD,"shardTotal":SHARDS,
        "catalogTotal":len(movies),"checkedTitles":len(results),
        "failedTitles":bad,
        "results":results
    }
    with open(OUT,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print("FULL_AUDIT_DONE",json.dumps({k:out[k] for k in ("shardIndex","checkedTitles","failedTitles")}),flush=True)

if __name__=="__main__":
    main()
