import time
import app_full as core
from flask import jsonify, request

PAGE_SIZE=24
_cache={}

SECTION_RULES={
 'Điện ảnh Hàn Quốc':['han quoc','korea'],
 'Mọt phim Hoa Ngữ':['trung quoc','hoa ngu','china'],
 'Thiên đường Phim Thái':['thai lan','thailand'],
 'Phim US-UK Mới':['au my','us uk','anh','my'],
 'Phim Điện Ảnh Mới Cóng':['dien anh','chieu rap'],
 'Dấu ấn điện ảnh Việt':['viet nam','vietnam'],
 'Đêm Kinh Hoàng':['kinh di','horror'],
 'Mê Cung Phim Nhật':['nhat ban','japan'],
 'Phim Bộ Đã Hoàn Thành':['phim bo','hoan thanh'],
 'Hành Động Nghẹt Thở':['hanh dong','action'],
 'Trinh Thám & Bí Ẩn':['trinh tham','bi an','mystery'],
 'Tinh Hoa Điện Ảnh Hồng Kông':['hong kong','hongkong'],
 'Thế giới Anime':['anime'],
 'Cổ Trang Trung Quốc':['co trang'],
 'Mãn Nhãn với Phim Chiếu Rạp':['chieu rap'],
}
LIMITED={'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Sắp Lên Sóng'}

def _cached(key,fn,ttl=600):
    now=time.time();c=_cache.get(key)
    if c and now-c[0]<ttl:return c[1]
    v=fn();_cache[key]=(now,v);return v

def _all_text(x):
    vals=[]
    for k in ('sections','genres','countries'):
        vals += core.tax(x,k)
    vals += [x.get('title',''),x.get('description','')]
    return core.norm(' '.join(str(v) for v in vals if v))

def _home_urls(label):
    # The source home row is only a priority order. Full row content comes from cached catalog taxonomy.
    try:return list((core.source_home_sections().get(label) or {}).get('home') or [])
    except:return []

def source_section_items_fast(label):
    def build():
        urls=_home_urls(label)
        if label not in LIMITED:
            rules=SECTION_RULES.get(label,[])
            if rules:
                for x in core.load().get('movies',[]):
                    text=_all_text(x)
                    if any(core.norm(r) in text for r in rules):
                        u=x.get('url')
                        if u and u not in urls:urls.append(u)
        return core.ordered(urls)
    return _cached('section:'+label,build)

def source_menu_fast(kind):
    def build():
        data=core.load();rows=data.get('movies',[]);stored=(data.get('sourceOrders') or {}).get('series' if kind=='series' else 'movies') or []
        items=core.ordered(stored,lambda x:core.typ(x)==kind);seen={x.get('url') for x in items}
        for x in rows:
            if core.typ(x)==kind and x.get('url') not in seen:
                items.append(x);seen.add(x.get('url'))
        return core.dedupe_series(items) if kind=='series' else items
    return _cached('menu:'+kind,build)

def manifest_fast():
    common=[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
    cats=[
      {'type':'movie','id':'ivy_movies','name':'❤️ Ivy • Phim Lẻ','extra':common},
      {'type':'series','id':'ivy_series','name':'❤️ Ivy • Phim Bộ','extra':common},
    ]
    # Exact Home map supplied from the source site. No network crawl is done while serving manifest.
    for i,label in enumerate(core.SOURCE_SECTIONS):
        cats.append({'type':'series' if label in core.SERIES_SECTIONS else 'movie','id':f'ivy_src_{i}','name':f'❤️ Ivy • {label}','extra':common})
    return {
      'id':'community.ivy.catalog','version':'1.9.3','name':'Ivy❤️',
      'description':'Ivy❤️ • source sitemap rows • 24 items/page • cached catalog • web playback resolver',
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
    if cid=='ivy_movies':items=source_menu_fast('movie')
    elif cid=='ivy_series':items=source_menu_fast('series')
    elif cid.startswith('ivy_src_'):
        try:items=source_section_items_fast(core.SOURCE_SECTIONS[int(cid.rsplit('_',1)[1])])
        except:return jsonify({'metas':[]})
    else:items=[]
    if q:
        items=[x for x in items if q in (core.clean(x.get('title'))+' '+core.clean(x.get('description'))).lower()]
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    # Nuvio loads more with skip=24, skip=48... instead of downloading 100 cards at once.
    return jsonify({'metas':[core.base_meta(x) for x in items[sk:sk+PAGE_SIZE]]})

core.source_section_items=source_section_items_fast
core.source_menu=source_menu_fast
core.manifest_data=manifest_fast
core.extras=extras_fast
core.catalog=catalog_fast
core.cp=lambda t,cid: catalog_fast(cid)
core.ce=lambda t,cid,p: catalog_fast(cid,p)

# Flask routes were registered with old function objects; replace their view functions explicitly.
core.app.view_functions['manifest']=lambda: jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid: catalog_fast(cid)
core.app.view_functions['ce']=lambda t,cid,p: catalog_fast(cid,p)
core.app.view_functions['root']=lambda: jsonify({'ok':True,'service':'Ivy❤️','version':'1.9.3','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda: jsonify({'ok':True,'version':'1.9.3','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'legacyFranchiseCatalog':False,'playbackResolver':'recursive-hls'})

app=core.app
