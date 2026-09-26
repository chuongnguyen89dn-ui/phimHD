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

    # Current RoPhim /xem-phim/ pages often keep the real player URL only
    # inside the JavaScript episodes array. Resolve those sources directly
    # instead of treating the watch page itself as a media/player URL.
    if "rophims.team/xem-phim/" in u.lower() or "rophim.loan/xem-phim/" in u.lower():
        try:
            arr=extract_array_after(page,"var episodes =") or extract_array_after(page,"episodes =") or []
            watch_sources=[]
            for srv in arr if isinstance(arr,list) else []:
                for item in (srv.get("server_data") or []) if isinstance(srv,dict) else []:
                    media=item.get("link_m3u8") or item.get("link_embed")
                    if not media: continue
                    media=html.unescape(str(media).replace("\\/","/")).strip()
                    if media and media not in watch_sources: watch_sources.append(media)
            for media in watch_sources[:12]:
                if ".m3u8" in media.lower():
                    pair=(urljoin(u,media),u)
                    if pair not in out: out.append(pair)
                elif depth<2:
                    for pair in resolve_media_url(media,u,depth+1):
                        if pair not in out: out.append(pair)
                if len(out)>=8: break
            if out:
                _resolve_cache[(u,referer or "")]=(time.time(),out)
                return out
        except Exception as e:
            print("[rophim watch resolve]",u,type(e).__name__,str(e)[:180],flush=True)

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

def canonical_movie_url(u):
    s=str(u or "").strip()
    if not s:return ""
    try:
        p=re.sub(r"^https?://(?:www\.)?(?:rophim\.loan|rophims\.team)","",s,flags=re.I)
        if p.startswith("/"):return p.rstrip("/") or "/"
    except:pass
    return s.rstrip("/")

def data_index():
    data=load().get("movies",[]);by={}
    for x in data:
        u=x.get("url")
        if not u:continue
        by[str(u).rstrip("/")]=x
        by[canonical_movie_url(u)]=x
    return data,by
def ordered(urls,pred=None):
    _,by=data_index();out=[];seen=set()
    for u in urls:
        x=by.get(str(u).rstrip("/")) or by.get(canonical_movie_url(u))
        if x and (pred is None or pred(x)):
            k=canonical_movie_url(x.get("url"))
            if k not in seen:out.append(x);seen.add(k)
    return out

def infer_season(x,h=""):
    text=" ".join([clean(x.get("title","")),clean(h[:20000])])
    for pat in [r"(?i)(?:phần|season)\s*(\d+)",r"(?i)S(\d{1,2})(?:E\d+)?"]:
        m=re.search(pat,text)
        if m:return max(1,int(m.group(1)))
    return 1
def series_key(x):
    s=clean(x.get("title") or x.get("slug") or "").lower();s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I);s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")
