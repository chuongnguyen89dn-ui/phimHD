import json,time
from urllib.request import Request,urlopen
import app_full as core
from flask import jsonify,request

PAGE_SIZE=24
SITEMAP_URL='https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/ivy_sitemap.json'
_sitemap={'at':0,'data':None}
_manifest_cache={'at':0,'data':None}
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
    urls=list(s.get('urls') or s.get('home') or [])
    # Never crawl dozens of source pages during a Nuvio catalog request.
    # Keep the live Home Top 10 first, then extend instantly from the already
    # downloaded catalog snapshot when the sitemap has not yet published the
    # full paginated listing.
    if label=='Top 10 phim lẻ hôm nay' and len(urls)<=10:
        seen={core.canonical_movie_url(u) for u in urls}
        for x in core.load().get('movies',[]):
            if core.typ(x)!='movie':continue
            u=x.get('url')
            k=core.canonical_movie_url(u)
            if u and k not in seen:
                urls.append(u);seen.add(k)
    elif label=='Top 10 phim bộ hôm nay' and len(urls)<=10:
        seen={core.canonical_movie_url(u) for u in urls}
        for x in core.load().get('movies',[]):
            if core.typ(x)!='series':continue
            u=x.get('url')
            k=core.canonical_movie_url(u)
            if u and k not in seen:
                urls.append(u);seen.add(k)
    return materialize_urls(urls,label)

GENRE_OPTIONS=[
    'Tất cả thể loại','Hành Động','Tình Cảm','Hài Hước','Kinh Dị','Bí Ẩn',
    'Trinh Thám','Cổ Trang','Phiêu Lưu','Khoa Học Viễn Tưởng','Tâm Lý',
    'Gia Đình','Chiến Tranh','Tài Liệu','Hình Sự','Võ Thuật','Thể Thao',
    'Âm Nhạc','Hoạt Hình','Chính Kịch','Giả Tưởng'
]

def genre_options(kind=None):
    # Manifest must stay instant. Do not scan the full remote catalog here.
    return GENRE_OPTIONS

def row_extras(kind,search_required=False):
    return [
        {'name':'genre','isRequired':False,'options':genre_options(kind)},
        {'name':'skip','isRequired':False},
        {'name':'search','isRequired':search_required}
    ]

def manifest_fast():
    cats=[]
    # Search-only catalog: available in Nuvio's search catalog selector but does
    # not create a Home row because search is required.
    cats.append({
        'type':'movie',
        'id':'ivy_search_all',
        'name':'❤️ Ivy • Tất cả danh mục',
        'extra':row_extras(None,True)
    })
    # Home stays exactly equal to the 17 source sections.
    for i,row in enumerate(home_rows()):
        cats.append({
            'type':'movie',
            'id':f'ivy_home_{i}',
            'name':f'❤️ Ivy • {row}',
            'extra':row_extras(None,False)
        })
    return {
        'id':'community.ivy.catalog',
        'version':'1.11.3',
        'name':'Ivy❤️',
        'description':'Ivy❤️ • 17 danh mục nguồn; Tất cả danh mục chỉ dùng khi tìm kiếm',
        'resources':['catalog','meta','stream'],
        'types':['movie','series'],
        'idPrefixes':['ivy_'],
        'behaviorHints':{'configurable':False},
        'catalogs':cats
    }

def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=core.unquote(v)
    for k in ('skip','search','genre'):
        if request.args.get(k) is not None:o[k]=request.args[k]
    return o

def searchable_text(x):
    vals=[x.get('title',''),x.get('originalTitle',''),x.get('slug',''),x.get('description','')]
    for k in ('genres','countries','sections'):vals.extend(core.tax(x,k))
    return core.norm(' '.join(str(v or '') for v in vals))

def search_rank(x,q):
    title=core.norm(x.get('title') or '')
    original=core.norm(x.get('originalTitle') or '')
    slug=core.norm(x.get('slug') or '')
    if q==title or q==original:return 0
    if title.startswith(q) or original.startswith(q):return 1
    if q in title or q in original:return 2
    if q in slug:return 3
    return 4

def filter_rows(rows,e,kind=None):
    if kind:
        rows=[x for x in rows if core.typ(x)==kind]
    genre=(e.get('genre') or '').strip()
    if genre and genre!='Tất cả thể loại':
        ng=core.norm(genre)
        rows=[x for x in rows if any(core.norm(g)==ng for g in core.tax(x,'genres'))]
    q=core.norm(e.get('search') or '')
    if q:
        rows=[x for x in rows if q in searchable_text(x)]
        rows.sort(key=lambda x:(search_rank(x,q),core.norm(x.get('title') or x.get('slug') or '')))
    return rows

def all_items(kind):
    out=[];seen=set()
    for x in core.load().get('movies',[]):
        if core.typ(x)!=kind:continue
        k=core.canonical_movie_url(x.get('url'))
        if not k or k in seen:continue
        seen.add(k);out.append(x)
    return out

def catalog(cid,path=''):
    e=extras(path);rows=[]
    if cid=='ivy_search_all':
        rows=all_items('movie')+all_items('series')
    elif cid=='ivy_all':
        # Compatibility only for clients that cached the temporary 1.11.2 ID.
        rows=all_items('movie')+all_items('series')
    elif cid.startswith('ivy_home_'):
        try:
            idx=int(cid[len('ivy_home_'):])
            rows=items(home_rows()[idx])
        except:
            rows=[]
    # Compatibility with the temporary duplicated IDs from 1.11.0/1.11.1.
    elif cid.startswith('ivy_all_'):
        kind='series' if cid.endswith('_series') else 'movie'
        rows=all_items(kind)
    elif cid.startswith('ivy_home_movie_') or cid.startswith('ivy_home_series_'):
        kind='movie' if cid.startswith('ivy_home_movie_') else 'series'
        prefix=f'ivy_home_{kind}_'
        try:
            idx=int(cid[len(prefix):])
            rows=items(home_rows()[idx])
        except:
            rows=[]
        rows=[x for x in rows if core.typ(x)==kind]
    rows=filter_rows(rows,e,None)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in rows[sk:sk+PAGE_SIZE]]})

core.app.view_functions['manifest']=lambda:jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid:catalog(cid)
core.app.view_functions['ce']=lambda t,cid,p:catalog(cid,p)
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.11.3','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.10.1','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':home_rows(),'sitemapSections':len(sitemap().get('sections',[])),'rowSearchScope':'selected-type-category-genre','searchFilters':['type','category','genre'],'playbackResolver':'recursive-hls'})
app=core.app