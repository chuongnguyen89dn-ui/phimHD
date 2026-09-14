import time
import app_full as core
from flask import jsonify, request

PAGE_SIZE=24
_cache={}

# Home rows are source-home rows, not generic Phim Le/Phim Bo navigation catalogs.
HOME_ROWS=[
 'Phim Điện Ảnh Mới Coóng',
 'Top 10 Phim Hôm Nay',
 'Mãn Nhãn với Tuyển Tập Phim Lẻ Hot',
 'Hòa Mình Cùng Các Bộ Phim Hoạt Hình Hay',
 'Kho Tàng Anime Mới Nhất',
]
ROW_RULES={
 'Phim Điện Ảnh Mới Coóng':['chieu rap','dien anh'],
 'Mãn Nhãn với Tuyển Tập Phim Lẻ Hot':['phim le'],
 'Hòa Mình Cùng Các Bộ Phim Hoạt Hình Hay':['hoat hinh'],
 'Kho Tàng Anime Mới Nhất':['anime'],
}

def _cached(key,fn,ttl=600):
    now=time.time();c=_cache.get(key)
    if c and now-c[0]<ttl:return c[1]
    v=fn();_cache[key]=(now,v);return v

def _all_text(x):
    vals=[]
    for k in ('sections','genres','countries'):vals += core.tax(x,k)
    vals += [x.get('title',''),x.get('description','')]
    return core.norm(' '.join(str(v) for v in vals if v))

def _source_home():
    # Read current source home once per cache window. It is used only to preserve the exact visible order.
    return core.fetch_text(core.BASE+'/phimhay',300)

def _segment(label):
    h=_source_home();p=h.find(label)
    if p<0:return ''
    starts=[]
    for other in HOME_ROWS:
        q=h.find(other,p+len(label))
        if q>=0:starts.append(q)
    return h[p:min(starts) if starts else len(h)]

def _home_urls(label):
    seg=_segment(label)
    return core.extract_movie_urls(seg) if seg else []

def _ranked_top10_urls():
    # Current source exposes Top 10 as a finite ranking. Keep it finite; it is not a paginated category.
    seg=_segment('Top 10 Phim Hôm Nay')
    return core.extract_movie_urls(seg) if seg else []

def row_items(label):
    def build():
        urls=_ranked_top10_urls() if label=='Top 10 Phim Hôm Nay' else _home_urls(label)
        rules=ROW_RULES.get(label,[])
        # Rows with a "Xem thêm" concept expand from the already-crawled 6k catalog, so Nuvio can paginate them.
        if rules:
            for x in core.load().get('movies',[]):
                text=_all_text(x)
                if any(core.norm(r) in text for r in rules):
                    u=x.get('url')
                    if u and u not in urls:urls.append(u)
        return core.ordered(urls)
    return _cached('row:'+label,build)

def manifest_fast():
    common=[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
    cats=[]
    for i,label in enumerate(HOME_ROWS):
        cats.append({'type':'movie','id':f'ivy_home_{i}','name':f'❤️ Ivy • {label}','extra':common})
    return {
      'id':'community.ivy.catalog','version':'1.9.4','name':'Ivy❤️',
      'description':'Ivy❤️ • RoPhim current Home map • paginated expandable rows • web playback resolver',
      'resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],
      'behaviorHints':{'configurable':False},'catalogs':cats
    }

def extras_fast(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=core.unquote(v)
    for k in ('skip','search'):
        if request.args.get(k) is not None:o[k]=request.args[k]
    return o

def catalog_fast(cid,path=''):
    e=extras_fast(path);q=(e.get('search') or '').lower().strip()
    if cid.startswith('ivy_home_'):
        try:items=row_items(HOME_ROWS[int(cid.rsplit('_',1)[1])])
        except:return jsonify({'metas':[]})
    else:items=[]
    if q:items=[x for x in items if q in (core.clean(x.get('title'))+' '+core.clean(x.get('description'))).lower()]
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in items[sk:sk+PAGE_SIZE]]})

core.manifest_data=manifest_fast
core.extras=extras_fast
core.catalog=catalog_fast
core.app.view_functions['manifest']=lambda: jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid: catalog_fast(cid)
core.app.view_functions['ce']=lambda t,cid,p: catalog_fast(cid,p)
core.app.view_functions['root']=lambda: jsonify({'ok':True,'service':'Ivy❤️','version':'1.9.4','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda: jsonify({'ok':True,'version':'1.9.4','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':HOME_ROWS,'playbackResolver':'recursive-hls'})
app=core.app
