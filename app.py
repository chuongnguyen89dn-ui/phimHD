import json, os, base64, re, time
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from flask import Flask, jsonify, request
CATALOG=os.environ.get('IVY_CATALOG',os.environ.get('ROPHIM_CATALOG','rophim_catalog.json'));SOURCE_BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/');SOURCE_HOME=SOURCE_BASE+'/phimhay';UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I);app=Flask(__name__);_hc={'at':0,'sections':[]}
def load():
 try:
  with open(CATALOG,encoding='utf-8') as f:return json.load(f)
 except:return {'movies':[]}
def enc(s):return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')
def dec(s):
 try:s+='='*((4-len(s)%4)%4);return base64.urlsafe_b64decode(s).decode()
 except:return ''
def mid(x):return 'ivy_'+enc(x.get('url',''))
def clean(s):return re.sub(r'(?i)r[oổ]phim','Ivy❤️',str(s or '')).split(' - Xem ')[0].split(' | Ivy❤️')[0].strip()
def tax(x,k):return (x.get('taxonomy') or {}).get(k) or x.get(k) or []
def typ(x):
 text=' '.join([str(x.get('title','')),str(x.get('duration',''))]+tax(x,'sections')+tax(x,'genres')).lower()
 return 'series' if x.get('type')=='series' or any(k in text for k in ['phim bộ','tv shows','/tập','m/tập','season ','phần ']) else 'movie'
def year(x):
 ys=re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)',clean(x.get('title','')))
 if ys:return int(ys[-1])
 y=x.get('year');y=int(y) if str(y).isdigit() else 0
 return y if 1900<=y<=2100 and y!=2026 else None
def meta(x):
 m={'id':mid(x),'type':typ(x),'name':clean(x.get('title') or x.get('slug') or 'Ivy❤️'),'poster':x.get('poster') or None,'background':x.get('backdrop') or None,'description':clean(x.get('description')),'website':x.get('url'),'posterShape':'poster'};y=year(x)
 if y:m['releaseInfo']=str(y)
 if tax(x,'genres'):m['genres']=tax(x,'genres')
 if x.get('duration'):m['runtime']=x['duration']
 return m
class HP(HTMLParser):
 def __init__(self):super().__init__();self.s=[];self.c={'name':'Phim mới cập nhật','urls':[]};self.h=False;self.buf=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t in ('h2','h3'):self.h=True;self.buf=[]
  if t=='a' and '/phim/' in a.get('href',''):
   u=urljoin(SOURCE_BASE+'/',a['href']).split('#')[0]
   if u not in self.c['urls']:self.c['urls'].append(u)
 def handle_data(self,d):
  if self.h:self.buf.append(d)
 def handle_endtag(self,t):
  if t in ('h2','h3') and self.h:
   n=' '.join(''.join(self.buf).split()).strip()
   if n and n.lower() not in ('xem thêm','xem toàn bộ'):
    if self.c['urls']:self.s.append(self.c)
    self.c={'name':n,'urls':[]}
   self.h=False
 def done(self):
  if self.c['urls']:self.s.append(self.c)
  return self.s
def sections():
 if _hc['sections'] and time.time()-_hc['at']<900:return _hc['sections']
 try:
  with urlopen(Request(SOURCE_HOME,headers={'User-Agent':UA}),timeout=15) as r:h=r.read().decode('utf-8','replace')
  p=HP();p.feed(h);s=[z for z in p.done() if z['urls']]
  if s:_hc.update(at=time.time(),sections=s)
 except:pass
 return _hc['sections']
