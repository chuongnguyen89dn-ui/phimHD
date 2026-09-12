import json, os, base64
from flask import Flask, jsonify, request

CATALOG=os.environ.get("IVY_CATALOG",os.environ.get("ROPHIM_CATALOG","rophim_catalog.json"))
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
def clean_title(s):
 for marker in (" - Xem "," | RoPhim"," | Rổ Phim"):
  if marker in s:s=s.split(marker)[0]
 return s.strip()
def meta(x):
 typ="series" if x.get("type")=="series" or "Phim Bộ" in x.get("taxonomy",{}).get("sections",[]) else "movie"
 m={"id":mid(x),"type":typ,"name":clean_title(x.get("title") or x.get("slug") or "Ivy❤️"),"poster":x.get("poster") or None,"background":x.get("backdrop") or None,"description":x.get("description") or "","website":x.get("url"),"posterShape":"poster"}
 if x.get("year"):m["releaseInfo"]=str(x["year"])
 gs=x.get("taxonomy",{}).get("genres") or x.get("genres") or []
 if gs:m["genres"]=gs
 if x.get("duration"):m["runtime"]=x["duration"]
 return m

MANIFEST={"id":"community.ivy.catalog","version":"0.5.0","name":"Ivy❤️","description":"Ivy❤️ • Movies, Series, genres and countries","resources":["catalog","meta","stream"],"types":["movie","series"],"idPrefixes":["ivy_"],"catalogs":[{"type":"movie","id":"ivy_movies","name":"❤️ Ivy • Phim Lẻ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},{"type":"series","id":"ivy_series","name":"❤️ Ivy • Phim Bộ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]}]}
@app.get("/")
def root():return jsonify({"ok":True,"service":"Ivy❤️","manifest":"/manifest.json","version":MANIFEST["version"]})
@app.get("/health")
def health():
 d=load();return jsonify({"ok":True,"service":"Ivy❤️","version":MANIFEST["version"],"movies":len(d.get("movies",[])),"generatedAt":d.get("generatedAt")})
@app.get("/manifest.json")
def manifest():return jsonify(MANIFEST)
def catalog(typ):
 q=(request.args.get("search") or "").lower().strip()
 try:skip=max(0,int(request.args.get("skip") or 0))
 except:skip=0
 out=[]
 for x in load().get("movies",[]):
  m=meta(x)
  if m["type"]!=typ:continue
  if q and q not in (m.get("name","")+" "+m.get("description","")).lower():continue
  out.append(m)
 return jsonify({"metas":out[skip:skip+100]})
@app.get("/catalog/movie/ivy_movies.json")
def movies():return catalog("movie")
@app.get("/catalog/series/ivy_series.json")
def series():return catalog("series")
@app.get("/meta/<typ>/<path:item_id>.json")
def get_meta(typ,item_id):
 if not item_id.startswith("ivy_"):return jsonify({"meta":None})
 u=dec(item_id[4:])
 for x in load().get("movies",[]):
  if x.get("url")==u:return jsonify({"meta":meta(x)})
 return jsonify({"meta":None})
@app.get("/stream/<typ>/<path:item_id>.json")
def stream(typ,item_id):return jsonify({"streams":[]})
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
