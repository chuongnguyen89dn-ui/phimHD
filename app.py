import json, os, base64, re, time, html, unicodedata
from urllib.parse import unquote, urljoin, urlencode
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request

CATALOG=os.environ.get('IVY_CATALOG',os.environ.get('ROPHIM_CATALOG','rophim_catalog.json'))
REMOTE_CATALOG=os.environ.get('IVY_REMOTE_CATALOG','https://raw.githubusercontent.com/chuongnguyen89dn-ui/phimHD/catalog-data/rophim_catalog.json')
BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/')
TMDB_API_KEY=os.environ.get('TMDB_API_KEY','').strip();TMDB_API='https://api.themoviedb.org/3';TMDB_IMG='https://image.tmdb.org/t/p/'
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
app=Flask(__name__);_page_cache={};_order_cache={};_catalog_cache={'at':0,'data':None};_tmdb_cache={}
def _local_catalog():
 try:
  with open(CATALOG,encoding='utf-8') as f:return json.load(f)
 except:return {'movies':[]}
def load():
 now=time.time()
 if _catalog_cache['data'] is not None and now-_catalog_cache['at']<900:return _catalog_cache['data']
 fallback=_catalog_cache['data'] or _local_catalog()
 try:
  with urlopen(Request(REMOTE_CATALOG+'?t='+str(int(now//900)),headers={'User-Agent':UA,'Accept':'application/json'}),timeout=8) as r:data=json.loads(r.read().decode())
  if isinstance(data,dict) and len(data.get('movies',[]))>100:_catalog_cache.update(at=now,data=data);return data
 except:pass
 _catalog_cache.update(at=now,data=fallback);return fallback
def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')
def dec(s):
 try:s+='='*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s.encode()).decode()
 except:return ''
def mid(x):return 'ivy_'+enc(x.get('url',''))
def clean(s):
 s=html.unescape(re.sub(r'(?i)r[oổ]phim','Ivy❤️',str(s or '')));return re.sub(r'\s+',' ',s).split(' - Xem ')[0].split(' | Ivy❤️')[0].strip()
def tax(x,k):return (x.get('taxonomy') or {}).get(k) or x.get(k) or []
def typ(x):
 text=' '.join([str(x.get('title','')),str(x.get('duration',''))]+tax(x,'sections')+tax(x,'genres')).lower();return 'series' if x.get('type')=='series' or any(k in text for k in ['phim bộ','tv shows','/tập','m/tập','season ','phần ']) else 'movie'
def year(x):
 ys=re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)',clean(x.get('title','')))
 if ys:return int(ys[-1])
 y=x.get('year');y=int(y) if str(y).isdigit() else 0;return y if 1900<=y<=2100 and y!=2026 else None
def norm(s):
 s=unicodedata.normalize('NFKD',str(s or ''));s=''.join(c for c in s if not unicodedata.combining(c)).lower();s=re.sub(r'\([^)]*(?:19|20)\d{2}[^)]*\)',' ',s);s=re.sub(r'\b(?:phan|season)\s*\d+\b',' ',s);return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())
def tmdb_get(path,params=None,ttl=21600):
 if not TMDB_API_KEY:return None
 params=dict(params or {});params['api_key']=TMDB_API_KEY;key=path+'?'+urlencode(sorted(params.items()));now=time.time();c=_tmdb_cache.get(key)
 if c and now-c[0]<ttl:return c[1]
 try:
  with urlopen(Request(TMDB_API+path+'?'+urlencode(params),headers={'Accept':'application/json','User-Agent':'Ivy/1.8'}),timeout=8) as r:d=json.loads(r.read().decode());_tmdb_cache[key]=(now,d);return d
 except:return None
def tmdb_match(x):
 existing=x.get('tmdb') or {}
 if existing.get('tmdbId') or not TMDB_API_KEY:return existing
 media='tv' if typ(x)=='series' else 'movie';q=series_name(x) if media=='tv' else clean(x.get('title') or x.get('originalTitle') or '');params={'query':q,'language':'vi-VN','include_adult':'false'};y=year(x)
 if y:params['first_air_date_year' if media=='tv' else 'year']=y
 rows=(tmdb_get('/search/'+media,params) or {}).get('results') or [];target={norm(q),norm(x.get('originalTitle'))};target.discard('')
 for r in rows[:10]:
  names={norm(r.get('title')),norm(r.get('name')),norm(r.get('original_title')),norm(r.get('original_name'))};names.discard('')
  if not target.intersection(names):continue
  dt=r.get('release_date') or r.get('first_air_date') or '';ry=int(dt[:4]) if len(dt)>=4 and dt[:4].isdigit() else None
  if y and ry and abs(y-ry)>1:continue
  return {'tmdbId':r.get('id'),'mediaType':media,'voteAverage':r.get('vote_average'),'voteCount':r.get('vote_count'),'posterPath':r.get('poster_path'),'backdropPath':r.get('backdrop_path')}
 return existing
def apply_tmdb(x):
 tm=tmdb_match(x)
 if not tm:return x
 y=dict(x);y['tmdb']=tm
 if tm.get('posterPath'):y['poster']=TMDB_IMG+'w780'+tm['posterPath']
 if tm.get('backdropPath'):y['backdrop']=TMDB_IMG+'w1280'+tm['backdropPath']
 return y
def fetch_text(u,ttl=300):
 now=time.time();c=_page_cache.get(u)
 if c and now-c[0]<ttl:return c[1]
 try:
  with urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Referer':BASE+'/'}),timeout=18) as r:s=r.read().decode('utf-8','replace').replace('\\/','/');_page_cache[u]=(now,s);return s
 except:return ''
def live_source_order(path):
 u=BASE+path;h=fetch_text(u,300);out=[]
 for href in re.findall(r'href=["\']([^"\']+)',h,re.I):
  if '/phim/' in href:
   v=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
   if v not in out:out.append(v)
 return out
def source_order(kind):
 stored=(load().get('sourceOrders') or {}).get(kind) or []
 if stored:return stored
 return live_source_order({'home':'/phimhay','movies':'/phim-le','series':'/phim-bo'}.get(kind,'/phimhay'))
def infer_season(x,h=''):
 text=' '.join([clean(x.get('title','')),clean(h[:20000])])
 for pat in [r'(?i)(?:phần|season)\s*(\d+)',r'(?i)S(\d{1,2})(?:E\d+)?']:
  m=re.search(pat,text)
  if m:return max(1,int(m.group(1)))
 return 1
def series_key(x):
 s=clean(x.get('title') or x.get('slug') or '').lower();s=re.sub(r'\([^)]*(?:phần|season)\s*\d+[^)]*\)',' ',s,flags=re.I);s=re.sub(r'[-–—:]?\s*(?:phần|season)\s*\d+\b',' ',s,flags=re.I);return re.sub(r'\s+',' ',s).strip(' -–—:()')
def series_name(x):
 s=clean(x.get('title') or x.get('slug') or 'Ivy❤️');s=re.sub(r'\s*\([^)]*(?:phần|season)\s*\d+[^)]*\)','',s,flags=re.I);s=re.sub(r'\s*[-–—:]?\s*(?:phần|season)\s*\d+\b','',s,flags=re.I);return re.sub(r'\s+',' ',s).strip(' -–—:()') or clean(x.get('title'))
def family_seasons(x):
 out={};k=series_key(x)
 for y in load().get('movies',[]):
  if typ(y)=='series' and series_key(y)==k:
   s=infer_season(y)
   if s not in out or y.get('url')==x.get('url'):out[s]=y
 return out or {infer_season(x):x}
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
def episode_rows(x):
 h=fetch_text(x.get('url',''),180);arr=extract_array_after(h,'var episodes =') or extract_array_after(h,'episodes =') or [];by={}
 for srv in arr if isinstance(arr,list) else []:
  for item in (srv.get('server_data') or []) if isinstance(srv,dict) else []:
   slug=str(item.get('slug') or '');name=clean(item.get('name') or item.get('filename') or slug);m=re.search(r'(\d+)',slug+' '+name)
   if not m:continue
   ep=int(m.group(1));row=by.setdefault(ep,{'episode':ep,'title':name or f'Tập {ep}','sources':[]});u=item.get('link_m3u8') or item.get('link_embed') or ''
   if u:row['sources'].append({'name':clean(srv.get('server_name') or 'Nguồn'),'url':u})
 return infer_season(x,h),[by[k] for k in sorted(by)]
def base_meta(x,full=False):
 if full:x=apply_tmdb(x)
 m={'id':mid(x),'type':typ(x),'name':series_name(x) if typ(x)=='series' else clean(x.get('title') or x.get('slug') or 'Ivy❤️'),'poster':x.get('poster') or None,'background':x.get('backdrop') or None,'description':clean(x.get('description')),'website':x.get('url'),'posterShape':'poster'};y=year(x)
 if y:m['releaseInfo']=str(y)
 if tax(x,'genres'):m['genres']=tax(x,'genres')
 if tax(x,'countries'):m['country']=', '.join(tax(x,'countries'))
 if x.get('duration'):m['runtime']=x['duration']
 tm=x.get('tmdb') or {}
 if tm.get('voteAverage') is not None:m['rating']=round(float(tm['voteAverage']),1);m['voteCount']=tm.get('voteCount')
 if full and typ(x)=='series':
  videos=[]
  for season,src in sorted(family_seasons(x).items()):
   _,eps=episode_rows(src)
   for e in eps:videos.append({'id':f"{m['id']}:{season}:{e['episode']}",'title':e['title'],'season':season,'episode':e['episode'],'overview':clean(src.get('description') or x.get('description')),'thumbnail':src.get('backdrop') or src.get('poster')})
  if videos:m['videos']=videos
 return m
def data_index():
 d=load().get('movies',[]);return {str(x.get('url','')).rstrip('/'):x for x in d if x.get('url')}
def ordered(urls,pred=None):
 by=data_index();out=[];seen=set()
 for u in urls:
  x=by.get(str(u).rstrip('/'))
  if x and (not pred or pred(x)) and x.get('url') not in seen:out.append(x);seen.add(x.get('url'))
 return out
def dedupe_series(items):
 out=[];seen=set()
 for x in items:
  k=series_key(x)
  if k not in seen:seen.add(k);out.append(x)
 return out

# Only catalogs represented on the source site are exposed.
SOURCE_SECTIONS=['Điện ảnh Hàn Quốc','Mọt phim Hoa Ngữ','Thiên đường Phim Thái','Phim US-UK Mới','Phim Điện Ảnh Mới Cóng','Dấu ấn điện ảnh Việt','Đêm Kinh Hoàng','Mê Cung Phim Nhật','Phim Bộ Đã Hoàn Thành','Hành Động Nghẹt Thở','Trinh Thám & Bí Ẩn','Tinh Hoa Điện Ảnh Hồng Kông','Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Thế giới Anime','Cổ Trang Trung Quốc','Mãn Nhãn với Phim Chiếu Rạp','Sắp Lên Sóng']
SERIES_SECTIONS={'Phim Bộ Đã Hoàn Thành','Top 10 phim bộ hôm nay'}
def _pos(h,label,start=0):
 p=[h.find(v,start) for v in (label,html.escape(label,quote=False)) if h.find(v,start)>=0];return min(p) if p else -1
def source_home_sections():
 now=time.time();c=_order_cache.get('__sections__')
 if c and now-c[0]<600:return c[1]
 h=fetch_text(BASE+'/phimhay',300);start=max(0,_pos(h,'Bạn đang quan tâm gì?'));ps=[]
 for i,label in enumerate(SOURCE_SECTIONS):
  p=_pos(h,label,start)
  if p>=0:ps.append((p,i,label))
 ps.sort();out={}
 for n,(p,i,label) in enumerate(ps):
  seg=h[p:(ps[n+1][0] if n+1<len(ps) else len(h))];urls=[]
  for href in re.findall(r'href=["\']([^"\']+)',seg,re.I):
   if '/phim/' in href:
    u=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
    if u not in urls:urls.append(u)
  if urls:out[label]=urls
 _order_cache['__sections__']=(now,out);return out
def source_section_items(label):return ordered(source_home_sections().get(label) or [])
def source_menu(kind):
 a=ordered(source_order(kind),lambda x:typ(x)==kind);return dedupe_series(a) if kind=='series' else a
def genre_options():
 out=[]
 for x in load().get('movies',[]):
  for g in tax(x,'genres'):
   if g and g not in out:out.append(g)
 return sorted(out)
def manifest_data():
 common=[{'name':'genre','isRequired':False,'options':genre_options()},{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
 # Phim Lẻ / Phim Bộ are source navigation entries. Editorial rows are exactly the rows detected on source Home.
 cats=[{'type':'movie','id':'ivy_movies','name':'❤️ Ivy • Phim Lẻ','extra':common},{'type':'series','id':'ivy_series','name':'❤️ Ivy • Phim Bộ','extra':common}]
 active=source_home_sections()
 for i,label in enumerate(SOURCE_SECTIONS):
  if active.get(label):cats.append({'type':'series' if label in SERIES_SECTIONS else 'movie','id':f'ivy_src_{i}','name':f'❤️ Ivy • {label}','extra':common})
 return {'id':'community.ivy.catalog','version':'1.8.0','name':'Ivy❤️','description':'Ivy❤️ • catalogs mirror current source navigation and Home rows; TMDB only enriches matched detail metadata','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}
@app.get('/')
def root():return jsonify({'ok':True,'service':'Ivy❤️','version':'1.8.0','manifest':'/manifest.json'})
@app.get('/manifest.json')
def manifest():return jsonify(manifest_data())
@app.get('/health')
def health():return jsonify({'ok':True,'version':'1.8.0','movies':len(load().get('movies',[])),'sourceSections':list(source_home_sections().keys())})
def extras(path=''):
 o={}
 for p in path.split('/'):
  if '=' in p:k,v=p.split('=',1);o[k]=unquote(v)
 for k in ('skip','search','genre'):
  if request.args.get(k)!=None:o[k]=request.args[k]
 return o
def catalog(cid,path=''):
 e=extras(path);q=(e.get('search') or '').lower().strip()
 if cid=='ivy_movies':items=source_menu('movies')
 elif cid=='ivy_series':items=source_menu('series')
 elif cid.startswith('ivy_src_'):
  try:items=source_section_items(SOURCE_SECTIONS[int(cid.rsplit('_',1)[1])])
  except:return jsonify({'metas':[]})
 else:items=[]
 out=[]
 for x in items:
  if e.get('genre') and e['genre'] not in tax(x,'genres'):continue
  m=base_meta(x)
  if not q or q in (m['name']+' '+m.get('description','')).lower():out.append(m)
 try:sk=max(0,int(e.get('skip',0)))
 except:sk=0
 return jsonify({'metas':out[sk:sk+100]})
@app.get('/catalog/<t>/<cid>.json')
def cp(t,cid):return catalog(cid)
@app.get('/catalog/<t>/<cid>/<path:p>.json')
def ce(t,cid,p):return catalog(cid,p)
@app.get('/meta/<t>/<path:item_id>.json')
def meta_route(t,item_id):
 base=item_id.split(':',1)[0];u=dec(base[4:]) if base.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),None);return jsonify({'meta':base_meta(x,True) if x else None})
@app.get('/stream/<t>/<path:item_id>.json')
def stream(t,item_id):
 parts=item_id.split(':');base=parts[0];u=dec(base[4:]) if base.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),None)
 if not x:return jsonify({'streams':[]})
 if len(parts)>=3 and typ(x)=='series':
  try:season=int(parts[-2]);ep=int(parts[-1])
  except:return jsonify({'streams':[]})
  src=family_seasons(x).get(season) or x;_,rows=episode_rows(src);row=next((r for r in rows if r['episode']==ep),None)
  if not row:return jsonify({'streams':[]})
  return jsonify({'streams':[{'name':'Ivy❤️','title':f"Ivy❤️ • Mùa {season} • {row['title']} • {s['name']}",'url':s['url'],'behaviorHints':{'notWebReady':True}} for s in row['sources']]})
 hints=x.get('playbackHints') or {};urls=list(dict.fromkeys((hints.get('direct') or [])+HLS_RE.findall(fetch_text(u,120))))
 if not urls:
  for s in hints.get('episodeSources') or []:
   if s.get('url'):urls.append(s['url'])
 return jsonify({'streams':[{'name':'Ivy❤️','title':'Ivy❤️ • Phát' if i==0 else f'Ivy❤️ • Nguồn {i+1}','url':v,'behaviorHints':{'notWebReady':True}} for i,v in enumerate(dict.fromkeys(urls))]})
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
