import json, os, base64, re, time, html
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request

CATALOG=os.environ.get('IVY_CATALOG',os.environ.get('ROPHIM_CATALOG','rophim_catalog.json'))
REMOTE_CATALOG=os.environ.get('IVY_REMOTE_CATALOG','https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/rophim_catalog.json')
BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/')
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
app=Flask(__name__)
_page_cache={};_order_cache={};_catalog_cache={'at':0,'data':None}

def _local_catalog():
    try:
        with open(CATALOG,encoding='utf-8') as f:return json.load(f)
    except:return {'movies':[]}
def load():
    now=time.time()
    if _catalog_cache['data'] is not None and now-_catalog_cache['at']<900:return _catalog_cache['data']
    fallback=_catalog_cache['data'] or _local_catalog()
    try:
        req=Request(REMOTE_CATALOG+'?t='+str(int(now//900)),headers={'User-Agent':UA,'Accept':'application/json'})
        with urlopen(req,timeout=8) as r:data=json.loads(r.read().decode('utf-8'))
        if isinstance(data,dict) and len(data.get('movies',[]))>100:
            _catalog_cache.update(at=now,data=data);return data
    except:pass
    _catalog_cache.update(at=now,data=fallback);return fallback

def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')
def dec(s):
    try:s+='='*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
    except:return ''
def mid(x):return 'ivy_'+enc(x.get('url',''))
def clean(s):
    s=html.unescape(re.sub(r'(?i)r[oổ]phim','Ivy❤️',str(s or '')))
    return re.sub(r'\s+',' ',s).split(' - Xem ')[0].split(' | Ivy❤️')[0].strip()
def tax(x,k):return (x.get('taxonomy') or {}).get(k) or x.get(k) or []
def typ(x):
    text=' '.join([str(x.get('title','')),str(x.get('duration',''))]+tax(x,'sections')+tax(x,'genres')).lower()
    return 'series' if x.get('type')=='series' or any(k in text for k in ['phim bộ','tv shows','/tập','m/tập','season ','phần ']) else 'movie'
def year(x):
    ys=re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)',clean(x.get('title','')))
    if ys:return int(ys[-1])
    y=x.get('year');y=int(y) if str(y).isdigit() else 0
    return y if 1900<=y<=2100 and y!=2026 else None

def fetch_text(u,ttl=300):
    now=time.time();c=_page_cache.get(u)
    if c and now-c[0]<ttl:return c[1]
    try:
        with urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Referer':BASE+'/'}),timeout=18) as r:s=r.read().decode('utf-8','replace').replace('\\/','/')
        _page_cache[u]=(now,s);return s
    except:return ''
def live_source_order(path):
    u=BASE+path;now=time.time();c=_order_cache.get(u)
    if c and now-c[0]<600:return c[1]
    h=fetch_text(u,300);out=[]
    for href in re.findall(r'href=["\']([^"\']+)',h,re.I):
        if '/phim/' not in href:continue
        v=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
        if v not in out:out.append(v)
    if out:_order_cache[u]=(now,out)
    return out
def source_order(kind):
    d=load();stored=(d.get('sourceOrders') or {}).get(kind) or []
    if stored:return stored
    path={'home':'/phimhay','movies':'/phim-le','series':'/phim-bo'}.get(kind,'/phimhay')
    return live_source_order(path)

def infer_season(x,h=''):
    text=' '.join([clean(x.get('title','')),clean(h[:20000])])
    for pat in [r'(?i)(?:phần|season)\s*(\d+)',r'(?i)S(\d{1,2})(?:E\d+)?']:
        m=re.search(pat,text)
        if m:return max(1,int(m.group(1)))
    return 1
def extract_array_after(h,marker):
    p=h.find(marker)
    if p<0:return None
    p=h.find('[',p)
    if p<0:return None
    depth=0;quote=None;esc=False
    for i in range(p,len(h)):
        ch=h[i]
        if quote:
            if esc:esc=False
            elif ch=='\\':esc=True
            elif ch==quote:quote=None
            continue
        if ch in ('"',"'"):quote=ch;continue
        if ch=='[':depth+=1
        elif ch==']':
            depth-=1
            if depth==0:
                try:return json.loads(h[p:i+1])
                except:return None
    return None
def episode_servers(x):
    h=fetch_text(x.get('url',''),180);arr=extract_array_after(h,'var episodes =') or extract_array_after(h,'episodes =') or [];out=[]
    if isinstance(arr,list):
        for srv in arr:
            if not isinstance(srv,dict):continue
            data=srv.get('server_data') or []
            if isinstance(data,list):out.append((clean(srv.get('server_name') or srv.get('name') or 'Nguồn'),data))
    return h,out
def episode_rows(x):
    h,servers=episode_servers(x);season=infer_season(x,h);by={}
    for sname,data in servers:
        for item in data:
            if not isinstance(item,dict):continue
            slug=str(item.get('slug') or '');name=clean(item.get('name') or item.get('filename') or slug);m=re.search(r'(\d+)',slug+' '+name)
            if not m:continue
            ep=int(m.group(1));row=by.setdefault(ep,{'episode':ep,'title':name or f'Tập {ep}','sources':[]})
            u=item.get('link_m3u8') or item.get('link_embed') or ''
            if u:row['sources'].append({'name':sname,'url':u})
    return season,[by[k] for k in sorted(by)]

def base_meta(x,full=False):
    m={'id':mid(x),'type':typ(x),'name':clean(x.get('title') or x.get('slug') or 'Ivy❤️'),'poster':x.get('poster') or None,'background':x.get('backdrop') or None,'description':clean(x.get('description')),'website':x.get('url'),'posterShape':'poster'}
    y=year(x)
    if y:m['releaseInfo']=str(y)
    if tax(x,'genres'):m['genres']=tax(x,'genres')
    if tax(x,'countries'):m['country']=', '.join(tax(x,'countries'))
    if x.get('duration'):m['runtime']=x['duration']
    tm=x.get('tmdb') or {}
    if tm.get('voteAverage') is not None:
        m['rating']=round(float(tm['voteAverage']),1);m['voteCount']=tm.get('voteCount')
    if full and m['type']=='series':
        season,eps=episode_rows(x);videos=[]
        for e in eps:videos.append({'id':f"{m['id']}:{season}:{e['episode']}",'title':e['title'],'season':season,'episode':e['episode'],'overview':clean(x.get('description')),'thumbnail':x.get('backdrop') or x.get('poster')})
        if videos:m['videos']=videos
    return m

def data_index():
    d=load().get('movies',[]);return d,{x.get('url'):x for x in d if x.get('url')}
def ordered_from_urls(urls,predicate=None,include_tail=True):
    data,by=data_index();seen=set();out=[]
    for u in urls:
        x=by.get(u)
        if x and (predicate is None or predicate(x)) and u not in seen:out.append(x);seen.add(u)
    if include_tail:
        tail=[x for x in data if x.get('url') not in seen and (predicate is None or predicate(x))]
        tail.sort(key=lambda x:(-(year(x) or 0),clean(x.get('title','')).lower()));out.extend(tail)
    return out
def latest_items(kind):
    # "Mới cập nhật" follows the source's /phimhay update feed, then filters movie/series.
    pred=(lambda x:typ(x)==kind)
    return ordered_from_urls(source_order('home'),pred,True)
def ranked_items(key,kind=None):
    d=load();by={x.get('url'):x for x in d.get('movies',[]) if x.get('url')};out=[]
    for u in (d.get('tmdbRankings') or {}).get(key,[]):
        x=by.get(u)
        if x and (kind is None or typ(x)==kind):out.append(x)
    return out

def genre_options(data):
    preferred=['Hành Động','Action','Phiêu Lưu','Adventure','Hoạt Hình','Animation','Hài','Comedy','Chính Kịch','Drama','Kinh Dị','Horror','Bí Ẩn','Mystery','Hình Sự','Crime','Tình Cảm','Romance','Khoa Học','Science Fiction','Gia Đình','Family','Chiến Tranh','War','Lịch Sử','History','Tài Liệu','Documentary']
    found=[]
    for x in data:
        for g in tax(x,'genres'):
            if g and g not in found:found.append(g)
    out=[p for p in preferred if p in found];out.extend(sorted(g for g in found if g not in out));return out

def manifest_data():
    d=load();data=d.get('movies',[]);genres=genre_options(data);common=[{'name':'genre','isRequired':False,'options':genres},{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
    cats=[
      {'type':'movie','id':'ivy_latest_movies','name':'❤️ Ivy • Phim Lẻ Mới Cập Nhật','extra':common},
      {'type':'series','id':'ivy_latest_series','name':'❤️ Ivy • Phim Bộ Mới Cập Nhật','extra':common}]
    ranks=d.get('tmdbRankings') or {}
    if ranks.get('trendingMovies'):cats.append({'type':'movie','id':'ivy_trending_movies','name':'🔥 Ivy • Phim Đang Thịnh Hành','extra':common})
    if ranks.get('trendingSeries'):cats.append({'type':'series','id':'ivy_trending_series','name':'🔥 Ivy • Series Đang Thịnh Hành','extra':common})
    if ranks.get('popularMovies'):cats.append({'type':'movie','id':'ivy_popular_movies','name':'🎬 Ivy • Phim Phổ Biến','extra':common})
    if ranks.get('popularSeries'):cats.append({'type':'series','id':'ivy_popular_series','name':'📺 Ivy • Series Phổ Biến','extra':common})
    if ranks.get('topRatedMovies'):cats.append({'type':'movie','id':'ivy_top_movies','name':'⭐ Ivy • Phim Đánh Giá Cao','extra':common})
    if ranks.get('topRatedSeries'):cats.append({'type':'series','id':'ivy_top_series','name':'⭐ Ivy • Series Đánh Giá Cao','extra':common})
    cats.append({'type':'series','id':'ivy_franchises','name':'❤️ Ivy • Loạt Phim','extra':common})
    return {'id':'community.ivy.catalog','version':'1.4.1','name':'Ivy❤️','description':'Ivy❤️ • source playback with objective discovery','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

@app.get('/')
def root():return jsonify({'ok':True,'service':'Ivy❤️','version':'1.4.1','manifest':'/manifest.json'})
@app.get('/manifest.json')
def manifest():return jsonify(manifest_data())
@app.get('/health')
def health():
    d=load();return jsonify({'ok':True,'version':'1.4.1','movies':len(d.get('movies',[])),'catalogGeneratedAt':d.get('generatedAt'),'tmdbMatchedCount':d.get('tmdbMatchedCount',0),'homeOrder':len(source_order('home'))})
def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=unquote(v)
    for k in ('skip','search','genre'):
        if request.args.get(k)!=None:o[k]=request.args[k]
    return o
def catalog(cid,path=''):
    e=extras(path);q=(e.get('search') or '').lower().strip()
    if cid=='ivy_latest_movies':items=latest_items('movie')
    elif cid=='ivy_latest_series':items=latest_items('series')
    elif cid=='ivy_trending_movies':items=ranked_items('trendingMovies','movie')
    elif cid=='ivy_trending_series':items=ranked_items('trendingSeries','series')
    elif cid=='ivy_popular_movies':items=ranked_items('popularMovies','movie')
    elif cid=='ivy_popular_series':items=ranked_items('popularSeries','series')
    elif cid=='ivy_top_movies':items=ranked_items('topRatedMovies','movie')
    elif cid=='ivy_top_series':items=ranked_items('topRatedSeries','series')
    elif cid=='ivy_franchises':items=ordered_from_urls(source_order('series'),lambda x:typ(x)=='series' and re.search(r'(?i)(phần|season)\s*\d+',clean(x.get('title',''))),True)
    else:items=[]
    out=[]
    for x in items:
        if e.get('genre') and e['genre'] not in tax(x,'genres'):continue
        m=base_meta(x)
        if q and q not in (m['name']+' '+m.get('description','')).lower():continue
        out.append(m)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':out[sk:sk+100]})

@app.get('/catalog/<t>/<cid>.json')
def cp(t,cid):return catalog(cid)
@app.get('/catalog/<t>/<cid>/<path:p>.json')
def ce(t,cid,p):return catalog(cid,p)
@app.get('/meta/<t>/<path:item_id>.json')
def meta_route(t,item_id):
    base=item_id.split(':',1)[0];u=dec(base[4:]) if base.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),None)
    return jsonify({'meta':base_meta(x,True) if x else None})
@app.get('/stream/<t>/<path:item_id>.json')
def stream(t,item_id):
    parts=item_id.split(':');base=parts[0];u=dec(base[4:]) if base.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),None)
    if not x:return jsonify({'streams':[]})
    if len(parts)>=3 and typ(x)=='series':
        try:ep=int(parts[-1])
        except:return jsonify({'streams':[]})
        _,rows=episode_rows(x);row=next((r for r in rows if r['episode']==ep),None)
        if not row:return jsonify({'streams':[]})
        return jsonify({'streams':[{'name':'Ivy❤️','title':f"Ivy❤️ • {row['title']} • {s['name']}",'url':s['url'],'behaviorHints':{'notWebReady':True}} for s in row['sources']]})
    urls=list(dict.fromkeys(HLS_RE.findall(fetch_text(u,120))))
    return jsonify({'streams':[{'name':'Ivy❤️','title':'Ivy❤️ • Phát' if i==0 else f'Ivy❤️ • Nguồn {i+1}','url':v,'behaviorHints':{'notWebReady':True}} for i,v in enumerate(urls)]})

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
