import json, os, re, unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CATALOG=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
TOKEN=os.environ.get('TMDB_BEARER_TOKEN','').strip()
API='https://api.themoviedb.org/3'
UA='Ivy/1.0'


def norm(s):
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).lower()
    s=re.sub(r'\([^)]*(?:19|20)\d{2}[^)]*\)',' ',s)
    s=re.sub(r'\b(?:phan|season)\s*\d+\b',' ',s)
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(s.split())

def yval(x):
    y=x.get('year')
    if str(y).isdigit(): return int(y)
    m=re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)',str(x.get('title','')))
    return int(m[-1]) if m else None

def get(path,params=None):
    if not TOKEN: raise RuntimeError('TMDB_BEARER_TOKEN missing')
    u=API+path
    if params:u+='?'+urlencode(params)
    req=Request(u,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json','User-Agent':UA})
    with urlopen(req,timeout=20) as r:return json.loads(r.read().decode('utf-8'))

def fetch_pages(path,pages=5):
    out=[]
    for p in range(1,pages+1):
        d=get(path,{'language':'vi-VN','page':p})
        out.extend(d.get('results') or [])
    return out

def build_index(movies):
    idx={}
    for x in movies:
        names=[x.get('title'),x.get('originalTitle'),x.get('alternateName'),x.get('slug')]
        for name in names:
            n=norm(name)
            if n:idx.setdefault(n,[]).append(x)
    return idx

def choose(cands,tm):
    if not cands:return None
    dt=tm.get('release_date') or tm.get('first_air_date') or ''
    ty=int(dt[:4]) if len(dt)>=4 and dt[:4].isdigit() else None
    if ty:
        exact=[x for x in cands if yval(x)==ty]
        if exact:return exact[0]
        near=[x for x in cands if yval(x) and abs(yval(x)-ty)<=1]
        if near:return near[0]
    return cands[0]

def match_list(results,idx,media):
    urls=[];matches=[]
    for r in results:
        names=[r.get('title'),r.get('name'),r.get('original_title'),r.get('original_name')]
        x=None
        for name in names:
            n=norm(name)
            if n:
                x=choose(idx.get(n,[]),r)
                if x:break
        if not x:continue
        u=x.get('url')
        if not u or u in urls:continue
        urls.append(u)
        matches.append({'url':u,'tmdbId':r.get('id'),'mediaType':media,'voteAverage':r.get('vote_average'),'voteCount':r.get('vote_count'),'popularity':r.get('popularity'),'posterPath':r.get('poster_path'),'backdropPath':r.get('backdrop_path')})
    return urls,matches

def main():
    with open(CATALOG,encoding='utf-8') as f:d=json.load(f)
    movies=d.get('movies') or [];idx=build_index(movies)
    specs={
      'trendingMovies':('/trending/movie/day','movie',1),
      'trendingSeries':('/trending/tv/day','tv',1),
      'popularMovies':('/movie/popular','movie',5),
      'popularSeries':('/tv/popular','tv',5),
      'topRatedMovies':('/movie/top_rated','movie',5),
      'topRatedSeries':('/tv/top_rated','tv',5),
    }
    rankings={};meta={}
    for key,(path,media,pages) in specs.items():
        rows=fetch_pages(path,pages)
        urls,matches=match_list(rows,idx,media)
        rankings[key]=urls
        for m in matches:meta[m['url']]=m
        print(key,len(urls),flush=True)
    for x in movies:
        m=meta.get(x.get('url'))
        if m:x['tmdb']=m
    d['tmdbRankings']=rankings
    d['tmdbMatchedCount']=len(meta)
    with open(CATALOG+'.tmp','w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
    os.replace(CATALOG+'.tmp',CATALOG)
    print('DONE tmdbMatchedCount=',len(meta),flush=True)

if __name__=='__main__':main()
