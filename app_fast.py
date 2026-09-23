import json,time
from urllib.request import Request,urlopen
import app_full as core
from flask import jsonify,request

PAGE_SIZE=24
SITEMAP_URL='https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/ivy_sitemap.json'
_sitemap={'at':0,'data':None}
FALLBACK_HOME_ROWS=['Điện ảnh Hàn Quốc','Mọt phim Hoa Ngữ','Thiên đường Phim Thái','Phim US-UK Mới','Phim Điện Ảnh Mới Cóng','Dấu ấn điện ảnh Việt','Đêm Kinh Hoàng','Mê Cung Phim Nhật','Phim Bộ Đã Hoàn Thành','Hành Động Nghẹt Thở','Trinh Thám & Bí Ẩn','Tinh Hoa Điện Ảnh Hồng Kông','Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Thế giới Anime','Cổ Trang Trung Quốc','Mãn Nhãn với Phim Chiếu Rạp','Sắp Lên Sóng']
SERIES_ROWS={'Phim Bộ Đã Hoàn Thành','Top 10 phim bộ hôm nay'}

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
        for label in FALLBACK_HOME_ROWS:
            info=src.get(label) or {};d['sections'].append({'label':label,'home':info.get('home') or [],'urls':info.get('home') or [],'pages':1,'listing':info.get('listing')})
    except Exception:
        for label in FALLBACK_HOME_ROWS:d['sections'].append({'label':label,'home':[],'urls':[],'pages':1})
    _sitemap.update(at=now,data=d);return d

def home_rows():
    rows=[s.get('label') for s in sitemap().get('sections',[]) if s.get('label')]
    return rows or FALLBACK_HOME_ROWS

def section(label):
    for s in sitemap().get('sections',[]):
        if s.get('label')==label:return s
    return {'label':label,'urls':[],'pages':1}

def _stub(u,label):
    slug=str(u or '').rstrip('/').split('/')[-1]
    name=slug.replace('-',' ').strip().title() or 'Ivy❤️'
    return {'url':u,'slug':slug,'title':name,'type':'series' if label in SERIES_ROWS else 'movie','source':'runtime-fallback'}

def materialize_urls(urls,label):
    urls=[u for u in (urls or []) if u]
    known=core.ordered(urls)
    by={core.canonical_movie_url(x.get('url')):x for x in known if x.get('url')}
    out=[]
    for u in urls:
        k=core.canonical_movie_url(u)
        out.append(by.get(k) or _stub(u,label))
    return out

def items(label):
    s=section(label)
    if label=='Top 10 phim lẻ hôm nay':
        home=s.get('home') or []
        listing=s.get('listing') or core.BASE+'/phim-le'
        urls=list(home)
        for u in core.crawl_listing(listing,max_pages=60):
            if u not in urls:urls.append(u)
        return materialize_urls(urls,label)
    if label=='Top 10 phim bộ hôm nay':
        home=s.get('home') or []
        listing=s.get('listing') or core.BASE+'/phim-bo'
        urls=list(home)
        for u in core.crawl_listing(listing,max_pages=60):
            if u not in urls:urls.append(u)
        return materialize_urls(urls,label)
    return materialize_urls(s.get('urls') or s.get('home') or [],label)

def genre_options():
    out=[]
    for x in core.load().get('movies',[]):
        for g in core.tax(x,'genres'):
            g=core.clean(g)
            if g and g not in out:out.append(g)
    return ['Tất cả thể loại']+sorted(out,key=lambda s:core.norm(s))

def row_extras():return [{'name':'genre','isRequired':False,'options':genre_options()},{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]

def manifest_fast():
    cats=[]
    for i,label in enumerate(home_rows()):
        cats.append({'type':'series' if label in SERIES_ROWS else 'movie','id':f'ivy_home_{i}','name':f'❤️ Ivy • {label}','extra':row_extras()})
    return {'id':'community.ivy.catalog','version':'1.10.2','name':'Ivy❤️','description':'Ivy❤️ • source rows only • exact source membership • Nuvio search + genre filters','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=core.unquote(v)
    for k in ('skip','search','genre'):
        if request.args.get(k) is not None:o[k]=request.args[k]
    return o

def searchable_text(x):
    vals=[x.get('title',''),x.get('description',''),x.get('slug',''),x.get('originalTitle','')]
    for k in ('genres','countries','sections'):vals.extend(core.tax(x,k))
    return core.norm(' '.join(str(v or '') for v in vals))

def filter_rows(rows,e):
    genre=(e.get('genre') or '').strip()
    if genre and genre!='Tất cả thể loại':
        ng=core.norm(genre);rows=[x for x in rows if any(core.norm(g)==ng for g in core.tax(x,'genres'))]
    q=core.norm(e.get('search') or '')
    if q:rows=[x for x in rows if q in searchable_text(x)]
    return rows

def catalog(cid,path=''):
    e=extras(path);rows=[]
    if cid.startswith('ivy_home_'):
        token=cid[len('ivy_home_'):]
        try:
            label=home_rows()[int(token)]
            rows=items(label)
        except:
            rows=[]
        rows=filter_rows(rows,e)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in rows[sk:sk+PAGE_SIZE]]})

core.app.view_functions['manifest']=lambda:jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid:catalog(cid)
core.app.view_functions['ce']=lambda t,cid,p:catalog(cid,p)
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.10.1','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.10.1','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':home_rows(),'sitemapSections':len(sitemap().get('sections',[])),'rowSearchScope':'source-row','searchFilters':['genre'],'playbackResolver':'recursive-hls'})
app=core.app