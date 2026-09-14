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
    ids=[]
    for k in ('trailer','trailerUrl','trailer_url','youtube','youtubeId','ytId'):
        for y in _youtube_ids_from_text(x.get(k)):
            if y not in ids:ids.append(y)
    page=core.fetch_text(x.get('url',''),600) if x.get('url') else ''
    for y in _youtube_ids_from_text(page):
        if y not in ids:ids.append(y)
    if not ids:
        for y in _tmdb_trailer_ids(x):
            if y not in ids:ids.append(y)
    ids=ids[:3];_trailer_cache[key]=(now,ids);return ids

def youtube_media(yid):
    now=time.time();c=_youtube_media_cache.get(yid)
    if c and now-c[0]<600:return c[1]
    try:
        import yt_dlp
        opts={
            'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':15,'retries':1,
            'format':'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]',
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info=ydl.extract_info('https://www.youtube.com/watch?v='+yid,download=False)
        url=info.get('url');headers=info.get('http_headers') or {}
        if url:
            obj={'url':url,'headers':{str(k):str(v) for k,v in headers.items() if v}}
            _youtube_media_cache[yid]=(now,obj);return obj
    except Exception as e:
        print('youtube proxy resolve failed',yid,type(e).__name__,str(e)[:240],flush=True)
    return None

def youtube_proxy(yid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',yid):return Response('bad id',status=400)
    media=youtube_media(yid)
    if not media:return Response('youtube resolve failed',status=502)
    headers=dict(media.get('headers') or {})
    headers.setdefault('User-Agent',core.UA)
    if request.headers.get('Range'):headers['Range']=request.headers['Range']
    try:
        upstream=urlopen(UrlRequest(media['url'],headers=headers),timeout=20)
    except HTTPError as e:
        if e.code in (401,403,410):
            _youtube_media_cache.pop(yid,None);media=youtube_media(yid)
            if media:
                headers=dict(media.get('headers') or {});headers.setdefault('User-Agent',core.UA)
                if request.headers.get('Range'):headers['Range']=request.headers['Range']
                try:upstream=urlopen(UrlRequest(media['url'],headers=headers),timeout=20)
                except Exception:return Response('youtube upstream blocked',status=502)
            else:return Response('youtube resolve failed',status=502)
        else:return Response('youtube upstream error',status=502)
    except Exception:return Response('youtube upstream error',status=502)
    status=getattr(upstream,'status',200)
    out_headers={}
    for k in ('Content-Type','Content-Length','Content-Range','Accept-Ranges','Cache-Control'):
        v=upstream.headers.get(k)
        if v:out_headers[k]=v
    out_headers['Accept-Ranges']='bytes'
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
        page=core.fetch_text(x.get('url',''),600) if x.get('url') else ''
        country=_source_country(page)
        if country:m['country']=country
        else:m.pop('country',None)
        # Deliberately do not expose meta.trailers on Nuvio Full iOS. Its built-in
        # YouTube extractor hands a googlevideo URL to ffmpeg and can fail with 403.
        # Trailer playback is provided as a normal Ivy stream through our proxy instead.
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
        for i,y in enumerate(trailer_ids(x)):
            streams.append({
                'name':'Ivy❤️',
                'title':'🎬 Trailer' if i==0 else f'🎬 Trailer {i+1}',
                'url':f'https://phimhd.onrender.com/ytproxy/{y}.mp4',
                'behaviorHints':{'notWebReady':True},
            })
    return jsonify({'streams':streams})

core.base_meta=base_meta_with_trailer
core.app.add_url_rule('/ytproxy/<yid>.mp4','youtube_proxy',youtube_proxy,methods=['GET'])
core.app.view_functions['meta_route']=meta_route_with_trailer
core.app.view_functions['stream']=stream_with_trailer
_old_manifest=fast.manifest_fast
def manifest_runtime():
    m=_old_manifest();m['version']='1.10.1';m['description']='Ivy❤️ • source rows only • source country metadata • proxied YouTube trailer playback';return m
core.app.view_functions['manifest']=lambda:jsonify(manifest_runtime())
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.10.1','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.10.1','movies':len(core.load().get('movies',[])),'pageSize':fast.PAGE_SIZE,'homeRows':fast.HOME_ROWS,'sitemapSections':len(fast.sitemap().get('sections',[])),'country':'source-detail','trailers':'ivy-youtube-proxy','playbackResolver':'recursive-hls'})
app=core.app