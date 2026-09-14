import re, html, time
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError
import app_fast as fast
import app_full as core
from flask import jsonify, request, Response, stream_with_context

_trailer_cache={};_youtube_media_cache={}
_old_base_meta=core.base_meta
_old_stream=core.stream
YT_PATTERNS=[r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})',r'["\'](?:youtube_id|youtubeId|ytId|trailer_key|trailerKey)["\']\s*[:=]\s*["\']([A-Za-z0-9_-]{11})']

def _youtube_ids_from_text(text):
    out=[];text=html.unescape(str(text or '').replace('\\/','/'))
    for pat in YT_PATTERNS:
        for y in re.findall(pat,text,re.I):
            if y not in out:out.append(y)
    return out

def _sitemap_trailer_ids(x):
    u=(x or {}).get('url')
    if not u:return []
    for s in fast.sitemap().get('sections',[]):
        if s.get('label')!='Sắp Lên Sóng':continue
        info=(s.get('trailers') or {}).get(u) or {};out=[]
        for y in info.get('youtubeIds') or []:
            if re.fullmatch(r'[A-Za-z0-9_-]{11}',str(y)) and y not in out:out.append(y)
        return out[:3]
    return []

def _tmdb_trailer_ids(x):
    z=core.apply_tmdb(x);tm=z.get('tmdb') or {};tid=tm.get('tmdbId')
    if not tid:return []
    media='tv' if core.typ(x)=='series' else 'movie';out=[]
    for lang in ('vi-VN','en-US'):
        data=core.tmdb_get(f'/{media}/{tid}/videos',{'language':lang},21600) or {};rows=data.get('results') or []
        preferred=sorted(rows,key=lambda r:(str(r.get('type','')).lower()!='trailer',str(r.get('site','')).lower()!='youtube',not bool(r.get('official'))))
        for r in preferred:
            key=str(r.get('key') or '')
            if str(r.get('site','')).lower()=='youtube' and re.fullmatch(r'[A-Za-z0-9_-]{11}',key) and key not in out:out.append(key)
        if out:break
    return out[:3]

def trailer_ids(x):
    if not x:return []
    key=x.get('url') or core.mid(x);now=time.time();c=_trailer_cache.get(key)
    if c and now-c[0]<3600:return c[1]
    ids=_sitemap_trailer_ids(x)
    for k in ('trailer','trailerUrl','trailer_url','youtube','youtubeId','ytId'):
        for y in _youtube_ids_from_text(x.get(k)):
            if y not in ids:ids.append(y)
    if not ids:
        page=core.fetch_text(x.get('url',''),600) if x.get('url') else ''
        for y in _youtube_ids_from_text(page):
            if y not in ids:ids.append(y)
    if not ids:
        for y in _tmdb_trailer_ids(x):
            if y not in ids:ids.append(y)
    ids=ids[:3];_trailer_cache[key]=(now,ids);return ids

def _probe_media(obj):
    if not obj or not obj.get('url'):return False
    headers=dict(obj.get('headers') or {});headers.setdefault('User-Agent',core.UA);headers['Range']='bytes=0-1'
    try:
        with urlopen(UrlRequest(obj['url'],headers=headers),timeout=12) as r:
            status=getattr(r,'status',200);data=r.read(2)
            ok=status in (200,206) and len(data)>0
            print('youtube probe',obj.get('client'),obj.get('format_id'),status,'ok' if ok else 'empty',flush=True)
            return ok
    except Exception as e:
        print('youtube probe failed',obj.get('client'),obj.get('format_id'),type(e).__name__,str(e)[:180],flush=True);return False

