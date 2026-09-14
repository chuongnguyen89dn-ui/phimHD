import json,time
from urllib.request import Request,urlopen
import app_full as core
from flask import jsonify,request

PAGE_SIZE=24
SITEMAP_URL='https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/ivy_sitemap.json'
_sitemap={'at':0,'data':None}
HOME_ROWS=[
 'Điện ảnh Hàn Quốc','Mọt phim Hoa Ngữ','Thiên đường Phim Thái','Phim US-UK Mới',
 'Phim Điện Ảnh Mới Cóong','Dấu ấn điện ảnh Việt','Đêm Kinh Hoàng','Mê Cung Phim Nhật',
 'Phim Bộ Đã Hoàn Thành','Hành Động Nghẹt Thở','Trinh Thám & Bí Ẩn','Tinh Hoa Điện Ảnh Hồng Kông',
 'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Thế giới Anime','Cổ Trang Trung Quốc',
 'Mãn Nhãn với Phim Chiếu Rạp','Sắp Lên Sóng'
]
SERIES_ROWS={'Phim Bộ Đã Hoàn Thành','Top 10 phim bộ hôm nay'}

def sitemap():
    now=time.time()
    if _sitemap['data'] is not None and now-_sitemap['at']<900:return _sitemap['data']
    try:
        req=Request(SITEMAP_URL+'?t='+str(int(now//900)),headers={'User-Agent':core.UA,'Accept':'application/json'})
        with urlopen(req,timeout=8) as r:d=json.loads(r.read().decode('utf-8'))
        if isinstance(d,dict) and d.get('sections'):_sitemap.update(at=now,data=d);return d
    except Exception:pass
    # Safe fallback: preserve all source rows even before the first sitemap job finishes.
    d={'sections':[]}
    try:
        src=core.source_home_sections()
        for label in HOME_ROWS:
            info=src.get(label) or {};d['sections'].append({'label':label,'home':info.get('home') or [],'urls':info.get('home') or [],'pages':1,'listing':info.get('listing')})
    except Exception:
        for label in HOME_ROWS:d['sections'].append({'label':label,'home':[],'urls':[],'pages':1})
    _sitemap.update(at=now,data=d);return d

def section(label):
    for s in sitemap().get('sections',[]):
        if s.get('label')==label:return s
    return {'label':label,'urls':[],'pages':1}

def items(label):
    return core.ordered(section(label).get('urls') or section(label).get('home') or [])

def manifest_fast():
    common=[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
    cats=[]
    for i,label in enumerate(HOME_ROWS):
        cats.append({'type':'series' if label in SERIES_ROWS else 'movie','id':f'ivy_home_{i}','name':f'❤️ Ivy • {label}','extra':common})
    return {'id':'community.ivy.catalog','version':'1.9.5','name':'Ivy❤️','description':'Ivy❤️ • exact source home rows • full source pagination cached offline','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=core.unquote(v)
    for k in ('skip','search'):
        if request.args.get(k) is not None:o[k]=request.args[k]
    return o

def catalog(cid,path=''):
    e=extras(path);q=(e.get('search') or '').lower().strip();rows=[]
    if cid.startswith('ivy_home_'):
        try:rows=items(HOME_ROWS[int(cid.rsplit('_',1)[1])])
        except:rows=[]
    if q:rows=[x for x in rows if q in (core.clean(x.get('title'))+' '+core.clean(x.get('description'))).lower()]
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in rows[sk:sk+PAGE_SIZE]]})

core.app.view_functions['manifest']=lambda:jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid:catalog(cid)
core.app.view_functions['ce']=lambda t,cid,p:catalog(cid,p)
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.9.5','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.9.5','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':HOME_ROWS,'sitemapSections':len(sitemap().get('sections',[])),'playbackResolver':'recursive-hls'})
app=core.app
