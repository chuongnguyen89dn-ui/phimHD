import json, os, base64, re, time, html
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request

CATALOG=os.environ.get('IVY_CATALOG',os.environ.get('ROPHIM_CATALOG','rophim_catalog.json'))
BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/')
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
app=Flask(__name__)
_page_cache={}
_order_cache={}

def load():
    try:
        with open(CATALOG,encoding='utf-8') as f:return json.load(f)
    except:return {'movies':[]}

def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')
def dec(s):
    try:
        s+='='*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
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

def source_order(path):
    u=BASE+path;now=time.time();c=_order_cache.get(u)
    if c and now-c[0]<600:return c[1]
    h=fetch_text(u,300);out=[]
    for href in re.findall(r'href=["\']([^"\']+)',h,re.I):
        if '/phim/' not in href:continue
        v=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
        if v not in out:out.append(v)
    if out:_order_cache[u]=(now,out)
    return out

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
    h=fetch_text(x.get('url',''),180)
    arr=extract_array_after(h,'var episodes =') or extract_array_after(h,'episodes =') or []
    out=[]
    if isinstance(arr,list):
        for srv in arr:
            if not isinstance(srv,dict):continue
            name=clean(srv.get('server_name') or srv.get('name') or 'Nguồn')
            data=srv.get('server_data') or []
            if isinstance(data,list):
                out.append((name,data))
    return h,out

def episode_rows(x):
    h,servers=episode_servers(x);season=infer_season(x,h);by={}
    for sname,data in servers:
        for item in data:
            if not isinstance(item,dict):continue
            slug=str(item.get('slug') or '');name=clean(item.get('name') or item.get('filename') or slug)
            m=re.search(r'(\d+)',slug+' '+name)
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
    if full and m['type']=='series':
        season,eps=episode_rows(x);videos=[]
        for e in eps:
            videos.append({'id':f"{m['id']}:{season}:{e['episode']}",'title':e['title'],'season':season,'episode':e['episode'],'overview':clean(x.get('description')),'thumbnail':x.get('backdrop') or x.get('poster')})
        if videos:m['videos']=videos
    return m

def data_index():
    d=load().get('movies',[]);return d,{x.get('url'):x for x in d if x.get('url')}
def ordered_items(path,predicate=None):
    data,by=data_index();seen=set();out=[]
    for u in source_order(path):
        x=by.get(u)
        if x and (predicate is None or predicate(x)) and u not in seen:out.append(x);seen.add(u)
    if not out:
        out=[x for x in data if predicate is None or predicate(x)]
    return out

def manifest_data():
    data,_=data_index();genres=sorted({g for x in data for g in tax(x,'genres') if g});countries=sorted({g for x in data for g in tax(x,'countries') if g})
    return {'id':'community.ivy.catalog','version':'1.0.0','name':'Ivy❤️','description':'Ivy❤️ • Movies, series, seasons and episodes','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':[
      {'type':'movie','id':'ivy_latest','name':'❤️ Ivy • Phim Mới Cập Nhật','extra':[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]},
      {'type':'movie','id':'ivy_movies','name':'❤️ Ivy • Phim Lẻ','extra':[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]},
      {'type':'series','id':'ivy_series','name':'❤️ Ivy • Phim Bộ','extra':[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]},
      {'type':'series','id':'ivy_franchises','name':'❤️ Ivy • Loạt Phim','extra':[{'name':'skip','isRequired':False}]},
      {'type':'movie','id':'ivy_genres','name':'❤️ Ivy • Thể loại','extra':[{'name':'genre','isRequired':True,'options':genres},{'name':'skip','isRequired':False}]},
      {'type':'movie','id':'ivy_countries','name':'❤️ Ivy • Quốc gia','extra':[{'name':'country','isRequired':True,'options':countries},{'name':'skip','isRequired':False}]}
    ]}

@app.get('/')
def root():return jsonify({'ok':True,'service':'Ivy❤️','version':'1.0.0','manifest':'/manifest.json'})
@app.get('/manifest.json')
def manifest():return jsonify(manifest_data())
@app.get('/health')
def health():
    d=load();return jsonify({'ok':True,'version':'1.0.0','movies':len(d.get('movies',[])),'latest':len(source_order('/phimhay')),'movieOrder':len(source_order('/phim-le')),'seriesOrder':len(source_order('/phim-bo'))})

def extras(path=''):
    o={}
    for p in path.split('/'):
        if '=' in p:
            k,v=p.split('=',1);o[k]=unquote(v)
    for k in ('skip','search','genre','country'):
        if request.args.get(k)!=None:o[k]=request.args[k]
    return o

def catalog(cid,path=''):
    e=extras(path);q=(e.get('search') or '').lower().strip()
    if cid=='ivy_latest':items=ordered_items('/phimhay')
    elif cid=='ivy_movies':items=ordered_items('/phim-le',lambda x:typ(x)=='movie')
    elif cid=='ivy_series':items=ordered_items('/phim-bo',lambda x:typ(x)=='series')
    elif cid=='ivy_franchises':items=ordered_items('/phim-bo',lambda x:typ(x)=='series' and re.search(r'(?i)(phần|season)\s*\d+',clean(x.get('title',''))))
    else:items=load().get('movies',[])
    out=[]
    for x in items:
        if e.get('genre') and e['genre'] not in tax(x,'genres'):continue
        if e.get('country') and e['country'] not in tax(x,'countries'):continue
        m=base_meta(x)
        if q and q not in (m['name']+' '+m.get('description','')).lower():continue
        out.append(m)
    try:sk=max(0,int(e.get('skip',0)))
    except:sk=0
    return jsonify({'metas':out[sk:sk+100]})

@app.get('/catalog/<t>/<cid>.json')
def cat_plain(t,cid):return catalog(cid)
@app.get('/catalog/<t>/<cid>/<path:p>.json')
def cat_extra(t,cid,p):return catalog(cid,p)
@app.get('/meta/<t>/<path:item_id>.json')
def meta_route(t,item_id):
    base=item_id.split(':',1)[0];u=dec(base[4:]) if base.startswith('ivy_') else ''
    x=next((x for x in load().get('movies',[]) if x.get('url')==u),None)
    return jsonify({'meta':base_meta(x,True) if x else None})

@app.get('/stream/<t>/<path:item_id>.json')
def stream(t,item_id):
    parts=item_id.split(':');base=parts[0];u=dec(base[4:]) if base.startswith('ivy_') else ''
    x=next((x for x in load().get('movies',[]) if x.get('url')==u),None)
    if not x:return jsonify({'streams':[]})
    if len(parts)>=3 and typ(x)=='series':
        try:season=int(parts[-2]);ep=int(parts[-1])
        except:return jsonify({'streams':[]})
        actual_season,rows=episode_rows(x)
        row=next((r for r in rows if r['episode']==ep),None)
        if not row:return jsonify({'streams':[]})
        streams=[]
        for s in row['sources']:
            streams.append({'name':'Ivy❤️','title':f"Ivy❤️ • {row['title']} • {s['name']}",'url':s['url'],'behaviorHints':{'notWebReady':True}})
        return jsonify({'streams':streams})
    h=fetch_text(u,120);urls=list(dict.fromkeys(HLS_RE.findall(h)));streams=[]
    for i,v in enumerate(urls,1):streams.append({'name':'Ivy❤️','title':'Ivy❤️ • Phát' if i==1 else f'Ivy❤️ • Nguồn {i}','url':v,'behaviorHints':{'notWebReady':True}})
    return jsonify({'streams':streams})

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
