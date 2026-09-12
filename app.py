import json, os, base64
from flask import Flask, jsonify, request

CATALOG = os.environ.get("ROPHIM_CATALOG", "rophim_catalog.json")
app = Flask(__name__)

def load():
    with open(CATALOG, "r", encoding="utf-8") as f:
        return json.load(f)

def enc(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

def dec(s):
    try:
        s += "=" * ((4-len(s)%4)%4)
        return base64.urlsafe_b64decode(s.encode()).decode()
    except:
        return ""

def mid(item):
    return "rophim_" + enc(item.get("url",""))

def meta(item):
    typ = "series" if item.get("type")=="series" else "movie"
    m = {
        "id": mid(item),
        "type": typ,
        "name": item.get("title") or item.get("slug") or "RoPhim",
        "poster": item.get("poster") or None,
        "background": item.get("backdrop") or None,
        "description": item.get("description") or "",
        "website": item.get("url"),
        "posterShape": "poster"
    }
    if item.get("year"):
        m["releaseInfo"] = str(item["year"])
    if item.get("genres"):
        m["genres"] = item["genres"]
    if item.get("duration"):
        m["runtime"] = item["duration"]
    return m

MANIFEST = {
    "id":"community.rophim.catalog",
    "version":"0.1.0",
    "name":"RoPhim Catalog",
    "description":"Catalog/metadata index built from rophim_catalog.json",
    "resources":["catalog","meta"],
    "types":["movie","series"],
    "idPrefixes":["rophim_"],
    "catalogs":[
        {"type":"movie","id":"rophim_movies","name":"🎬 RoPhim • Movies",
         "extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},
        {"type":"series","id":"rophim_series","name":"📺 RoPhim • Series",
         "extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]}
    ]
}

@app.get("/")
def root():
    return jsonify({"ok":True,"service":"rophim-addon","manifest":"/manifest.json"})

@app.get("/health")
def health():
    return jsonify({"ok":True})

@app.get("/manifest.json")
def manifest():
    return jsonify(MANIFEST)

def catalog(typ):
    d=load()
    q=(request.args.get("search") or "").lower().strip()
    try:
        skip=max(0,int(request.args.get("skip") or 0))
    except:
        skip=0
    items=[]
    for x in d.get("movies",[]):
        xt="series" if x.get("type")=="series" else "movie"
        if xt!=typ:
            continue
        m=meta(x)
        if q and q not in (m.get("name","")+" "+m.get("description","")).lower():
            continue
        items.append(m)
    return jsonify({"metas":items[skip:skip+100]})

@app.get("/catalog/movie/rophim_movies.json")
def movies():
    return catalog("movie")

@app.get("/catalog/series/rophim_series.json")
def series():
    return catalog("series")

@app.get("/meta/<typ>/<path:item_id>.json")
def get_meta(typ,item_id):
    if not item_id.startswith("rophim_"):
        return jsonify({"meta":None})
    url=dec(item_id[len("rophim_"):])
    for x in load().get("movies",[]):
        if x.get("url")==url:
            return jsonify({"meta":meta(x)})
    return jsonify({"meta":None})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
