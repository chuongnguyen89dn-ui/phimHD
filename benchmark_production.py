import time,json,statistics
from curl_cffi import requests
BASE="https://phimhd-upos.onrender.com"
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"
S=requests.Session()
def hit(path):
 t=time.perf_counter()
 try:
  r=S.get(BASE+path,headers={"User-Agent":UA,"Accept":"application/json","Cache-Control":"no-cache"},timeout=90,impersonate="chrome",allow_redirects=True)
  dt=(time.perf_counter()-t)*1000
  return {"ms":round(dt,1),"status":r.status_code,"bytes":len(r.content)}
 except Exception as e:return {"ms":round((time.perf_counter()-t)*1000,1),"status":"ERR","error":repr(e)}
man=hit("/manifest.json");print("MANIFEST",man,flush=True)
m=S.get(BASE+"/manifest.json",headers={"User-Agent":UA},timeout=90,impersonate="chrome").json()
cats=m.get("catalogs") or []
home=next((c for c in cats if str(c.get("id","")).startswith("ivy_home_")),None)
paths=[
 ("manifest","/manifest.json"),
 ("home_first",f"/catalog/{home.get('type','movie')}/{home['id']}.json" if home else "/manifest.json"),
 ("search_conan","/catalog/movie/ivy_search_movie_all/search=conan.json"),
 ("search_tinh","/catalog/movie/ivy_search_movie_all/search=tinh.json"),
 ("search_none","/catalog/movie/ivy_search_movie_all/search=zzzzzzzzzz.json"),
]
out={}
for name,path in paths:
 vals=[]
 for i in range(5):
  x=hit(path);vals.append(x);print(name,i+1,x,flush=True)
 ok=[x["ms"] for x in vals if x["status"]==200]
 out[name]={"path":path,"runs":vals,"medianMs":round(statistics.median(ok),1) if ok else None,"minMs":min(ok) if ok else None,"maxMs":max(ok) if ok else None}
json.dump(out,open("benchmark_production.json","w"),indent=2)
print("SUMMARY",json.dumps({k:{q:v[q] for q in ("medianMs","minMs","maxMs")} for k,v in out.items()}),flush=True)
# trigger benchmark after workflow registration
# benchmark optimized runtime
