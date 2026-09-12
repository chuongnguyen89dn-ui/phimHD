import json, os, re, time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from urllib.request import Request, urlopen
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE=os.environ.get('ROPHIM_BASE','https://rophim.loan').rstrip('/')
OUT=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
WORKERS=int(os.environ.get('ROPHIM_WORKERS','12'))
UA='Mozilla/5.0 (compatible; RoPhimCatalog/5.0)'

TAX_PREFIXES={
 '/the-loai/':'genres','/quoc-gia/':'countries','/phim-le':'sections','/phim-bo':'sections',
 '/hoat-hinh':'sections','/tv-shows':'sections','/phim-chieu-rap':'sections','/lich-chieu':'schedules'
}

def norm(u):
 u=urljoin(BASE+'/',u); p=urlparse(u)
 if p.netloc!=urlparse(BASE).netloc:return ''
 q=urlencode(sorted(parse_qsl(p.query,keep_blank_values=True)))
 return urlunparse((p.scheme,p.netloc,p.path.rstrip('/') or '/', '',q,''))

def fetch(u):
 r=urlopen(Request(u,headers={'User-Agent':UA}),timeout=25); return r.geturl(),r.read().decode('utf-8','ignore')

def links(h,u):
 return [norm(x) for x in re.findall(r'href=["\']([^"\']+)',h,re.I) if norm(x)]

def movie(u): return urlparse(u).path.startswith('/phim/')
def tax(u):
 p=urlparse(u).path.lower(); return p=='/' or any(p==k or p.startswith(k) for k in TAX_PREFIXES)
def label(u):
 p=urlparse(u).path.strip('/').split('/')[-1] or 'home'; return p.replace('-',' ').title()
def title(h,u):
 m=re.search(r'<title[^>]*>(.*?)</title>',h,re.I|re.S)
 return re.sub(r'<[^>]+>','',m.group(1)).strip().split('|')[0].strip() if m else label(u)
def bucket(u):
 p=urlparse(u).path.lower()
 for k,v in TAX_PREFIXES.items():
  if p==k or p.startswith(k): return v
 return 'categories'

def crawl_taxonomy():
 q=deque([BASE+'/']); seen=set(); memberships=defaultdict(lambda:defaultdict(set)); cats=[]; errors=[]
 while q:
  u=q.popleft()
  if u in seen: continue
  seen.add(u)
  try:
   final,h=fetch(u); final=norm(final); ls=links(h,final); ms={x for x in ls if movie(x)}; name=title(h,final); b=bucket(final)
   cats.append({'url':final,'title':name,'movieCount':len(ms),'bucket':b})
   for m in ms:
    memberships[m][b].add(name)
   for x in ls:
    if tax(x) and x not in seen:q.append(x)
   if len(seen)%50==0: print(f'[taxonomy] pages={len(seen)} movies={len(memberships)}',flush=True)
  except Exception as e: errors.append({'url':u,'stage':'taxonomy','error':str(e)})
 return memberships,cats,errors

def load_old():
 try:
  with open(OUT,'r',encoding='utf-8') as f:return json.load(f)
 except:return {'movies':[]}

def parse_detail(u):
 final,h=fetch(u)
 t=title(h,final); slug=urlparse(final).path.rstrip('/').split('/')[-1]
 poster=''; m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',h,re.I)
 if m:poster=m.group(1)
 return {'url':norm(final),'slug':slug,'title':t,'poster':poster,'backdrop':poster,'description':'','year':None,'duration':'','quality':'','type':'movie','source':'rophim.loan'}

def main():
 started=datetime.now(timezone.utc).isoformat(); old=load_old(); oldmap={norm(x.get('url','')):x for x in old.get('movies',[]) if x.get('url')}
 mem,cats,errors=crawl_taxonomy(); urls=set(oldmap)|set(mem); new=sorted(urls-set(oldmap))
 print(f'[discover] cached={len(oldmap)} taxonomy={len(mem)} new={len(new)}',flush=True)
 if new:
  with ThreadPoolExecutor(max_workers=WORKERS) as ex:
   fs={ex.submit(parse_detail,u):u for u in new}
   for i,f in enumerate(as_completed(fs),1):
    try: x=f.result(); oldmap[norm(x['url'])]=x
    except Exception as e: errors.append({'url':fs[f],'stage':'new-movie','error':str(e)})
    if i%25==0: print(f'[new movies] {i}/{len(new)}',flush=True)
 movies=[]
 for u,x in oldmap.items():
  mm=mem.get(u,{})
  for b in ('genres','countries','sections','schedules','categories'):
   x[b]=sorted(mm.get(b,set()))
  movies.append(x)
 movies.sort(key=lambda x:(str(x.get('title','')).lower(),str(x.get('slug',''))))
 data={'generatedAt':datetime.now(timezone.utc).isoformat(),'startedAt':started,'baseUrl':BASE,'crawlerVersion':'taxonomy-cache-v5','categories':cats,'stats':{'cachedMovieCount':len(old.get('movies',[])),'taxonomyMovieCount':len(mem),'newMovieCount':len(new),'movieCount':len(movies),'categoryPageCount':len(cats),'errorCount':len(errors)},'movies':movies,'errors':errors}
 tmp=OUT+'.tmp'
 with open(tmp,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
 os.replace(tmp,OUT); print('DONE',json.dumps(data['stats'],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