def sid(n):return 'ivy_sec_'+enc(n)[:40]
def manifest_data():
 cats=[]
 for s in sections()[:18]:cats.append({'type':'movie','id':sid(s['name']),'name':'❤️ Ivy • '+clean(s['name']),'extra':[{'name':'skip','isRequired':False}]})
 cats += [{'type':'movie','id':'ivy_movies','name':'❤️ Ivy • Phim Lẻ','extra':[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]},{'type':'series','id':'ivy_series','name':'❤️ Ivy • Phim Bộ','extra':[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]}]
 genres=sorted({g for x in load().get('movies',[]) for g in tax(x,'genres') if g});countries=sorted({g for x in load().get('movies',[]) for g in tax(x,'countries') if g})
 cats += [{'type':'movie','id':'ivy_genres','name':'❤️ Ivy • Thể loại','extra':[{'name':'genre','isRequired':False,'options':genres},{'name':'skip','isRequired':False}]},{'type':'movie','id':'ivy_countries','name':'❤️ Ivy • Quốc gia','extra':[{'name':'country','isRequired':False,'options':countries},{'name':'skip','isRequired':False}]}]
 return {'id':'community.ivy.catalog','version':'0.9.0','name':'Ivy❤️','description':'Ivy❤️ • catalog theo đúng các hàng nội dung nguồn','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'catalogs':cats}
@app.get('/manifest.json')
def mani():return jsonify(manifest_data())
@app.get('/')
def root():return jsonify({'ok':True,'service':'Ivy❤️','version':'0.9.0','manifest':'/manifest.json'})
@app.get('/health')
def health():return jsonify({'ok':True,'version':'0.9.0','movies':len(load().get('movies',[])),'sections':[s['name'] for s in sections()]})
def extra(path=''):
 o={}
 for p in path.split('/'):
  if '=' in p:k,v=p.split('=',1);o[k]=unquote(v)
 for k in ('skip','search','genre','country'):
  if request.args.get(k)!=None:o[k]=request.args[k]
 return o
def catalog(t,c,path=''):
 e=extra(path);data=load().get('movies',[]);by={x.get('url'):x for x in data};ordered=data
 sec=next((s for s in sections() if sid(s['name'])==c),None)
 if sec:ordered=[by[u] for u in sec['urls'] if u in by]
 out=[];q=(e.get('search') or '').lower()
 for x in ordered:
  m=meta(x)
  if c=='ivy_movies' and m['type']!='movie':continue
  if c=='ivy_series' and m['type']!='series':continue
  if e.get('genre') and e['genre'] not in tax(x,'genres'):continue
  if e.get('country') and e['country'] not in tax(x,'countries'):continue
  if q and q not in (m['name']+' '+m.get('description','')).lower():continue
  out.append(m)
 try:sk=max(0,int(e.get('skip',0)))
 except:sk=0
 return jsonify({'metas':out[sk:sk+100]})
@app.get('/catalog/<t>/<c>.json')
def cp(t,c):return catalog(t,c)
@app.get('/catalog/<t>/<c>/<path:p>.json')
def ce(t,c,p):return catalog(t,c,p)
@app.get('/meta/<t>/<path:i>.json')
def gm(t,i):
 u=dec(i[4:]) if i.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),None);return jsonify({'meta':meta(x) if x else None})
def hls(u):
 try:
  with urlopen(Request(u,headers={'User-Agent':UA,'Referer':SOURCE_BASE+'/'}),timeout=15) as r:s=r.read().decode('utf-8','replace').replace('\\/','/')
  return list(dict.fromkeys(HLS_RE.findall(s)))
 except:return []
@app.get('/stream/<t>/<path:i>.json')
def stream(t,i):
 u=dec(i[4:]) if i.startswith('ivy_') else '';x=next((x for x in load().get('movies',[]) if x.get('url')==u),{});urls=hls(u);series=typ(x)=='series';a=[]
 for n,v in enumerate(urls,1):a.append({'name':'Ivy❤️','title':('Ivy❤️ • Tập '+str(n)) if series else ('Ivy❤️ • Phát' if n==1 else 'Ivy❤️ • Nguồn '+str(n)),'url':v,'behaviorHints':{'notWebReady':True}})
 return jsonify({'streams':a})
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
