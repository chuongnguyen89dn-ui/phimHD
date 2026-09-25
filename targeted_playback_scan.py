import os, re, json, base64, time, html, unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

CATALOG=os.environ.get("ROPHIM_CATALOG","rophim_catalog.json")
ADDON=os.environ.get("IVY_ADDON_BASE","https://phimhd.onrender.com").rstrip("/")
OUT=os.environ.get("IVY_TARGETED_REPORT","targeted_playback_report.json")
WORKERS=max(1,int(os.environ.get("IVY_TARGETED_WORKERS","32")))
TIMEOUT=max(3,int(os.environ.get("IVY_TARGETED_TIMEOUT","12")))
VALIDATE_HLS=os.environ.get("IVY_VALIDATE_HLS","1").lower() not in ("0","false","no")
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"

def clean(s):
    s=html.unescape(str(s or ""))
    return re.sub(r"\s+"," ",s).strip()

def norm(s):
    s=unicodedata.normalize("NFKD",str(s or ""))
    s="".join(c for c in s if not unicodedata.combining(c)).lower()
    s=re.sub(r"\([^)]*(?:19|20)\d{2}[^)]*\)"," ",s)
    s=re.sub(r"\b(?:phan|season)\s*\d+\b"," ",s)
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())

def typ(x):
    text=" ".join([str(x.get("title","")),str(x.get("duration",""))]+((x.get("taxonomy") or {}).get("sections") or [])+((x.get("taxonomy") or {}).get("genres") or [])).lower()
    return "series" if x.get("type")=="series" or any(k in text for k in ["phim bộ","tv shows","/tập","m/tập","season ","phần "]) else "movie"

