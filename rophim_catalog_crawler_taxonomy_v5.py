import json, os, re, time, random
from xml.etree import ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse, unquote
from urllib.request import Request, urlopen
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from rophim_catalog_crawler import parse_movie

BASE=os.environ.get('ROPHIM_BASE','https://rophims.team').rstrip('/')
OUT=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
WORKERS=int(os.environ.get('ROPHIM_WORKERS','32'))
FULL_REBUILD=os.environ.get('ROPHIM_FULL_REBUILD','0').strip().lower() in ('1','true','yes','on')
UA='Mozilla/5.0 (compatible; IvyCatalog/5.4)'
TAX_PREFIXES={'/the-loai/':'genres','/quoc-gia/':'countries','/phim-le':'sections','/phim-bo':'sections','/hoat-hinh':'sections','/tv-shows':'sections','/phim-chieu-rap':'sections','/lich-chieu':'schedules'}

def norm(u):
 u=urljoin(BASE+'/',u);p=urlparse(u);b=urlparse(BASE)
 if p.netloc in ('rophim.loan','www.rophim.loan','www.rophims.team'):p=p._replace(scheme=b.scheme,netloc=b.netloc)
 if p.netloc!=b.netloc:return ''
 q=urlencode(sorted(parse_qsl(p.query,keep_blank_values=True)))
 return urlunparse((b.scheme,b.netloc,p.path.rstrip('/') or '/','',q,''))
def fetch(u):
 r=urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Referer':BASE+'/'}),timeout=20)
 return r.geturl(),r.read().decode('utf-8','ignore')

def fetch_detail(u, attempts=4):
 headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36','Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8','Referer':BASE+'/'}
 last=None
 for i in range(attempts):
  try:
   from curl_cffi import requests as curl_requests
   r=curl_requests.get(u,headers=headers,timeout=20,impersonate='chrome',allow_redirects=True)
   if r.status_code < 400 and r.text:
    return r.url,r.text
   last=RuntimeError(f'HTTP {r.status_code}')
  except Exception as e:last=e
  try:
   r=urlopen(Request(u,headers=headers),timeout=20)
   body=r.read().decode('utf-8','ignore')
   if body:return r.geturl(),body
  except Exception as e:last=e
  time.sleep((i+1)*0.8 + random.random()*0.4)
 raise last or RuntimeError('empty detail response')
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
def sitemap_movies():
 roots=[BASE+'/sitemap.xml'];seen=set();movies=set();errors=[]
 while roots:
  u=roots.pop(0)
  if u in seen:continue
  seen.add(u)
  try:
   _,raw=fetch(u);root=ET.fromstring(raw)
   locs=[(e.text or '').strip() for e in root.iter() if e.tag.lower().endswith('loc')]
   for loc in locs:
    n=norm(unquote(loc))
    if not n:continue
    if movie(n):movies.add(n)
    elif 'sitemap' in urlparse(n).path.lower() and n not in seen:roots.append(n)
  except Exception as e:errors.append({'url':u,'stage':'sitemap','error':str(e)})
 print(f'[sitemap] checked={len(seen)} movies={len(movies)} errors={len(errors)}',flush=True)
 return movies,errors
def load_old():
 if FULL_REBUILD:return {'movies':[]}
 try:
  with open(OUT,'r',encoding='utf-8') as f:return json.load(f)
 except:return {'movies':[]}
def needs_refresh(x):return not isinstance(x,dict) or not x.get('poster') or not x.get('description') or x.get('year') in (None,'')
def parse_detail(u):
 final,h=fetch_detail(u);x=parse_movie(final,h);x['url']=norm(x.get('url') or final);x['source']='ivy-source';return x
def dedupe_movies(rows):
 seen=set();out=[]
 for x in rows:
  if not isinstance(x,dict):continue
  k=norm(x.get('url') or '')
  if not k:continue
  if k in seen:continue
  seen.add(k);x['url']=k;out.append(x)
 return out