def series_name(x):
    s=clean(x.get("title") or x.get("slug") or "Ivy❤️");s=re.sub(r"\s*\([^)]*(?:phần|season)\s*\d+[^)]*\)","",s,flags=re.I);s=re.sub(r"\s*[-–—:]?\s*(?:phần|season)\s*\d+\b","",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()") or clean(x.get("title"))
def dedupe_series(items):
    out=[];seen=set()
    for x in items:
        k=series_key(x)
        if k not in seen:seen.add(k);out.append(x)
    return out
def family_seasons(x):
    out={};k=series_key(x)
    for y in load().get("movies",[]):
        if typ(y)=="series" and series_key(y)==k:
            s=infer_season(y)
            if s not in out or y.get("url")==x.get("url"):out[s]=y
    return out or {infer_season(x):x}

SOURCE_SECTIONS=["Điện ảnh Hàn Quốc","Mọt phim Hoa Ngữ","Thiên đường Phim Thái","Phim US-UK Mới","Phim Điện Ảnh Mới Cóng","Dấu ấn điện ảnh Việt","Đêm Kinh Hoàng","Mê Cung Phim Nhật","Phim Bộ Đã Hoàn Thành","Hành Động Nghẹt Thở","Trinh Thám & Bí Ẩn","Tinh Hoa Điện Ảnh Hồng Kông","Top 10 phim bộ hôm nay","Top 10 phim lẻ hôm nay","Thế giới Anime","Cổ Trang Trung Quốc","Mãn Nhãn với Phim Chiếu Rạp","Sắp Lên Sóng"]
SECTION_ALIASES={"Phim Điện Ảnh Mới Cóng":["Phim Điện Ảnh Mới Cóng","Phim Điện Ảnh Mới Cóong"]}
SERIES_SECTIONS={"Phim Bộ Đã Hoàn Thành","Top 10 phim bộ hôm nay"}
def _pos(h,label,start=0):
    ps=[h.find(v,start) for v in (label,html.escape(label,quote=False)) if h.find(v,start)>=0];return min(ps) if ps else -1
def _listing_link(seg):
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',seg,re.I|re.S):
        txt=re.sub("<[^>]+>"," ",m.group(2))
        if re.search(r"(?i)xem\s*thêm|tất\s*cả|xem\s*tất",html.unescape(txt)):
            href=html.unescape(m.group(1))
            if "/phim/" not in href:return urljoin(BASE+"/",href)
    for href in re.findall(r'href=["\']([^"\']+)',seg,re.I):
        u=urljoin(BASE+"/",html.unescape(href)).split("#")[0]
        if "/phim/" not in u and u.startswith(BASE) and any(k in u for k in ["/chu-de/","/the-loai/","/quoc-gia/","/danh-sach/","/phim-le","/phim-bo"]):return u
    return None
def source_home_sections():
    now=time.time()
    if _section_cache["data"] and now-_section_cache["at"]<600:return _section_cache["data"]
    h=fetch_text(BASE+"/phimhay",300);start=max(0,_pos(h,"Bạn đang quan tâm gì?"));ps=[]
    for i,label in enumerate(SOURCE_SECTIONS):
        aliases=SECTION_ALIASES.get(label,[label])
        found=[_pos(h,v,start) for v in aliases]
        found=[p for p in found if p>=0]
        p=min(found) if found else -1
        if p>=0:ps.append((p,i,label))
    ps.sort();out={}
    for n,(p,i,label) in enumerate(ps):
        seg=h[p:(ps[n+1][0] if n+1<len(ps) else len(h))];home_urls=extract_movie_urls(seg)
        if home_urls:out[label]={"home":home_urls,"listing":_listing_link(seg)}
    _section_cache.update(at=now,data=out);return out
def source_section_items(label):
    info=source_home_sections().get(label) or {};urls=list(info.get("home") or []);listing=info.get("listing")
    if listing:
        for u in crawl_listing(listing):
            if u not in urls:urls.append(u)
    if len(urls)<40:
        target=norm(label)
        for x in load().get("movies",[]):
            vals=tax(x,"sections")+tax(x,"genres")+tax(x,"countries")
            if any(target==norm(v) or target in norm(v) or norm(v) in target for v in vals if v):
                u=x.get("url")
                if u and u not in urls:urls.append(u)
    return ordered(urls)
def source_menu(kind):
    path="/phim-bo" if kind=="series" else "/phim-le";urls=crawl_listing(BASE+path,max_pages=60);items=ordered(urls,lambda x:typ(x)==kind)
    if len(items)<100:
        seen={x.get("url") for x in items}
        for x in load().get("movies",[]):
            if typ(x)==kind and x.get("url") not in seen:items.append(x);seen.add(x.get("url"))
    return dedupe_series(items) if kind=="series" else items

def source_watch_url(page_url,episode=None):
    u=str(page_url or "")
    # Catalog IDs may still contain the retired rophim.loan host. Keep IDs stable,
    # but always resolve playback against the current rophims.team source host.
    try:
        path=re.sub(r"^https?://[^/]+","",u)
        if path.startswith("/"):u=BASE+path
    except:pass
    if "/phim/" in u:u=u.replace("/phim/","/xem-phim/",1)
    if episode:
        u=u.split("?",1)[0]
        u+="?tap=tap-"+str(max(1,int(episode)))+"&sv=0"
    return u

def extract_array_after(h,marker):
    p=h.find(marker)
    if p<0:return None
    p=h.find("[",p)
    if p<0:return None
    depth=0;quote=None;esc=False
    for i in range(p,len(h)):
        ch=h[i]
        if quote:
            if esc:esc=False
            elif ch=="\\":esc=True
            elif ch==quote:quote=None
            continue
        if ch in ('"',"'"):quote=ch;continue
        if ch=="[":depth+=1
        elif ch=="]":
            depth-=1
            if depth==0:
                try:return json.loads(h[p:i+1])
                except:return None
    return None
def exact_watch_episode_sources(watch_url,episode,referer=None):
    page=fetch_text(watch_url,120,referer or BASE+"/")
    arr=extract_array_after(page,"var episodes =") or extract_array_after(page,"episodes =") or []
    out=[];seen=set()
    for srv in arr if isinstance(arr,list) else []:
        if not isinstance(srv,dict):continue
        server=clean(srv.get("server_name") or "Nguồn")
        for item in srv.get("server_data") or []:
            if not isinstance(item,dict):continue
            text=(str(item.get("slug") or "")+" "+str(item.get("name") or "")+" "+str(item.get("filename") or ""))
            m=re.search(r"(?i)(?:tập|tap|episode)[-_ ]*(\d+)",text)
            if not m or int(m.group(1))!=int(episode):continue
            media=item.get("link_m3u8") or item.get("link_embed")
            if not media:continue
            media=html.unescape(str(media).replace("\\/","/"))
            if media in seen:continue
            seen.add(media);out.append({"name":server,"url":media,"referer":watch_url})
    return out

def episode_rows(x):
    page_url=x.get("url","");h=fetch_text(page_url,180);arr=extract_array_after(h,"var episodes =") or extract_array_after(h,"episodes =") or [];by={}
    def add(ep,name,server,url,referer=page_url):
        if not ep or not url:return
        row=by.setdefault(ep,{"episode":ep,"title":name or f"Tập {ep}","sources":[]})
        src={"name":clean(server or "Nguồn"),"url":html.unescape(str(url).replace("\\/","/")),"referer":referer}
        if not any(s.get("url")==src["url"] for s in row["sources"]):row["sources"].append(src)
    for srv in arr if isinstance(arr,list) else []:
        for item in (srv.get("server_data") or []) if isinstance(srv,dict) else []:
            slug=str(item.get("slug") or "");name=clean(item.get("name") or item.get("filename") or slug);m=re.search(r"(\d+)",slug+" "+name)
            if not m:continue
            add(int(m.group(1)),name,srv.get("server_name"),item.get("link_m3u8") or item.get("link_embed"))
    # Current RoPhim detail pages expose episode anchors but move media data to /xem-phim/.
    for href,label in re.findall(r'<a[^>]+href=["\']([^"\']*?/xem-phim/[^"\']*)["\'][^>]*>(.*?)</a>',h,re.I|re.S):
        u=urljoin(page_url,html.unescape(href));txt=clean(re.sub(r"<[^>]+>"," ",label))
        m=re.search(r"(?i)(?:tập|tap|episode)\s*[- ]?(\d+)",txt+" "+u)
        ep=int(m.group(1)) if m else (1 if "tap=" not in u.lower() else 0)
        # Only use the watch-page anchor as a fallback when this episode was not
        # already populated from the source's real server_data. Otherwise the
        # same episode is duplicated as an extra pseudo-source.
        if ep and ep not in by:add(ep,txt or f"Tập {ep}","RoPhim",u,page_url)
    if not by and typ(x)=="series":
        # Last-resort episode 1 watch page; more episodes may be discovered on next metadata refresh.
        add(1,"Tập 1","RoPhim",source_watch_url(page_url,1),page_url)
    return infer_season(x,h),[by[k] for k in sorted(by)]

def tmdb_get(path,params=None,ttl=21600):
    if not TMDB_API_KEY:return None
    params=dict(params or {});params["api_key"]=TMDB_API_KEY;key=path+"?"+urlencode(sorted(params.items()));now=time.time();c=_tmdb_cache.get(key)
    if c and now-c[0]<ttl:return c[1]
    try:
        with urlopen(Request(TMDB_API+path+"?"+urlencode(params),headers={"Accept":"application/json","User-Agent":"Ivy/1.9.1"}),timeout=8) as r:d=json.loads(r.read().decode())
        _tmdb_cache[key]=(now,d);return d
    except:return None
def apply_tmdb(x):
    if not TMDB_API_KEY:return x
    media="tv" if typ(x)=="series" else "movie";q=series_name(x) if media=="tv" else clean(x.get("title") or x.get("originalTitle") or "");params={"query":q,"language":"vi-VN","include_adult":"false"};y=year(x)
    if y:params["first_air_date_year" if media=="tv" else "year"]=y
    rows=(tmdb_get("/search/"+media,params) or {}).get("results") or [];target={norm(q),norm(x.get("originalTitle"))};target.discard("")
    for r in rows[:10]:
        names={norm(r.get("title")),norm(r.get("name")),norm(r.get("original_title")),norm(r.get("original_name"))};names.discard("")
        if not target.intersection(names):continue
        z=dict(x);z["tmdb"]={"voteAverage":r.get("vote_average"),"voteCount":r.get("vote_count"),"tmdbId":r.get("id")}
        if media=="tv":
            # Keep seasons visually distinct. The TV search result poster is the
            # show-level poster and would make every season card identical.
            # Prefer the exact TMDB season poster; if it is missing, preserve
            # the source-specific RoPhim poster already stored on this season.
            season_no=infer_season(x)
            sd=tmdb_get(f"/tv/{r.get('id')}/season/{season_no}",{"language":"vi-VN"}) or {}
            if sd.get("poster_path"):z["poster"]=TMDB_IMG+"w780"+sd["poster_path"]
        elif r.get("poster_path"):
            z["poster"]=TMDB_IMG+"w780"+r["poster_path"]
        if r.get("backdrop_path"):z["backdrop"]=TMDB_IMG+"w1280"+r["backdrop_path"]
        return z
    return x

def base_meta(x,full=False):
    if full:x=apply_tmdb(x)
    m={"id":mid(x),"type":typ(x),"name":series_name(x) if typ(x)=="series" else clean(x.get("title") or x.get("slug") or "Ivy❤️"),"poster":x.get("poster") or None,"background":x.get("backdrop") or None,"description":clean(x.get("description")),"website":x.get("url"),"posterShape":"poster"};y=year(x)
    if y:m["releaseInfo"]=str(y)
    if tax(x,"genres"):m["genres"]=tax(x,"genres")
    if tax(x,"countries"):m["country"]=', '.join(tax(x,"countries"))
    if x.get("duration"):m["runtime"]=x["duration"]
    tm=x.get("tmdb") or {}
    if tm.get("voteAverage") is not None:m["rating"]=round(float(tm["voteAverage"]),1);m["voteCount"]=tm.get("voteCount")
    if full and typ(x)=="series":
        videos=[]
        for season,src in sorted(family_seasons(x).items()):
            _,eps=episode_rows(src)
            for e in eps:videos.append({"id":f"{m['id']}:{season}:{e['episode']}","title":e["title"],"season":season,"episode":e["episode"],"overview":clean(src.get("description") or x.get("description")),"thumbnail":src.get("backdrop") or src.get("poster")})
        if videos:m["videos"]=videos
    return m

def genre_options():
    out=[]
    for x in load().get("movies",[]):
        for g in tax(x,"genres"):
            if g and g not in out:out.append(g)
    return sorted(out)
def manifest_data():
    common=[{"name":"genre","isRequired":False,"options":genre_options()},{"name":"skip","isRequired":False},{"name":"search","isRequired":False}]
    cats=[{"type":"movie","id":"ivy_movies","name":"❤️ Ivy • Phim Lẻ","extra":common},{"type":"series","id":"ivy_series","name":"❤️ Ivy • Phim Bộ","extra":common}]
    active=source_home_sections()
    for i,label in enumerate(SOURCE_SECTIONS):
        if active.get(label):cats.append({"type":"series" if label in SERIES_SECTIONS else "movie","id":f"ivy_src_{i}","name":f"❤️ Ivy • {label}","extra":common})
    return {"id":"community.ivy.catalog","version":"1.9.1","name":"Ivy❤️","description":"Ivy❤️ • source catalogs with paginated listings and web playback resolver","resources":["catalog","meta","stream"],"types":["movie","series"],"idPrefixes":["ivy_"],"behaviorHints":{"configurable":False},"catalogs":cats}

@app.get("/")
def root():return jsonify({"ok":True,"service":"Ivy❤️","version":"1.9.1","manifest":"/manifest.json"})
@app.get("/manifest.json")
def manifest():return jsonify(manifest_data())
@app.get("/health")
def health():return jsonify({"ok":True,"version":"1.9.1","movies":len(load().get("movies",[])),"sourceSections":list(source_home_sections().keys()),"legacyFranchiseCatalog":False,"playbackResolver":"recursive-hls"})
def extras(path=""):
    o={}
    for p in path.split("/"):
        if "=" in p:k,v=p.split("=",1);o[k]=unquote(v)
    for k in ("skip","search","genre"):
        if request.args.get(k)!=None:o[k]=request.args[k]
    return o
def catalog(cid,path=""):
    e=extras(path);q=(e.get("search") or "").lower().strip()
    if cid=="ivy_movies":items=source_menu("movie")
    elif cid=="ivy_series":items=source_menu("series")
    elif cid.startswith("ivy_src_"):
        try:items=source_section_items(SOURCE_SECTIONS[int(cid.rsplit("_",1)[1])])
        except:return jsonify({"metas":[]})
    else:items=[]
    out=[]
    for x in items:
        if e.get("genre") and e["genre"] not in tax(x,"genres"):continue
        m=base_meta(x)
        if not q or q in (m["name"]+" "+m.get("description","")).lower():out.append(m)
    try:sk=max(0,int(e.get("skip",0)))
    except:sk=0
    return jsonify({"metas":out[sk:sk+100]})
@app.get("/catalog/<t>/<cid>.json")
def cp(t,cid):return catalog(cid)
@app.get("/catalog/<t>/<cid>/<path:p>.json")
def ce(t,cid,p):return catalog(cid,p)
@app.get("/meta/<t>/<path:item_id>.json")
def meta_route(t,item_id):
    base=item_id.split(":",1)[0];u=dec(base[4:]) if base.startswith("ivy_") else "";x=next((x for x in load().get("movies",[]) if x.get("url")==u),None)
    return jsonify({"meta":base_meta(x,True) if x else None})
@app.get("/stream/<t>/<path:item_id>.json")
def stream(t,item_id):
    parts=item_id.split(":");base=parts[0];u=dec(base[4:]) if base.startswith("ivy_") else "";x=next((x for x in load().get("movies",[]) if x.get("url")==u),None)
    if not x:return jsonify({"streams":[]})
    streams=[];seen=set()
    if len(parts)>=3 and typ(x)=="series":
        try:season=int(parts[-2]);ep=int(parts[-1])
        except:return jsonify({"streams":[]})
        src=family_seasons(x).get(season) or x
        harvested=(src.get("playbackHints") or {}).get("episodeSources") or []
        cached=[]
        for s in harvested:
            if s.get("episode")==ep:
                cached.append({
                    "name":clean(s.get("server") or "Nguồn"),
                    "url":s.get("link_m3u8") or s.get("link_embed") or s.get("url"),
                    "referer":(src.get("playbackHints") or {}).get("watchUrl") or src.get("url")
                })
        if cached:
            row={"episode":ep,"title":f"Tập {ep}","sources":cached}
        else:
            _,rows=episode_rows(src);row=next((r for r in rows if r["episode"]==ep),None)
            if not row:return jsonify({"streams":[]})
        expanded=[]
        for source in row["sources"]:
            raw=source.get("url")
            ref0=source.get("referer") or src.get("url")
            if "/xem-phim/" in str(raw or "") and ".m3u8" not in str(raw or "").lower():
                exact=exact_watch_episode_sources(raw,ep,ref0)
                if exact:
                    expanded.extend(exact)
                    continue
            expanded.append(source)
        for source in expanded:
            raw=source.get("url")
            ref0=source.get("referer") or src.get("url")
            if ".m3u8" in str(raw or "").lower():
                pairs=[(raw,ref0)]
            else:
                pairs=resolve_media_url(raw,ref0)
                if pairs:pairs=pairs[:1]
            for media,ref in pairs:
                if media in seen:continue
                seen.add(media);streams.append(stream_obj(media,f"Ivy❤️ • Mùa {season} • {row['title']} • {source['name']}",ref))
        return jsonify({"streams":streams})
    page_url=x.get("url","");page=fetch_text(page_url,120);candidates=[]
    # Playback now lives on /xem-phim/ rather than the public /phim/ detail page.
    candidates.append((source_watch_url(page_url,1),page_url))
    hints=x.get("playbackHints") or {}
    for v in hints.get("direct") or []:candidates.append((v,page_url))
    for v in HLS_RE.findall(page):candidates.append((v,page_url))
    arr=extract_array_after(page,"var episodes =") or extract_array_after(page,"episodes =") or []
    for srv in arr if isinstance(arr,list) else []:
        for item in (srv.get("server_data") or []) if isinstance(srv,dict) else []:
            if item.get("link_m3u8"):candidates.append((item["link_m3u8"],page_url))
            elif item.get("link_embed"):candidates.append((item["link_embed"],page_url))
    for s in hints.get("episodeSources") or []:
        if s.get("url"):candidates.append((s["url"],page_url))
    for raw,ref0 in candidates:
        pairs=resolve_media_url(raw,ref0)
        if not pairs and ".m3u8" in str(raw).lower():pairs=[(raw,ref0)]
        for media,ref in pairs:
            if media in seen:continue
            seen.add(media);streams.append(stream_obj(media,"Ivy❤️ • Phát" if not streams else f"Ivy❤️ • Nguồn {len(streams)+1}",ref))
    return jsonify({"streams":streams})

@app.get("/diag/playback/<slug>.json")
def playback_diag(slug):
    u=BASE+"/phim/"+slug
    watch=source_watch_url(u,1)
    h=fetch_text(u,0)
    wh=fetch_text(watch,0,u)
    merged=h+"\n"+wh
    arr=extract_array_after(merged,"var episodes =") or extract_array_after(merged,"episodes =") or []
    direct=list(dict.fromkeys(HLS_RE.findall(merged)))
    eps=[]
    for srv in arr if isinstance(arr,list) else []:
        if not isinstance(srv,dict):continue
        for item in srv.get("server_data") or []:
            if not isinstance(item,dict):continue
            media=item.get("link_m3u8") or item.get("link_embed") or ""
            if media:eps.append({"server":clean(srv.get("server_name") or "Nguồn"),"name":clean(item.get("name") or item.get("slug") or ""),"url":media})
    return jsonify({"ok":bool(direct or eps),"url":u,"watchUrl":watch,"detailHtmlBytes":len(h),"watchHtmlBytes":len(wh),"hasEpisodesVar":"var episodes =" in merged or "episodes =" in merged,"direct":direct[:8],"episodeSources":eps[:20]})

if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
