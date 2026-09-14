import re, html, time
import app_fast as fast
import app_full as core
from flask import jsonify

_trailer_cache={}
_old_base_meta=core.base_meta
_old_stream=core.stream

YT_PATTERNS=[
    r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,20})',
    r'["\'](?:youtube_id|youtubeId|ytId|trailer_key|trailerKey)["\']\s*[:=]\s*["\']([A-Za-z0-9_-]{6,20})',
]

def _youtube_ids_from_text(text):
    out=[]
    text=html.unescape(str(text or '').replace('\\/','/'))
    for pat in YT_PATTERNS:
        for y in re.findall(pat,text,re.I):
            if y not in out:out.append(y)
    return out

def _tmdb_trailer_ids(x):
    # Use TMDB only as fallback when the source page itself does not expose its trailer.
    z=core.apply_tmdb(x)
    tm=z.get('tmdb') or {};tid=tm.get('tmdbId')
    if not tid:return []
    media='tv' if core.typ(x)=='series' else 'movie';out=[]
    for lang in ('vi-VN','en-US'):
        data=core.tmdb_get(f'/{media}/{tid}/videos',{'language':lang},21600) or {}
        rows=data.get('results') or []
        preferred=sorted(rows,key=lambda r:(str(r.get('type','')).lower()!='trailer',str(r.get('site','')).lower()!='youtube',not bool(r.get('official'))))
        for r in preferred:
            if str(r.get('site','')).lower()=='youtube' and r.get('key') and r['key'] not in out:out.append(r['key'])
        if out:break
    return out[:3]

def trailer_ids(x):
    if not x:return []
    key=x.get('url') or core.mid(x);now=time.time();c=_trailer_cache.get(key)
    if c and now-c[0]<3600:return c[1]
    ids=[]
    # Catalog fields first, then exact source detail page.
    for k in ('trailer','trailerUrl','trailer_url','youtube','youtubeId','ytId'):
        ids += [y for y in _youtube_ids_from_text(x.get(k)) if y not in ids]
    page=core.fetch_text(x.get('url',''),600) if x.get('url') else ''
    for y in _youtube_ids_from_text(page):
        if y not in ids:ids.append(y)
    if not ids:
        for y in _tmdb_trailer_ids(x):
            if y not in ids:ids.append(y)
    ids=ids[:3];_trailer_cache[key]=(now,ids);return ids

def base_meta_with_trailer(x,full=False):
    m=_old_base_meta(x,full)
    if not x or not m:return m
    if full:
        ys=trailer_ids(x)
        if ys:
            # Both fields are emitted because native Stremio/Nuvio clients use one or the other depending on build.
            m['trailers']=[{'source':y,'type':'Trailer'} for y in ys]
            m['trailerStreams']=[{'title':'Trailer' if i==0 else f'Trailer {i+1}','ytId':y} for i,y in enumerate(ys)]
    return m

def _find_item(item_id):
    base=item_id.split(':',1)[0];u=core.dec(base[4:]) if base.startswith('ivy_') else ''
    return next((x for x in core.load().get('movies',[]) if x.get('url')==u),None)

def meta_route_with_trailer(t,item_id):
    x=_find_item(item_id)
    return jsonify({'meta':base_meta_with_trailer(x,True) if x else None})

def stream_with_trailer(t,item_id):
    # Keep all normal Ivy playback sources. For titles that have no released media yet,
    # expose the source trailer as a native YouTube stream so Nuvio can play it.
    response=_old_stream(t,item_id)
    try:data=response.get_json() or {};streams=list(data.get('streams') or [])
    except:return response
    x=_find_item(item_id)
    if x:
        ys=trailer_ids(x)
        existing={s.get('ytId') for s in streams if isinstance(s,dict)}
        for i,y in enumerate(ys):
            if y in existing:continue
            streams.append({'name':'Ivy❤️','title':'Trailer' if i==0 else f'Trailer {i+1}','ytId':y})
    return jsonify({'streams':streams})

# Patch metadata used by catalog/detail and replace already-registered Flask route handlers.
core.base_meta=base_meta_with_trailer
core.app.view_functions['meta_route']=meta_route_with_trailer
core.app.view_functions['stream']=stream_with_trailer

# bump visible runtime version while keeping the exact sitemap implementation from app_fast
_old_manifest=fast.manifest_fast
def manifest_196():
    m=_old_manifest();m['version']='1.9.6';m['description']='Ivy❤️ • exact source sitemap • full pagination • native Nuvio trailers';return m
core.app.view_functions['manifest']=lambda:jsonify(manifest_196())
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.9.6','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.9.6','movies':len(core.load().get('movies',[])),'pageSize':fast.PAGE_SIZE,'homeRows':fast.HOME_ROWS,'sitemapSections':len(fast.sitemap().get('sections',[])),'trailers':'native-youtube','playbackResolver':'recursive-hls'})

app=core.app
