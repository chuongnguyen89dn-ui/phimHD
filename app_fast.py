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
CATEGORY_OPTIONS=['Tất cả']+HOME_ROWS

def sitemap():
    now=time.time()
    if _sitemap['data'] is not None and now-_sitemap['at']<900:return _sitemap['data']
    try:
        req=Request(SITEMAP_URL+'?t='+str(int(now//900)),headers={'User-Agent':core.UA,'Accept':'application/json'})
        with urlopen(req,timeout=8) as r:d=json.loads(r.read().decode('utf-8'))
        if isinstance(d,dict) and d.get('sections'):_sitemap.update(at=now,data=d);return d
    except Exception:pass
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

def items(label):return core.ordered(section(label).get('urls') or section(label).get('home') or [])

def genre_options():
    out=[]
    for x in core.load().get('movies',[]):
        for g in core.tax(x,'genres'):
            g=core.clean(g)
            if g and g not in out:out.append(g)
    return ['Tất cả thể loại']+sorted(out,key=lambda s:core.norm(s))

def search_extras():return [{'name':'search','isRequired':False},{'name':'category','isRequired':False,'options':CATEGORY_OPTIONS},{'name':'genre','isRequired':False,'options':genre_options()},{'name':'skip','isRequired':False}]
def row_extras():return [{'name':'genre','isRequired':False,'options':genre_options()},{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]

def manifest_fast():
    cats=[{'type':'movie','id':'ivy_search_movies','name':'❤️ Ivy • Tìm toàn bộ phim lẻ','extra':search_extras()},{'type':'series','id':'ivy_search_series','name':'❤️ Ivy • Tìm toàn bộ phim bộ','extra':search_extras()}]
    for i,label in enumerate(HOME_ROWS):cats.append({'type':'series' if label in SERIES_ROWS else 'movie','id':f'ivy_home_{i}','name':f'❤️ Ivy • {label}','extra':row_extras()})
    return {'id':'community.ivy.catalog','version':'1.9.8','name':'Ivy❤️','description':'Ivy❤️ • exact source catalog membership • native Nuvio filters • full-library search','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=core.unquote(v)
    for k in ('skip','search','genre','category'):
        if request.args.get(k) is not None:o[k]=request.args[k]
    return o

def searchable_text(x):
    vals=[x.get('title',''),x.get('description',''),x.get('slug',''),x.get('originalTitle','')]
    for k in ('genres','countries','sections'):vals.extend(core.tax(x,k))
    return core.norm(' '.join(str(v or '') for v in vals))

def all_library(kind):
    rows=[];seen=set()
    for x in core.load().get('movies',[]):
        if core.typ(x)!=kind:continue
        u=x.get('url')
        if not u or u in seen:continue
        seen.add(u);rows.append(x)
    return core.dedupe_series(rows) if kind=='series' else rows

def filter_rows(rows,e):
    cat=(e.get('category') or '').strip()
    if cat and cat!='Tất cả':
        allowed={x.get('url') for x in items(cat)};rows=[x for x in rows if x.get('url') in allowed]
    genre=(e.get('genre') or '').strip()
    if genre and genre!='Tất cả thể loại':
        ng=core.norm(genre);rows=[x for x in rows if any(core.norm(g)==ng for g in core.tax(x,'genres'))]
    q=core.norm(e.get('search') or '')
    if q:rows=[x for x in rows if q in searchable_text(x)]
    return rows

def catalog(cid,path=''):
    e=extras(path);rows=[]
    if cid=='ivy_search_movies':rows=filter_rows(all_library('movie'),e)
    elif cid=='ivy_search_series':rows=filter_rows(all_library('series'),e)
    elif cid.startswith('ivy_home_'):
        try:label=HOME_ROWS[int(cid.rsplit('_',1)[1])];rows=items(label)
        except:rows=[]
        # Critical: searching a source row must stay inside that row. Nuvio queries every
        # catalog independently, so replacing rows with all_library duplicated every hit
        # under Korea/China/Thailand/etc.
        rows=filter_rows(rows,e)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in rows[sk:sk+PAGE_SIZE]]})

core.app.view_functions['manifest']=lambda:jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid:catalog(cid)
core.app.view_functions['ce']=lambda t,cid,p:catalog(cid,p)
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.9.8','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.9.8','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':HOME_ROWS,'sitemapSections':len(sitemap().get('sections',[])),'searchScope':'full-library','rowSearchScope':'source-row','searchFilters':['category','genre'],'playbackResolver':'recursive-hls'})
app=core.app