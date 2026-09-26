import json, os, base64, re, time, html, unicodedata
from urllib.parse import unquote, urljoin, urlencode, urlparse
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request

CATALOG=os.environ.get("IVY_CATALOG", os.environ.get("ROPHIM_CATALOG","rophim_catalog.json"))
REMOTE_CATALOG=os.environ.get("IVY_REMOTE_CATALOG","https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/rophim_catalog.json")
BASE=os.environ.get("IVY_SOURCE_BASE","https://rophims.team").rstrip("/")
TMDB_API_KEY=os.environ.get("TMDB_API_KEY","").strip()
TMDB_API="https://api.themoviedb.org/3"; TMDB_IMG="https://image.tmdb.org/t/p/"
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
MEDIA_SRC_RE=re.compile(r'(?:src|file|source|url)\s*[:=]\s*["\']([^"\']+)["\']',re.I)
app=Flask(__name__)
_page_cache={}; _catalog_cache={"at":0,"data":None}; _tmdb_cache={}; _list_cache={}; _section_cache={"at":0,"data":{}}; _resolve_cache={}

def _local_catalog():
    try:
        with open(CATALOG,encoding="utf-8") as f:return json.load(f)
    except:return {"movies":[]}

def load():
    now=time.time()
    if _catalog_cache["data"] is not None and now-_catalog_cache["at"]<900:return _catalog_cache["data"]
    fallback=_catalog_cache["data"] or _local_catalog()
    try:
        req=Request(REMOTE_CATALOG+"?t="+str(int(now//900)),headers={"User-Agent":UA,"Accept":"application/json"})
        with urlopen(req,timeout=8) as r:data=json.loads(r.read().decode("utf-8"))
        if isinstance(data,dict) and len(data.get("movies",[]))>100:
            _catalog_cache.update(at=now,data=data);return data
    except:pass
    _catalog_cache.update(at=now,data=fallback);return fallback

def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
def dec(s):
    try:s+="="*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
    except:return ""
def mid(x):return "ivy_"+enc(x.get("url",""))
def clean(s):
    s=html.unescape(re.sub(r"(?i)r[oổ]phim","Ivy❤️",str(s or "")))
    return re.sub(r"\s+"," ",s).split(" - Xem ")[0].split(" | Ivy❤️")[0].strip()
def tax(x,k):return (x.get("taxonomy") or {}).get(k) or x.get(k) or []
def typ(x):
    text=" ".join([str(x.get("title","")),str(x.get("duration",""))]+tax(x,"sections")+tax(x,"genres")).lower()
    return "series" if x.get("type")=="series" or any(k in text for k in ["phim bộ","tv shows","/tập","m/tập","season ","phần "]) else "movie"
def year(x):
    ys=re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)",clean(x.get("title","")))
    if ys:return int(ys[-1])
    y=x.get("year"); y=int(y) if str(y).isdigit() else 0
    return y if 1900<=y<=2100 and y!=2026 else None
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "")); s="".join(c for c in s if not unicodedata.combining(c)).lower()
    s=re.sub(r"\([^)]*(?:19|20)\d{2}[^)]*\)"," ",s); s=re.sub(r"\b(?:phan|season)\s*\d+\b"," ",s)
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())

def fetch_text(u,ttl=300,referer=None):
    key=(u,referer or "");now=time.time(); c=_page_cache.get(key)
    if c and now-c[0]<ttl:return c[1]
    headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*;q=0.8","Accept-Language":"vi-VN,vi;q=0.9,en;q=0.8","Referer":referer or BASE+"/"}
    # RoPhim intermittently rejects datacenter urllib/TLS fingerprints while still
    # serving normal browsers. Prefer curl_cffi browser impersonation, then keep
    # urllib as a lightweight fallback.
    try:
        from curl_cffi import requests as curl_requests
        r=curl_requests.get(u,headers=headers,timeout=18,impersonate="chrome",allow_redirects=True)
        if r.status_code < 400 and r.text:
            s=r.text.replace("\\/","/")
            _page_cache[key]=(now,s);return s
        print("[fetch_text curl]",u,r.status_code,(r.url or "")[:180],flush=True)
    except Exception as e:
        print("[fetch_text curl]",u,type(e).__name__,str(e)[:180],flush=True)
    try:
        with urlopen(Request(u,headers=headers),timeout=18) as r:s=r.read().decode("utf-8","replace").replace("\\/","/")
        _page_cache[key]=(now,s);return s
    except Exception as e:
        print("[fetch_text urllib]",u,type(e).__name__,str(e)[:180],flush=True)
        return ""

