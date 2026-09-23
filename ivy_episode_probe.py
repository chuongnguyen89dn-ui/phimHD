import json,re,sys
from urllib.request import Request,urlopen
from urllib.parse import urljoin
BASE='https://rophim.loan';UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
PATTERNS=[r'(?i)(?:season|mùa)\s*(\d+)',r'(?i)(?:episode|tập)\s*(\d+)',r'(?i)S(\d{1,2})E(\d{1,3})']
def fetch(u):
 headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8','Referer':BASE+'/'}
 try:
  from curl_cffi import requests as curl_requests
  r=curl_requests.get(u,headers=headers,timeout=20,impersonate='chrome',allow_redirects=True)
  print('FETCH',r.status_code,len(r.text),r.url,file=sys.stderr,flush=True)
  if r.status_code < 400 and r.text:return r.text.replace('\\/','/')
 except Exception as e:
  print('CURL_FAIL',type(e).__name__,str(e)[:180],file=sys.stderr,flush=True)
 with urlopen(Request(u,headers=headers),timeout=20) as r:return r.read().decode('utf-8','replace').replace('\\/','/')
def probe(u):
 h=fetch(u);links=[]
 for href,text in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',h,re.I|re.S):
  txt=re.sub('<[^>]+>',' ',text);txt=' '.join(txt.split())
  if re.search(r'(?i)\b(tập|episode|mùa|season)\b',txt):links.append({'text':txt[:160],'url':urljoin(u,href)})
 scripts=[]
 for m in re.finditer(r'(?i)(.{0,100}(?:episode|season|tập|mùa|playlist|m3u8).{0,220})',h):
  s=' '.join(m.group(1).split())
  if s not in scripts:scripts.append(s)
 watch=[]
 for row in links[:3]:
  try:
   wh=fetch(row['url'].replace('&amp;','&'))
   watch.append({'url':row['url'],'hls':list(dict.fromkeys(HLS.findall(wh)))[:8],'bytes':len(wh)})
  except Exception as e:
   watch.append({'url':row['url'],'error':type(e).__name__+': '+str(e)[:160]})
 return {'url':u,'hls':list(dict.fromkeys(HLS.findall(h))),'episodeLinks':links[:100],'watchPages':watch,'signals':scripts[:100]}
if __name__=='__main__':
 for u in sys.argv[1:]:print(json.dumps(probe(u),ensure_ascii=False,indent=2))
