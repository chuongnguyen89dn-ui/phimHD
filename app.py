import json, os, base64, re, time
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from flask import Flask, jsonify, request

CATALOG=os.environ.get("IVY_CATALOG",os.environ.get("ROPHIM_CATALOG","rophim_catalog.json"))
SOURCE_BASE=os.environ.get("IVY_SOURCE_BASE","https://rophim.loan").rstrip('/')
SOURCE_HOME=os.environ.get("IVY_SOURCE_HOME",SOURCE_BASE+"/phimhay")
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
app=Flask(__name__)
_home_cache={"at":0,"sections":[]}

def load():
    try:
        with open(CATALOG,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return {"movies":[]}
def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
def dec(s):
    try:s+="="*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
    except:return ""
def mid(x):return "ivy_"+enc(x.get("url",""))
def visible_text(s):return re.sub(r"(?i)r[oổ]phim","Ivy❤️",str(s or ""))
def clean_title(s):
    s=visible_text(s)
    for marker in (" - Xem "," | Ivy❤️"):
        if marker in s:s=s.split(marker)[0]
    return s.strip()
def taxonomy(x,key):
    t=x.get("taxonomy") or {};return t.get(key) or x.get(key) or []
def item_type(x):
    secs=taxonomy(x,"sections")
    return "series" if x.get("type")=="series" or "Phim Bộ" in secs or "TV Shows" in secs else "movie"
def reliable_year(x):
    title=clean_title(x.get("title") or "")
    ys=[int(y) for y in re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)',title)]
    if ys:return ys[-1]
    y=x.get("year")
    # 2026 was widely injected by the old crawler from page/footer text; hide it unless title proves it.
    if isinstance(y,int) and 1900<=y<=2100 and y!=2026:return y
    if isinstance(y,str) and y.isdigit() and 1900<=int(y)<=2100 and int(y)!=2026:return int(y)
    return None
def meta(x):
    m={"id":mid(x),"type":item_type(x),"name":clean_title(x.get("title") or x.get("slug") or "Ivy❤️"),"poster":x.get("poster") or None,"background":x.get("backdrop") or None,"description":visible_text(x.get("description") or ""),"website":x.get("url"),"posterShape":"poster"}
    y=reliable_year(x)
    if y:m["releaseInfo"]=str(y)
    gs=taxonomy(x,"genres") or x.get("genres") or []
    if gs:m["genres"]=gs
    if x.get("duration"):m["runtime"]=x["duration"]
    return m

class HomeParser(HTMLParser):
    def __init__(self):
        super().__init__();self.sections=[];self.current={"name":"Mới cập nhật","urls":[]};self.in_h2=False;self.h2=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="h2":self.in_h2=True;self.h2=[]
        if tag=="a":
            href=a.get("href","")
            if "/phim/" in href:
                u=urljoin(SOURCE_BASE+"/",href).split('#')[0]
                if u not in self.current["urls"]:self.current["urls"].append(u)
    def handle_data(self,data):
        if self.in_h2:self.h2.append(data)
    def handle_endtag(self,tag):
        if tag=="h2" and self.in_h2:
            name=" ".join("".join(self.h2).split()).strip()
            if name:
                if self.current["urls"]:self.sections.append(self.current)
                self.current={"name":name,"urls":[]}
            self.in_h2=False
    def finish(self):
        if self.current["urls"]:self.sections.append(self.current)
        return self.sections

def homepage_sections():
    now=time.time()
    if _home_cache["sections"] and now-_home_cache["at"]<900:return _home_cache["sections"]
    try:
        req=Request(SOURCE_HOME,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.8"})
        with urlopen(req,timeout=15) as r:h=r.read().decode("utf-8","replace")
        p=HomeParser();p.feed(h);secs=p.finish()
        if secs:_home_cache.update({"at":now,"sections":secs})
    except Exception:pass
    return _home_cache["sections"]

def options(key):
    vals=set()
    for x in load().get("movies",[]):vals.update(taxonomy(x,key))
    return sorted(v for v in vals if v)
def manifest_data():
    genres=options("genres");countries=options("countries")
    cats=[{"type":"movie","id":"ivy_home","name":"❤️ Ivy • Mới cập nhật","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]}]
    cats += [{"type":"movie","id":"ivy_movies","name":"❤️ Ivy • Phim Lẻ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},{"type":"series","id":"ivy_series","name":"❤️ Ivy • Phim Bộ","extra":[{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]},{"type":"movie","id":"ivy_genres","name":"❤️ Ivy • Thể loại","extra":[{"name":"genre","isRequired":False,"options":genres},{"name":"skip","isRequired":False}]},{"type":"movie","id":"ivy_countries","name":"❤️ Ivy • Quốc gia","extra":[{"name":"country","isRequired":False,"options":countries},{"name":"skip","isRequired":False}]}]
    return {"id":"community.ivy.catalog","version":"0.8.0","name":"Ivy❤️","description":"Ivy❤️ • cập nhật theo giao diện nguồn","resources":["catalog","meta","stream"],"types":["movie","series"],"idPrefixes":["ivy_"],"catalogs":cats}

@app.get("/")
def root():return jsonify({"ok":True,"service":"Ivy❤️","manifest":"/manifest.json","version":manifest_data()["version"]})
@app.get("/health")
def health():
    d=load();return jsonify({"ok":True,"service":"Ivy❤️","version":manifest_data()["version"],"movies":len(d.get("movies",[])),"homeSections":[s["name"] for s in homepage_sections()],"generatedAt":d.get("generatedAt")})
@app.get("/manifest.json")
def manifest():return jsonify(manifest_data())

def extras(extra=""):
    out={}
    for part in (extra or "").split("/"):
        if "=" in part:
            k,v=part.split("=",1);out[k]=unquote(v)
    for k in ("skip","search","genre","country"):
        if request.args.get(k) is not None:out[k]=request.args.get(k)
    return out
def catalog(typ,cid,extra=""):
    ex=extras(extra);q=(ex.get("search") or "").lower().strip();genre=ex.get("genre") or "";country=ex.get("country") or ""
    try:skip=max(0,int(ex.get("skip") or 0))
    except:skip=0
    data=load().get("movies",[]);byurl={x.get("url"):x for x in data};ordered=[]
    if cid=="ivy_home":
        seen=set()
        for sec in homepage_sections():
            for u in sec["urls"]:
                if u in byurl and u not in seen:ordered.append(byurl[u]);seen.add(u)
        if not ordered:ordered=data
    else:ordered=data
    out=[]
    for x in ordered:
        m=meta(x)
        if cid=="ivy_movies" and m["type"]!="movie":continue
        if cid=="ivy_series" and m["type"]!="series":continue
        if genre and genre not in taxonomy(x,"genres"):continue
        if country and country not in taxonomy(x,"countries"):continue
        if q and q not in (m.get("name","")+" "+m.get("description","")).lower():continue
        out.append(m)
    return jsonify({"metas":out[skip:skip+100]})
@app.get("/catalog/<typ>/<cid>.json")
def cat_plain(typ,cid):return catalog(typ,cid)
@app.get("/catalog/<typ>/<cid>/<path:extra>.json")
def cat_extra(typ,cid,extra):return catalog(typ,cid,extra)
@app.get("/meta/<typ>/<path:item_id>.json")
def get_meta(typ,item_id):
    u=dec(item_id[4:]) if item_id.startswith("ivy_") else ""
    for x in load().get("movies",[]):
        if x.get("url")==u:return jsonify({"meta":meta(x)})
    return jsonify({"meta":None})

def resolve_http(source_url):
    try:
        req=Request(source_url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.8","Referer":SOURCE_BASE+"/"})
        with urlopen(req,timeout=15) as r:text=r.read().decode("utf-8","replace").replace("\\/","/")
        return list(dict.fromkeys(HLS_RE.findall(text)))
    except Exception:return []
@app.get("/stream/<typ>/<path:item_id>.json")
def stream(typ,item_id):
    if not item_id.startswith("ivy_"):return jsonify({"streams":[]})
    source_url=dec(item_id[4:]);found=resolve_http(source_url)
    if not found:return jsonify({"streams":[]})
    x=next((z for z in load().get("movies",[]) if z.get("url")==source_url),{})
    is_series=item_type(x)=="series"
    streams=[]
    for i,u in enumerate(found,1):
        title=f"Ivy❤️ • Tập {i}" if is_series else ("Ivy❤️ • Phát" if i==1 else f"Ivy❤️ • Nguồn {i}")
        streams.append({"name":"Ivy❤️","title":title,"url":u,"behaviorHints":{"notWebReady":True}})
    return jsonify({"streams":streams})
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