def main():
 started=datetime.now(timezone.utc).isoformat();old=load_old();oldmap={}
 if FULL_REBUILD:print('[full-rebuild] ignoring cached catalog; refreshing every discovered detail page',flush=True)
 for x in old.get('movies',[]):
  if not isinstance(x,dict) or not x.get('url'):continue
  k=norm(x.get('url',''))
  if not k:continue
  y=dict(x);y['url']=k
  oldmap[k]=y
 mem,cats,errors=crawl_taxonomy();smap,serr=sitemap_movies();errors.extend(serr);urls=set(oldmap)|set(mem)|set(smap);new=set(urls)-set(oldmap);stale={u for u,x in oldmap.items() if needs_refresh(x)};todo=sorted(new|stale)
 print(f'[discover] cached={len(oldmap)} taxonomy={len(mem)} sitemap={len(smap)} new={len(new)} stale={len(stale)} detail={len(todo)}',flush=True)
 detail_failed=[]
 if todo:
  with ThreadPoolExecutor(max_workers=WORKERS) as ex:
   fs={ex.submit(parse_detail,u):u for u in todo}
   for i,f in enumerate(as_completed(fs),1):
    u=fs[f]
    try:x=f.result();oldmap[norm(x['url'])]=x
    except Exception as e:detail_failed.append((u,str(e)))
    if i%100==0 or i==len(todo):print(f'[details] {i}/{len(todo)} failed={len(detail_failed)}',flush=True)
 if detail_failed:
  retry_workers=max(4,min(12,WORKERS//2))
  print(f'[details-retry] retrying {len(detail_failed)} unresolved URLs with {retry_workers} workers',flush=True)
  unresolved=[]
  with ThreadPoolExecutor(max_workers=retry_workers) as ex:
   fs={ex.submit(parse_detail,u):u for u,_ in detail_failed}
   for i,f in enumerate(as_completed(fs),1):
    u=fs[f]
    try:x=f.result();oldmap[norm(x['url'])]=x
    except Exception as e:unresolved.append((u,str(e)))
    if i%50==0 or i==len(detail_failed):print(f'[details-retry] {i}/{len(detail_failed)} unresolved={len(unresolved)}',flush=True)
  detail_failed=unresolved
 for u,e in detail_failed:errors.append({'url':u,'stage':'detail-unresolved','error':e})
 movie_order=source_order('/phim-le');series_order=source_order('/phim-bo');home_order=source_order('/phimhay')
 rank={u:i for i,u in enumerate(movie_order+series_order+home_order)}
 movies=[]
 for u,x in oldmap.items():
  mm=mem.get(u,{});taxonomy={b:sorted(mm.get(b,set())) for b in ('genres','countries','sections','schedules','categories')};oldtax=x.get('taxonomy') if isinstance(x.get('taxonomy'),dict) else {}
  for b in taxonomy:
   if not taxonomy[b] and oldtax.get(b):taxonomy[b]=oldtax[b]
  if not taxonomy['genres'] and x.get('genres'):taxonomy['genres']=x.get('genres')
  x['taxonomy']=taxonomy;x['categoryMembership']=sorted(set(sum((taxonomy[b] for b in taxonomy),[])));x['genres']=taxonomy['genres'] or x.get('genres') or [];x['countries']=taxonomy['countries'];x['sections']=taxonomy['sections'];x['schedules']=taxonomy['schedules'];x['categories']=taxonomy['categories'];x['sourceLatestRank']=rank.get(u);movies.append(x)
 movies=dedupe_movies(movies)
 movies.sort(key=lambda x:(x.get('sourceLatestRank') is None,x.get('sourceLatestRank') if x.get('sourceLatestRank') is not None else 10**9,str(x.get('title','')).lower()))
 data={'generatedAt':datetime.now(timezone.utc).isoformat(),'startedAt':started,'baseUrl':BASE,'crawlerVersion':'ivy-taxonomy-full-v5.5' if FULL_REBUILD else 'ivy-taxonomy-cache-v5.5','sourceOrders':{'movies':movie_order,'series':series_order,'home':home_order},'categories':cats,'stats':{'cachedMovieCount':len(old.get('movies',[])),'taxonomyMovieCount':len(mem),'sitemapMovieCount':len(smap),'newMovieCount':len(new),'refreshedMovieCount':len(stale),'movieCount':len(movies),'categoryPageCount':len(cats),'errorCount':len(errors),'detailUnresolvedCount':len([e for e in errors if e.get('stage')=='detail-unresolved']),'movieOrderCount':len(movie_order),'seriesOrderCount':len(series_order)},'movies':movies,'errors':errors}
 tmp=OUT+'.tmp';json.dump(data,open(tmp,'w',encoding='utf-8'),ensure_ascii=False,indent=2);os.replace(tmp,OUT);print('DONE',json.dumps(data['stats'],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