def _extract_media(yid,client,fmt):
    import yt_dlp
    opts={'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':15,'retries':1,'format':fmt,'extractor_args':{'youtube':{'player_client':[client]}}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info('https://www.youtube.com/watch?v='+yid,download=False)
        url=info.get('url');headers=info.get('http_headers') or {}
        if not url:return None
        return {'url':url,'headers':{str(k):str(v) for k,v in headers.items() if v},'format_id':str(info.get('format_id') or ''),'client':client,'ext':str(info.get('ext') or '')}
    except Exception as e:
        print('youtube extract failed',yid,client,fmt,type(e).__name__,str(e)[:220],flush=True);return None

def youtube_media(yid):
    now=time.time();c=_youtube_media_cache.get(yid)
    if c and now-c[0]<300:return c[1]
    # 2026 YouTube PO-token enforcement blocks many GVS URLs. Format 18 is pre-muxed H264+AAC
    # and remains the most reliable no-token fallback for android_vr. Every URL is probed from
    # the same Render host before it is exposed to Nuvio, so dead/403 URLs are never cached.
    candidates=[('android_vr','18'),('web_embedded','18/best[ext=mp4][vcodec!=none][acodec!=none]'),('tv','18/best[ext=mp4][vcodec!=none][acodec!=none]')]
    for client,fmt in candidates:
        obj=_extract_media(yid,client,fmt)
        if obj and _probe_media(obj):
            _youtube_media_cache[yid]=(now,obj);return obj
    return None

def youtube_proxy(yid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',yid):return Response('bad id',status=400)
    media=youtube_media(yid)
    if not media:return Response('youtube playable format unavailable',status=502)
    headers=dict(media.get('headers') or {});headers.setdefault('User-Agent',core.UA)
    if request.headers.get('Range'):headers['Range']=request.headers['Range']
    try:upstream=urlopen(UrlRequest(media['url'],headers=headers),timeout=25)
    except HTTPError as e:
        print('youtube upstream http',yid,media.get('client'),media.get('format_id'),e.code,flush=True)
        if e.code in (401,403,410):
            _youtube_media_cache.pop(yid,None);media=youtube_media(yid)
            if not media:return Response('youtube playable format unavailable',status=502)
            headers=dict(media.get('headers') or {});headers.setdefault('User-Agent',core.UA)
            if request.headers.get('Range'):headers['Range']=request.headers['Range']
            try:upstream=urlopen(UrlRequest(media['url'],headers=headers),timeout=25)
            except Exception as e2:
                print('youtube retry failed',yid,type(e2).__name__,str(e2)[:180],flush=True);return Response('youtube upstream blocked',status=502)
        else:return Response('youtube upstream error',status=502)
    except Exception as e:
        print('youtube upstream failed',yid,type(e).__name__,str(e)[:180],flush=True);return Response('youtube upstream error',status=502)
    status=getattr(upstream,'status',200);out_headers={}
    for k in ('Content-Type','Content-Length','Content-Range','Accept-Ranges','Cache-Control'):
        v=upstream.headers.get(k)
        if v:out_headers[k]=v
    out_headers['Accept-Ranges']='bytes';print('youtube proxy hit',yid,media.get('client'),media.get('format_id'),status,request.headers.get('Range',''),flush=True)
    def generate():
        try:
            while True:
                chunk=upstream.read(256*1024)
                if not chunk:break
                yield chunk
        finally:
            try:upstream.close()
            except:pass
    return Response(stream_with_context(generate()),status=status,headers=out_headers,direct_passthrough=True)

def _source_country(page):
    if not page:return ''
    text=html.unescape(page)
    pats=[r'Quốc\s*gia(?:\s*sản\s*xuất)?\s*</[^>]+>\s*(?:<[^>]+>\s*)*([^<]{2,80})',r'Quốc\s*gia(?:\s*sản\s*xuất)?\s*[:：]\s*(?:<[^>]+>\s*)*([^<\n]{2,80})',r'["\']country["\']\s*[:=]\s*["\']([^"\']{2,80})']
    for p in pats:
        m=re.search(p,text,re.I|re.S)
        if m:
            v=core.clean(re.sub('<[^>]+>',' ',m.group(1)))
            if v:return v
    return ''

def base_meta_with_trailer(x,full=False):
    m=_old_base_meta(x,full)
    if not x or not m:return m
    if full:
        page=core.fetch_text(x.get('url',''),600) if x.get('url') else '';country=_source_country(page)
        if country:m['country']=country
        else:m.pop('country',None)
        m.pop('trailers',None);m.pop('trailerStreams',None)
    return m

def _find_item(item_id):
    base=item_id.split(':',1)[0];u=core.dec(base[4:]) if base.startswith('ivy_') else ''
    return next((x for x in core.load().get('movies',[]) if x.get('url')==u),None)

def meta_route_with_trailer(t,item_id):
    x=_find_item(item_id);return jsonify({'meta':base_meta_with_trailer(x,True) if x else None})

def stream_with_trailer(t,item_id):
    response=_old_stream(t,item_id)
    try:data=response.get_json() or {};streams=list(data.get('streams') or [])
    except:return response
    x=_find_item(item_id)
    if x:
        ids=trailer_ids(x);print('ivy stream',item_id,'trailers',ids,flush=True)
        for i,y in enumerate(ids):streams.append({'name':'Ivy❤️','title':'🎬 Trailer' if i==0 else f'🎬 Trailer {i+1}','url':f'https://phimhd.onrender.com/ytproxy/{y}.mp4','behaviorHints':{'notWebReady':True}})
    return jsonify({'streams':streams})

core.base_meta=base_meta_with_trailer
core.app.add_url_rule('/ytproxy/<yid>.mp4','youtube_proxy',youtube_proxy,methods=['GET'])
core.app.view_functions['meta_route']=meta_route_with_trailer
core.app.view_functions['stream']=stream_with_trailer
_old_manifest=fast.manifest_fast
def manifest_runtime():
    m=_old_manifest();m['version']='1.10.3';m['description']='Ivy❤️ • exact source rows • probed YouTube format 18 trailer proxy';return m
core.app.view_functions['manifest']=lambda:jsonify(manifest_runtime())
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.10.3','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.10.3','movies':len(core.load().get('movies',[])),'pageSize':fast.PAGE_SIZE,'homeRows':fast.HOME_ROWS,'sitemapSections':len(fast.sitemap().get('sections',[])),'country':'source-detail','trailers':'source-id+probed-format18-proxy','playbackResolver':'recursive-hls'})
app=core.app