def decode_js_escapes(s):
    s=str(s or "")
    # Decode common JavaScript string escapes used by StreamVSMov players.
    s=re.sub(r"\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),s)
    s=re.sub(r"\\u([0-9a-fA-F]{4})",lambda m:chr(int(m.group(1),16)),s)
    s=s.replace("\\/","/")
    return html.unescape(s)

def resolve_media_url(raw,referer=None,depth=0):
    raw=html.unescape(str(raw or "").replace("\\/","/")).strip()
    if not raw:return []
    u=urljoin(referer or BASE+"/",raw)
    if ".m3u8" in u.lower():return [(u,referer or BASE+"/")]

    # StreamC player pages use a bootstrap POST. Asking for playlist_format=hls
    # returns a preissued plain-HLS playlist URL, avoiding the browser-only
    # AES-GCM playlist path used by Chromium.
    if re.match(r"^https?://[^/]*streamc\.xyz/embed\.php\?",u,re.I):
        key=(u,referer or "");now=time.time();cached=_resolve_cache.get(key)
        if cached and now-cached[0]<300:return cached[1]
        try:
            from curl_cffi import requests as curl_requests
            pu=urlparse(u)
            ref=referer or BASE+"/"
            rp=urlparse(ref)
            frame_origin=(rp.scheme+"://"+rp.netloc) if rp.scheme and rp.netloc else BASE
            payload={
                "action":"bootstrap",
                "referrer":ref,
                "frame_origins":[frame_origin],
                "request_grant":True,
                "playlist_format":"hls",
                "pretty_url":True,
                "path_chunks":True,
            }
            headers={
                "User-Agent":UA,
                "Accept":"application/json,*/*",
                "Content-Type":"application/json",
                "Origin":pu.scheme+"://"+pu.netloc,
                "Referer":u,
            }
            r=curl_requests.post(u,headers=headers,json=payload,timeout=18,impersonate="chrome",allow_redirects=True)
            if r.status_code<400:
                d=r.json() if r.text else {}
                p=((d.get("preissued") or {}).get("playlist") if isinstance(d,dict) else None)
                if p:
                    out=[(html.unescape(str(p)),u)]
                    _resolve_cache[key]=(now,out)
                    return out
        except Exception as e:
            print("[streamc bootstrap]",u,type(e).__name__,str(e)[:180],flush=True)

    # StreamVSMov exposes stable player URLs as /video/<uuid> (and sometimes
    # /embed/<uuid>) while the actual HLS playlist lives at
    # /stream/<uuid>/master.m3u8. RoPhim stores the player URL in playbackHints,
    # so derive the playlist before fetching/parsing player JavaScript. This also
    # avoids datacenter/player-page blocking and fixes both movies and series.
    sm=re.match(r"^(https?://[^/]*streamvsmov\.com)/(?:video|embed)/([0-9a-f-]{16,})(?:[/?#].*)?$",u,re.I)
    if sm:
        hls=f"{sm.group(1)}/stream/{sm.group(2)}/master.m3u8"
        return [(hls,u)]

    key=(u,referer or "");now=time.time();c=_resolve_cache.get(key)
    if c and now-c[0]<300:return c[1]
    if depth>2:return []
    page=fetch_text(u,120,referer or BASE+"/")
    decoded=decode_js_escapes(page)
    out=[]

    # First trust only explicit HLS URLs found in the player HTML/JS.
    # Scan both raw and JavaScript-decoded content because StreamVSMov often
    # hides URLs behind \xNN / \uNNNN escapes.
    for body in (page,decoded):
        for hls in HLS_RE.findall(body):
            hls=decode_js_escapes(hls)
            pair=(urljoin(u,hls),u)
            if pair not in out:out.append(pair)

    # streamvsmov pages contain many generic JS tokens called url/src/file.
    # Treating those as media recursively produced bogus analytics/assets URLs.
    # For this host, only follow real iframe/embed/player links when no HLS was
    # found; never scan arbitrary generic JS URL variables.
    is_streamvsmov="streamvsmov.com" in u.lower()
    if not out:
        candidates=[]
        if not is_streamvsmov:
            for v in MEDIA_SRC_RE.findall(page):
                v=html.unescape(v.replace("\\/","/")).strip()
                if not v or any(ch in v for ch in (" ","{","}","(",")",";")):continue
                absolute=urljoin(u,v)
                if absolute!=u and absolute not in candidates:candidates.append(absolute)
        for v in re.findall(r'<iframe[^>]+src=["\']([^"\']+)',decoded,re.I):
            v=html.unescape(v).strip()
            if not v:continue
            absolute=urljoin(u,v)
            if absolute!=u and absolute not in candidates:candidates.append(absolute)
        for child in candidates[:8]:
            low=child.lower()
            if ".m3u8" in low:
                out.append((child,u));continue
            if depth<2 and ("embed" in low or "player" in low):
                for pair in resolve_media_url(child,u,depth+1):
                    if pair not in out:out.append(pair)
            if len(out)>=8:break

    _resolve_cache[key]=(now,out);return out

def stream_obj(url,title,referer=None):
    hints={"notWebReady":True}
    if referer:
        hints["proxyHeaders"]={"request":{"User-Agent":UA,"Referer":referer}}
    return {"name":"Ivy❤️","title":title,"url":url,"behaviorHints":hints}

def extract_movie_urls(h):
    out=[]
    for href in re.findall(r'href=["\']([^"\']+)',h,re.I):
        if "/phim/" not in href:continue
        u=urljoin(BASE+"/",html.unescape(href)).split("#")[0]
        if u not in out:out.append(u)
    return out

def crawl_listing(seed,max_pages=30):
    if not seed:return []
    seed=urljoin(BASE+"/",seed);now=time.time();c=_list_cache.get(seed)
    if c and now-c[0]<900:return c[1]
    urls=[];seen_pages=set();queue=[seed]
    while queue and len(seen_pages)<max_pages:
        page=queue.pop(0)
        if page in seen_pages:continue
        seen_pages.add(page);h=fetch_text(page,600);before=len(urls)
        for u in extract_movie_urls(h):
            if u not in urls:urls.append(u)
        for href in re.findall(r'href=["\']([^"\']+)',h,re.I):
            v=urljoin(page,html.unescape(href)).split("#")[0]
            if v.startswith(BASE) and re.search(r"(?:[?&]page=\d+|/page/\d+|/trang[-/]\d+)",v,re.I) and v not in seen_pages and v not in queue:queue.append(v)
        if len(seen_pages)<max_pages:
            n=len(seen_pages)+1;sep="&" if "?" in seed else "?";probe=seed+sep+"page="+str(n)
            if probe not in seen_pages and probe not in queue and (before<len(urls) or len(seen_pages)==1):queue.append(probe)
    _list_cache[seed]=(now,urls);return urls
