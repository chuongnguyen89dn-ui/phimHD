import json, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse
from rophim_catalog_crawler import discover_sitemaps, fetch, text, parse_movie

OUT=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
WORKERS=int(os.environ.get('IVY_SEED_WORKERS','48'))

def one(u):
    final,ct,body=fetch(u)
    h=text(body)
    x=parse_movie(final,h)
    x['source']='ivy-source'
    return x

def main():
    started=datetime.now(timezone.utc).isoformat()
    urls,_=discover_sitemaps()
    urls=sorted({u for u in urls if urlparse(u).path.startswith('/phim/')})
    print(f'[seed] urls={len(urls)} workers={WORKERS}',flush=True)
    movies=[];errors=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fs={ex.submit(one,u):u for u in urls}
        for i,f in enumerate(as_completed(fs),1):
            try:movies.append(f.result())
            except Exception as e:errors.append({'url':fs[f],'error':str(e)})
            if i%100==0 or i==len(urls):print(f'[seed] {i}/{len(urls)} ok={len(movies)} err={len(errors)}',flush=True)
    movies.sort(key=lambda x:(str(x.get('title','')).lower(),str(x.get('slug',''))))
    data={'generatedAt':datetime.now(timezone.utc).isoformat(),'startedAt':started,'crawlerVersion':'ivy-seed-now-v1','stats':{'movieCount':len(movies),'urlCount':len(urls),'errorCount':len(errors)},'movies':movies,'errors':errors}
    tmp=OUT+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,OUT)
    print('DONE',data['stats'],flush=True)
if __name__=='__main__':main()
