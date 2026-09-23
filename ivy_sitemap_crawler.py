import json, re, html, os, time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE=os.environ.get('IVY_SOURCE_BASE','https://rophims.team').rstrip('/')
OUT=os.environ.get('IVY_SITEMAP_OUT','ivy_sitemap.json')
UAS=[
 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36',
 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
]
SECTIONS=['Điện ảnh Hàn Quốc','Mọt phim Hoa Ngữ','Thiên đường Phim Thái','Phim US-UK Mới','Phim Điện Ảnh Mới Cóng','Dấu ấn điện ảnh Việt','Đêm Kinh Hoàng','Mê Cung Phim Nhật','Phim Bộ Đã Hoàn Thành','Hành Động Nghẹt Thở','Trinh Thám & Bí Ẩn','Tinh Hoa Điện Ảnh Hồng Kông','Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Thế giới Anime','Cổ Trang Trung Quốc','Mãn Nhãn với Phim Chiếu Rạp','Sắp Lên Sóng']
TOP10={'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay'}
MAX_PAGES=180;BATCH=12

def fetch(u,timeout=20):
 for attempt in range(4):
  ua=UAS[attempt%len(UAS)]
  try:
   req=Request(u,headers={'User-Agent':ua,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi-VN,vi;q=0.9,en;q=0.7','Cache-Control':'no-cache','Referer':BASE+'/'})
   with urlopen(req,timeout=timeout) as r:
    body=r.read().decode('utf-8','replace').replace('\\/','/')
    if body:return body
  except Exception as e:
   print('fetch retry',attempt+1,u,type(e).__name__,e,flush=True)
  time.sleep(1.5*(attempt+1))
 return ''

def movie_urls(txt):
 out=[]
 for href in re.findall(r'href=["\']([^"\']+)',txt,re.I):
  if '/phim/' not in href:continue
  u=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
  if u not in out:out.append(u)
 return out

def pos(txt,label,start=0):
 ps=[]
 for v in (label,html.escape(label,quote=False)):
  p=txt.find(v,start)
  if p>=0:ps.append(p)
 return min(ps) if ps else -1

def listing_link(seg,label=''):
 links=[]
 for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',seg,re.I|re.S):
  u=urljoin(BASE+'/',html.unescape(m.group(1))).split('#')[0]
  if '/phim/' in u:continue
  text=html.unescape(re.sub('<[^>]+>',' ',m.group(2)));links.append((u,text))
  if re.search(r'(?i)xem\s*(?:thêm|toàn\s*bộ|tất\s*cả)|tất\s*cả',text):return u
 if label=='Sắp Lên Sóng':
  for u,text in links:
   if re.search(r'(?i)(lich[-_/ ]?chieu|sap[-_/ ]?len[-_/ ]?song|upcoming|coming)',u+' '+text):return u
  return BASE+'/lich-chieu'
 return None

def page_url(seed,n):
 if n<=1:return seed
 if re.search(r'([?&])page=\d+',seed):return re.sub(r'([?&])page=\d+',r'\1page='+str(n),seed)
 return seed+('&' if '?' in seed else '?')+'page='+str(n)

def crawl_listing(seed):
 first=fetch(seed)
 if not first:return [],0
 urls=movie_urls(first);seen=set(urls);last_good=1;empty=0;start=2
 while start<=MAX_PAGES and empty<2:
  nums=list(range(start,min(MAX_PAGES+1,start+BATCH)));pages={}
  with ThreadPoolExecutor(max_workers=len(nums)) as ex:
   fs={ex.submit(fetch,page_url(seed,n)):n for n in nums}
   for f in as_completed(fs):pages[fs[f]]=f.result()
  stop=False
  for n in nums:
   rows=movie_urls(pages.get(n,''));new=[u for u in rows if u not in seen]
   if new:empty=0;last_good=n;urls.extend(new);seen.update(new)
   else:
    empty+=1
    if empty>=2:stop=True;break
  if stop:break
  start+=BATCH
 return urls,last_good

def main():
 home=fetch(BASE+'/phimhay')
 if not home:
  print('phimhay unavailable; trying source root',flush=True);home=fetch(BASE+'/')
 if not home:raise SystemExit('cannot fetch source home after retries')
 start=max(0,pos(home,'Bạn đang quan tâm gì?'));found=[]
 for i,label in enumerate(SECTIONS):
  p=pos(home,label,start)
  if p>=0:found.append((p,i,label))
 found.sort();out={'source':BASE,'generatedAt':int(time.time()),'sections':[]}
 for idx,(p,i,label) in enumerate(found):
  end=found[idx+1][0] if idx+1<len(found) else len(home);seg=home[p:end];home_urls=movie_urls(seg);listing=listing_link(seg,label)
  if label in TOP10 or not listing:all_urls=home_urls;pages=1
  else:
   crawled,pages=crawl_listing(listing);all_urls=[]
   for u in home_urls+crawled:
    if u not in all_urls:all_urls.append(u)
  row={'label':label,'home':home_urls,'listing':listing,'pages':pages,'count':len(all_urls),'urls':all_urls}
  out['sections'].append(row);print(label,'home=',len(home_urls),'pages=',pages,'items=',len(all_urls),'listing=',listing,flush=True)
 with open(OUT,'w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
 print('wrote',OUT,'sections=',len(out['sections']))
if __name__=='__main__':main()