def series_key(x):
    s=clean(x.get("title") or x.get("slug") or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")

def mid(x):
    raw=str(x.get("url") or "").encode()
    return "ivy_"+base64.urlsafe_b64encode(raw).decode().rstrip("=")

def get_json(url):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urlopen(req,timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def proxy_headers(stream):
    try:
        return (((stream.get("behaviorHints") or {}).get("proxyHeaders") or {}).get("request") or {})
    except Exception:
        return {}

def validate_hls(stream):
    u=str(stream.get("url") or "")
    if not u:
        return False,"empty_url"
    if not VALIDATE_HLS:
        return True,"not_checked"
    headers={"User-Agent":UA,"Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,*/*"}
    headers.update(proxy_headers(stream))
    try:
        req=Request(u,headers=headers)
        with urlopen(req,timeout=TIMEOUT) as r:
            body=r.read(2048)
            status=getattr(r,"status",200)
        if status>=400:
            return False,f"http_{status}"
        text=body.decode("utf-8","replace")
        if ".m3u8" in u.lower() and "#EXTM3U" not in text:
            return False,"not_hls"
        return True,"ok"
    except HTTPError as e:
        return False,f"http_{e.code}"
    except Exception as e:
        return False,type(e).__name__

def movie_check(x):
    iid=mid(x)
    url=f"{ADDON}/stream/movie/{iid}.json"
    try:
        data=get_json(url); streams=data.get("streams") or []
    except Exception as e:
        return {"kind":"movie","title":x.get("title"),"url":x.get("url"),"id":iid,"status":"endpoint_error","error":repr(e)}
    if not streams:
        return {"kind":"movie","title":x.get("title"),"url":x.get("url"),"id":iid,"status":"no_stream","streamCount":0}
    checks=[]
    good=0
    for s in streams[:3]:
        ok,reason=validate_hls(s)
        checks.append({"url":s.get("url"),"ok":ok,"reason":reason})
        good+=1 if ok else 0
    if good==0:
        return {"kind":"movie","title":x.get("title"),"url":x.get("url"),"id":iid,"status":"dead_stream","streamCount":len(streams),"checks":checks}
    return None

def expected_episode_count(family):
    eps=set()
    for x in family:
        for s in ((x.get("playbackHints") or {}).get("episodeSources") or []):
            try:
                ep=int(s.get("episode") or 0)
                if ep: eps.add((x.get("url"),ep))
            except: pass
    return len(eps)

def series_check(family):
    rep=family[0]; iid=mid(rep)
    meta_url=f"{ADDON}/meta/series/{iid}.json"
    family_info=[{"title":x.get("title"),"url":x.get("url"),"poster":x.get("poster")} for x in family]
    posters=[str(x.get("poster") or "") for x in family if x.get("poster")]
    poster_duplicate=len(family)>1 and len(set(posters))<len(posters)
    expected=expected_episode_count(family)
    problems=[]
    try:
        meta=get_json(meta_url).get("meta") or {}
    except Exception as e:
        return {"kind":"series","title":rep.get("title"),"url":rep.get("url"),"id":iid,"status":"meta_error","error":repr(e),"family":family_info,"duplicatePoster":poster_duplicate}
    videos=meta.get("videos") or []
    if not videos:
        problems.append({"status":"no_videos"})
    if expected and len(videos)<expected:
        problems.append({"status":"missing_videos","expectedFromCatalogHints":expected,"metaVideos":len(videos)})
    bad=[]
    for v in videos:
        vid=v.get("id")
        if not vid: continue
        try:
            data=get_json(f"{ADDON}/stream/series/{vid}.json")
            streams=data.get("streams") or []
        except Exception as e:
            bad.append({"videoId":vid,"title":v.get("title"),"season":v.get("season"),"episode":v.get("episode"),"status":"endpoint_error","error":repr(e)})
            continue
        if not streams:
            bad.append({"videoId":vid,"title":v.get("title"),"season":v.get("season"),"episode":v.get("episode"),"status":"no_stream"})
            continue
        checks=[];good=0
        for s in streams[:3]:
            ok,reason=validate_hls(s); checks.append({"url":s.get("url"),"ok":ok,"reason":reason});good+=1 if ok else 0
        if good==0:
            bad.append({"videoId":vid,"title":v.get("title"),"season":v.get("season"),"episode":v.get("episode"),"status":"dead_stream","checks":checks})
    if bad: problems.append({"status":"bad_episodes","count":len(bad),"items":bad})
    if problems or poster_duplicate:
        return {"kind":"series","title":rep.get("title"),"url":rep.get("url"),"id":iid,"status":"suspect" if problems else "poster_only","metaVideos":len(videos),"expectedFromCatalogHints":expected,"problems":problems,"duplicatePoster":poster_duplicate,"family":family_info}
    return None

def main():
    with open(CATALOG,encoding="utf-8") as f:d=json.load(f)
    movies=[x for x in (d.get("movies") or []) if isinstance(x,dict) and x.get("url")]
    films=[x for x in movies if typ(x)=="movie"]
    groups=defaultdict(list)
    for x in movies:
        if typ(x)=="series": groups[series_key(x)].append(x)
    jobs=[]
    for x in films: jobs.append(("movie",x))
    for fam in groups.values(): jobs.append(("series",fam))
    print(f"TARGETED_SCAN jobs={len(jobs)} movies={len(films)} seriesFamilies={len(groups)} workers={WORKERS} validateHls={VALIDATE_HLS}",flush=True)
    suspects=[];done=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs=[]
        for kind,payload in jobs:
            futs.append(ex.submit(movie_check,payload) if kind=="movie" else ex.submit(series_check,payload))
        for fut in as_completed(futs):
            done+=1
            try:r=fut.result()
            except Exception as e:r={"kind":"unknown","status":"checker_error","error":repr(e)}
            if r:
                suspects.append(r)
                print(f"[{done}/{len(jobs)}] SUSPECT {r.get('kind')} {r.get('status')} {r.get('title','')}",flush=True)
            elif done%100==0:
                print(f"[{done}/{len(jobs)}] ok",flush=True)
    playback=[x for x in suspects if x.get("status")!="poster_only" and (x.get("problems") or x.get("status") not in ("poster_only",))]
    poster=[x for x in suspects if x.get("duplicatePoster")]
    bad_eps=sum(sum(1 for p in x.get("problems",[]) if p.get("status")=="bad_episodes" for _ in p.get("items",[])) for x in suspects)
    out={
        "generatedAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "addon":ADDON,
        "catalogMovies":len(movies),
        "movieJobs":len(films),
        "seriesFamilies":len(groups),
        "checkedJobs":len(jobs),
        "suspectJobs":len(suspects),
        "playbackSuspectJobs":len(playback),
        "badSeriesEpisodes":bad_eps,
        "duplicatePosterFamilies":len(poster),
        "browserCandidates":[x for x in suspects if x.get("status")!="poster_only"],
        "posterDuplicates":poster
    }
    with open(OUT,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print("TARGETED_SCAN_DONE",json.dumps({k:out[k] for k in ("checkedJobs","suspectJobs","playbackSuspectJobs","badSeriesEpisodes","duplicatePosterFamilies")},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
