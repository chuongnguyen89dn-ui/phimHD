import re, html, time
import app_fast as fast
import app_full as core
from flask import jsonify

_trailer_cache={}
_old_base_meta=core.base_meta
_old_stream=core.stream
YT_PATTERNS=[r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})',r'["\'](?:youtube_id|youtubeId|ytId|trailer_key|trailerKey)["\']\s*[:=]\s*["\']([A-Za-z0-9_-]{11})']

def youtube_url(yid):
    return 'https://www.youtube.com/watch?v='+yid

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
        ys=trailer_ids(x)
        if ys:
            # Nuvio accepts a full YouTube URL as trailer.key. This is the most robust
            # path on iOS: App Store builds open it externally, Full builds can resolve it in-app.
            m['trailers']=[{'id':y,'key':youtube_url(y),'source':youtube_url(y),'site':'YouTube','type':'Trailer','name':'Trailer'} for y in ys]
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
            # Nuvio's stream parser supports externalUrl. Do not feed a YouTube webpage
            # into the native media player as url; let Nuvio hand it to YouTube/browser.
            streams.append({
                'name':'Ivy❤️',
                'title':'Trailer' if i==0 else f'Trailer {i+1}',
                'externalUrl':youtube_url(y),
                'ytId':y,
            })
    return jsonify({'streams':streams})

core.base_meta=base_meta_with_trailer
core.app.view_functions['meta_route']=meta_route_with_trailer
core.app.view_functions['stream']=stream_with_trailer
_old_manifest=fast.manifest_fast
def manifest_runtime():
    m=_old_manifest();m['version']='1.10.0';m['description']='Ivy❤️ • source rows only • source country metadata • Nuvio-native YouTube trailers';return m
core.app.view_functions['manifest']=lambda:jsonify(manifest_runtime())
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.10.0','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.10.0','movies':len(core.load().get('movies',[])),'pageSize':fast.PAGE_SIZE,'homeRows':fast.HOME_ROWS,'sitemapSections':len(fast.sitemap().get('sections',[])),'country':'source-detail','trailers':'youtube-external-native','playbackResolver':'recursive-hls'})
app=core.app