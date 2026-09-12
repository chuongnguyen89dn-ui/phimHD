import json, os, base64, re
from urllib.parse import unquote
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request

CATALOG=os.environ.get("IVY_CATALOG",os.environ.get("ROPHIM_CATALOG","rophim_catalog.json"))
SOURCE_BASE=os.environ.get("IVY_SOURCE_BASE","https://rophim.loan").rstrip('/')
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
app=Flask(__name__)

def load():
    try:
        with open(CATALOG,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return {"movies":[]}

def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
def dec(s):
    try:
        s+="="*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
    except:return ""
def mid(x):return "ivy_"+enc(x.get("url",""))

def visible_text(s):
    s=str(s or "")
    s=re.sub(r"(?i)r[oổ]phim", "Ivy❤️", s)
    return s

def clean_title(s):
    s=visible_text(s)
    for marker in (" - Xem "," | Ivy❤️"):
        if marker in s:s=s.split(marker)[0]
    return s.strip()

def taxonomy(x,key):
    t=x.get("taxonomy") or {}
    return t.get(key) or x.get(key) or []

def item_type(x):
    secs=taxonomy(x,"sections")
    return "series" if x.get("type")=="series" or "Phim Bộ" in secs or "TV Shows" in secs else "movie"

def meta(x):
    typ=item_type(x)
    m={"id":mid(x),"type":typ,"name":clean_title(x.get("title") or x.get("slug") or "Ivy❤️"),"poster":x.get("poster") or None,"background":x.get("backdrop") or None,"description":visible_text(x.get("description") or ""),"website":x.get("url"),"posterShape":"poster"}
    if x.get("year"):m["releaseInfo"]=str(x["year"])
    gs=taxonomy(x,"genres") or x.get("genres") or []
    if gs:m["genres"]=gs
    if x.get("duration"):m["runtime"]=x["duration"]
    return m

def options(key):
    vals=set()
    for x in load().get("movies",[]):vals.update(taxonomy(x,key))
    return sorted(v for v in vals if v)

def manifest_data():
    genres=options("genres");countries=options("countries")
    return {"id":"community.ivy.catalog","version":"0.7.0","name":"Ivy❤️","description":"Ivy❤️ • Phim Lẻ, Phim Bộ, Thể loại và Quốc gia","resources":["catalog","meta","stream"],"types":["movie","series"],"idPrefixes":["ivy_"],"catalogs":[
      {"type":"movie","id":"ivy_movies","name":"❤️ Ivy • Phim Lẻ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},
      {"type":"series","id":"ivy_series","name":"❤️ Ivy • Phim Bộ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},
      {"type":"movie","id":"ivy_genres","name":"❤️ Ivy • Thể loại","extra":[{"name":"genre","isRequired":False,"options":genres},{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},
      {"type":"movie","id":"ivy_countries","name":"❤️ Ivy • Quốc gia","extra":[{"name":"country","isRequired":False,"options":countries},{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]}
    ]}

@app.get("/")
def root():return jsonify({"ok":True,"service":"Ivy❤️","manifest":"/manifest.json","version":manifest_data()["version"]})
@app.get("/health")
def health():
    d=load();return jsonify({"ok":True,"service":"Ivy❤️","version":manifest_data()["version"],"movies":len(d.get("movies",[])),"generatedAt":d.get("generatedAt"),"stats":d.get("stats",{})})
@app.get("/manifest.json")
def manifest():return jsonify(manifest_data())

def extras_from_path(extra=""):
    out={}
    for part in (extra or "").split("/"):
        if "=" in part:
            k,v=part.split("=",1);out[k]=unquote(v)
    for k in ("skip","search","genre","country"):
        if request.args.get(k) is not None:out[k]=request.args.get(k)
    return out

def catalog(typ,catalog_id,extra=""):
    ex=extras_from_path(extra);q=(ex.get("search") or "").lower().strip()
    try:skip=max(0,int(ex.get("skip") or 0))
    except:skip=0
    genre=ex.get("genre") or "";country=ex.get("country") or "";out=[]
    for x in load().get("movies",[]):
        m=meta(x)
        if catalog_id=="ivy_movies" and m["type"]!="movie":continue
        if catalog_id=="ivy_series" and m["type"]!="series":continue
        if catalog_id in ("ivy_genres","ivy_countries") and m["type"]!="movie":continue
        if genre and genre not in taxonomy(x,"genres"):continue
        if country and country not in taxonomy(x,"countries"):continue
        if q and q not in (m.get("name","")+" "+m.get("description","")).lower():continue
        out.append(m)
    return jsonify({"metas":out[skip:skip+100]})

@app.get("/catalog/<typ>/<catalog_id>.json")
def cat_plain(typ,catalog_id):return catalog(typ,catalog_id)
@app.get("/catalog/<typ>/<catalog_id>/<path:extra>.json")
def cat_extra(typ,catalog_id,extra):return catalog(typ,catalog_id,extra)

@app.get("/meta/<typ>/<path:item_id>.json")
def get_meta(typ,item_id):
    if not item_id.startswith("ivy_"):return jsonify({"meta":None})
    u=dec(item_id[4:])
    for x in load().get("movies",[]):
        if x.get("url")==u:return jsonify({"meta":meta(x)})
    return jsonify({"meta":None})

def choose_master(urls):
    urls=list(dict.fromkeys(urls))
    masters=[u for u in urls if "master.m3u8" in u.lower()]
    if masters:return sorted(masters,key=len)[0]
    indexes=[u for u in urls if u.lower().split('?')[0].endswith('/index.m3u8')]
    return sorted(indexes,key=len)[0] if indexes else (urls[0] if urls else "")

def resolve_http(source_url):
    try:
        req=Request(source_url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.8","Referer":SOURCE_BASE+"/"})
        with urlopen(req,timeout=15) as r:text=r.read().decode("utf-8","replace").replace("\\/","/")
        found=list(dict.fromkeys(HLS_RE.findall(text)))
        return choose_master(found),found
    except Exception:return "",[]

@app.get("/stream/<typ>/<path:item_id>.json")
def stream(typ,item_id):
    if not item_id.startswith("ivy_"):return jsonify({"streams":[]})
    source_url=dec(item_id[4:])
    if not source_url.startswith(SOURCE_BASE+"/"):return jsonify({"streams":[]})
    master,found=resolve_http(source_url)
    if not master:return jsonify({"streams":[]})
    streams=[{"name":"Ivy❤️","title":"Ivy❤️ • Auto HLS","url":master,"behaviorHints":{"notWebReady":True}}]
    # Additional playlists are kept as backups without duplicating the selected master.
    for i,u in enumerate(found[:8],1):
        if u==master:continue
        streams.append({"name":"Ivy❤️","title":f"Ivy❤️ • Backup {i}","url":u,"behaviorHints":{"notWebReady":True}})
    return jsonify({"streams":streams})

if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
