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

def items(label):
    s=section(label);home=core.ordered(s.get('home') or [])
    if label=='Top 10 phim lẻ hôm nay':
        full=core.source_menu('movie')
    elif label=='Top 10 phim bộ hôm nay':
        full=core.source_menu('series')
    else:
        return core.ordered(s.get('urls') or s.get('home') or [])
    out=[];seen=set()
    for x in home+full:
        u=x.get('url')
        if u and u not in seen:seen.add(u);out.append(x)
    return out

def genre_options():
    out=[]
    for x in core.load().get('movies',[]):
        for g in core.tax(x,'genres'):
            g=core.clean(g)
            if g and g not in out:out.append(g)
    return ['Tất cả thể loại']+sorted(out,key=lambda s:core.norm(s))

def row_extras():return [{'name':'genre','isRequired':False,'options':genre_options()},{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]

def catalog_id(label):return 'ivy_home_'+core.enc(label)

def manifest_fast():
    cats=[]
    for label in home_rows():cats.append({'type':'series' if label in SERIES_ROWS else 'movie','id':catalog_id(label),'name':f'❤️ Ivy • {label}','extra':row_extras()})
    return {'id':'community.ivy.catalog','version':'1.10.0','name':'Ivy❤️','description':'Ivy❤️ • source rows only • exact source membership • Nuvio search + genre filters','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

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
        label=None
        # Backward compatibility for old index-based catalog IDs already cached by Nuvio.
        if token.isdigit():
            try:label=home_rows()[int(token)]
            except:label=None
        else:
            try:label=core.dec(token)
            except:label=None
        if label in home_rows():rows=items(label)
        rows=filter_rows(rows,e)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':[core.base_meta(x) for x in rows[sk:sk+PAGE_SIZE]]})

core.app.view_functions['manifest']=lambda:jsonify(manifest_fast())
core.app.view_functions['cp']=lambda t,cid:catalog(cid)
core.app.view_functions['ce']=lambda t,cid,p:catalog(cid,p)
core.app.view_functions['root']=lambda:jsonify({'ok':True,'service':'Ivy❤️','version':'1.10.0','manifest':'/manifest.json'})
core.app.view_functions['health']=lambda:jsonify({'ok':True,'version':'1.9.9','movies':len(core.load().get('movies',[])),'pageSize':PAGE_SIZE,'homeRows':home_rows(),'sitemapSections':len(sitemap().get('sections',[])),'rowSearchScope':'source-row','searchFilters':['genre'],'playbackResolver':'recursive-hls'})
app=core.app