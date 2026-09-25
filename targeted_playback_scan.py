import os, re, json, time, html, unicodedata
from collections import defaultdict

CATALOG=os.environ.get("ROPHIM_CATALOG","rophim_catalog.json")
OUT=os.environ.get("IVY_TARGETED_REPORT","targeted_playback_report.json")

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(str(s or ""))).strip()

def typ(x):
    text=" ".join([str(x.get("title","")),str(x.get("duration",""))]+((x.get("taxonomy") or {}).get("sections") or [])+((x.get("taxonomy") or {}).get("genres") or [])).lower()
    return "series" if x.get("type")=="series" or any(k in text for k in ["phim bộ","tv shows","/tập","m/tập","season ","phần "]) else "movie"

def series_key(x):
    s=clean(x.get("title") or x.get("slug") or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")

def source_rows(x):
    h=x.get("playbackHints") or {}
    rows=h.get("episodeSources") or []
    direct=h.get("direct") or []
    return h,rows,direct

def valid_url(v):
    return isinstance(v,str) and v.startswith(("http://","https://"))

def analyze_movie(x):
    h,rows,direct=source_rows(x)
    urls=[]
    urls += [u for u in direct if valid_url(u)]
    for r in rows:
        if not isinstance(r,dict): continue
        for k in ("link_m3u8","link_embed","url"):
            u=r.get(k)
            if valid_url(u): urls.append(u); break
    if not urls:
        return {
            "kind":"movie","title":x.get("title"),"url":x.get("url"),
            "reason":"no_cached_playback_source"
        }
    return None

def analyze_series_family(fam):
    bad=[]
    all_eps=defaultdict(list)
    for x in fam:
        h,rows,direct=source_rows(x)
        if not rows:
            bad.append({"title":x.get("title"),"url":x.get("url"),"reason":"no_episode_sources"})
            continue
        for r in rows:
            if not isinstance(r,dict): continue
            ep=r.get("episode")
            u=r.get("link_m3u8") or r.get("link_embed") or r.get("url")
            if not ep or not valid_url(u):
                bad.append({"title":x.get("title"),"url":x.get("url"),"episode":ep,"reason":"episode_missing_url"})
            else:
                all_eps[(x.get("url"),int(ep))].append(u)
    posters=[str(x.get("poster") or "") for x in fam if x.get("poster")]
    dup=len(fam)>1 and len(posters)>1 and len(set(posters))<len(posters)
    out=None
    if bad:
        out={
            "kind":"series","title":fam[0].get("title"),"url":fam[0].get("url"),
            "reason":"series_structure_issue","issues":bad,"family":[
                {"title":x.get("title"),"url":x.get("url"),"poster":x.get("poster")} for x in fam
            ]
        }
    return out,dup

def main():
    with open(CATALOG,encoding="utf-8") as f:d=json.load(f)
    movies=[x for x in (d.get("movies") or []) if isinstance(x,dict) and x.get("url")]
    films=[x for x in movies if typ(x)=="movie"]
    groups=defaultdict(list)
    for x in movies:
        if typ(x)=="series": groups[series_key(x)].append(x)

    playback=[]
    for x in films:
        r=analyze_movie(x)
        if r: playback.append(r)

    poster_dups=[]
    for fam in groups.values():
        r,dup=analyze_series_family(fam)
        if r: playback.append(r)
        if dup:
            poster_dups.append({
                "title":fam[0].get("title"),
                "family":[{"title":x.get("title"),"url":x.get("url"),"poster":x.get("poster")} for x in fam]
            })

    out={
        "generatedAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "mode":"local_catalog_shortlist_no_production_hammering",
        "catalogMovies":len(movies),
        "movieItems":len(films),
        "seriesFamilies":len(groups),
        "playbackCandidates":len(playback),
        "duplicatePosterFamilies":len(poster_dups),
        "browserCandidates":playback,
        "posterDuplicates":poster_dups,
        "note":"Candidates are structural/cached-source anomalies only. Browser verification should run only on these candidates."
    }
    with open(OUT,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print("TARGETED_LOCAL_SCAN",json.dumps({k:out[k] for k in ("catalogMovies","movieItems","seriesFamilies","playbackCandidates","duplicatePosterFamilies")},ensure_ascii=False))

if __name__=="__main__":
    main()
