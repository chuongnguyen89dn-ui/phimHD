import json, os, re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from urllib.request import Request, urlopen
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from rophim_catalog_crawler import parse_movie

BASE=os.environ.get('ROPHIM_BASE','https://rophim.loan').rstrip('/')
OUT=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
WORKERS=int(os.environ.get('ROPHIM_WORKERS','32'))
UA='Mozilla/5.0 (compatible; IvyCatalog/5.3)'
TAX_PREFIXES={'/the-loai/':'genres','/quoc-gia/':'countries','/phim-le':'sections','/phim-bo':'sections','/hoat-hinh':'sections','/tv-shows':'sections','/phim-chieu-rap':'sections','/lich-chieu':'schedules'}

def norm(u):
 u=urljoin(BASE+'/',u);p=urlparse(u)
 if p.netloc!=urlparse(BASE).netloc:return ''
 q=urlencode(sorted(parse_qsl(p.query,keep_blank_values=True)))
 return urlunparse((p.scheme,p.netloc,p.path.rstrip('/') or '/','',q,''))
def fetch(u):
 r=urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Referer':BASE+'/'}),timeout=20)
 return r.geturl(),r.read().decode('utf-8','ignore')
def links(h,u):return [norm(x) for x in re.findall(r'href=["\']([^"\']+)',h,re.I) if norm(x)]
def movie(u):return urlparse(u).path.startswith('/phim/')
def tax(u):
 p=urlparse(u).path.lower();return p=='/' or any(p==k or p.startswith(k) for k in TAX_PREFIXES)
def title(h,u):
 m=re.search(r'<title[^>]*>(.*?)</title>',h,re.I|re.S)
 return re.sub(r'<[^>]+>','',m.group(1)).strip().split('|')[0].strip() if m else urlparse(u).path.strip('/').split('/')[-1].replace('-',' ').title()
def bucket(u):
 p=urlparse(u).path.lower()
 for k,v in TAX_PREFIXES.items():
  if p==k or p.startswith(k):return v
 return 'categories'
def scan_page(u):
 final,h=fetch(u);final=norm(final);ls=links(h,final);ms={x for x in ls if movie(x)}
 return final,title(h,final),bucket(final),ms,{x for x in ls if tax(x)}
def source_order(path):
 try:
  final,h=fetch(BASE+path);out=[]
  for u in links(h,final):
   if movie(u) and u not in out:out.append(u)
  return out
 except Exception:return []
def crawl_taxonomy():
 pending={BASE+'/'};seen=set();memberships=defaultdict(lambda:defaultdict(set));cats=[];errors=[]
 with ThreadPoolExecutor(max_workers=WORKERS) as ex:
  while pending:
   batch=list(pending)[:WORKERS*4];pending.difference_update(batch)
   fs={ex.submit(scan_page,u):u for u in batch}
   for f in as_completed(fs):
    u=fs[f]
    if u in seen:continue
    seen.add(u)
    try:
     final,name,b,ms,nexts=f.result();cats.append({'url':final,'title':name,'movieCount':len(ms),'bucket':b})
     for m in ms:memberships[m][b].add(name)
     for x in nexts:
      if x not in seen:pending.add(x)
    except Exception as e:errors.append({'url':u,'stage':'taxonomy','error':str(e)})
   if len(seen)%100<WORKERS*4:print(f'[taxonomy] pages={len(seen)} queued={len(pending)} movies={len(memberships)}',flush=True)
 return memberships,cats,errors
def load_old():
 try:
  with open(OUT,'r',encoding='utf-8') as f:return json.load(f)
 except:return {'movies':[]}
def needs_refresh(x):return not isinstance(x,dict) or not x.get('poster') or not x.get('description') or x.get('year') in (None,'')
def parse_detail(u):
 final,h=fetch(u);x=parse_movie(final,h);x['url']=norm(x.get('url') or final);x['source']='ivy-source';return x
def main():
 started=datetime.now(timezone.utc).isoformat();old=load_old();oldmap={norm(x.get('url','')):x for x in old.get('movies',[]) if isinstance(x,dict) and x.get('url')}
 mem,cats,errors=crawl_taxonomy();urls=set(oldmap)|set(mem);new=set(urls)-set(oldmap);stale={u for u,x in oldmap.items() if needs_refresh(x)};todo=sorted(new|stale)
 print(f'[discover] cached={len(oldmap)} taxonomy={len(mem)} new={len(new)} stale={len(stale)} detail={len(todo)}',flush=True)
 if todo:
  with ThreadPoolExecutor(max_workers=WORKERS) as ex:
   fs={ex.submit(parse_detail,u):u for u in todo}
   for i,f in enumerate(as_completed(fs),1):
    u=fs[f]
    try:x=f.result();oldmap[norm(x['url'])]=x
    except Exception as e:errors.append({'url':u,'stage':'detail','error':str(e)})
    if i%100==0 or i==len(todo):print(f'[details] {i}/{len(todo)}',flush=True)
 movie_order=source_order('/phim-le');series_order=source_order('/phim-bo');home_order=source_order('/phimhay')
 rank={u:i for i,u in enumerate(movie_order+series_order+home_order)}
 movies=[]
 for u,x in oldmap.items():
  mm=mem.get(u,{});taxonomy={b:sorted(mm.get(b,set())) for b in ('genres','countries','sections','schedules','categories')};oldtax=x.get('taxonomy') if isinstance(x.get('taxonomy'),dict) else {}
  for b in taxonomy:
   if not taxonomy[b] and oldtax.get(b):taxonomy[b]=oldtax[b]
  if not taxonomy['genres'] and x.get('genres'):taxonomy['genres']=x.get('genres')
  x['taxonomy']=taxonomy;x['categoryMembership']=sorted(set(sum((taxonomy[b] for b in taxonomy),[])));x['genres']=taxonomy['genres'] or x.get('genres') or [];x['countries']=taxonomy['countries'];x['sections']=taxonomy['sections'];x['schedules']=taxonomy['schedules'];x['categories']=taxonomy['categories'];x['sourceLatestRank']=rank.get(u);movies.append(x)
 movies.sort(key=lambda x:(x.get('sourceLatestRank') is None,x.get('sourceLatestRank') if x.get('sourceLatestRank') is not None else 10**9,str(x.get('title','')).lower()))
 data={'generatedAt':datetime.now(timezone.utc).isoformat(),'startedAt':started,'baseUrl':BASE,'crawlerVersion':'ivy-taxonomy-cache-v5.3','sourceOrders':{'movies':movie_order,'series':series_order,'home':home_order},'categories':cats,'stats':{'cachedMovieCount':len(old.get('movies',[])),'taxonomyMovieCount':len(mem),'newMovieCount':len(new),'refreshedMovieCount':len(stale),'movieCount':len(movies),'categoryPageCount':len(cats),'errorCount':len(errors),'movieOrderCount':len(movie_order),'seriesOrderCount':len(series_order)},'movies':movies,'errors':errors}
 tmp=OUT+'.tmp';json.dump(data,open(tmp,'w',encoding='utf-8'),ensure_ascii=False,indent=2);os.replace(tmp,OUT);print('DONE',json.dumps(data['stats'],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
