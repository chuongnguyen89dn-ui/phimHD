import re,json,html
from curl_cffi import requests
u="https://rophims.team/xem-phim/gioi-quy-toc?tap=tap-1&sv=0"
r=requests.get(u,headers={"User-Agent":"Mozilla/5.0 Chrome/146 Safari/537.36","Referer":"https://rophims.team/phim/gioi-quy-toc"},timeout=25,impersonate="chrome")
t=r.text.replace("\\/","/")
print("STATUS",r.status_code,"LEN",len(t))
for k in ["var episodes","episodes =","link_embed","link_m3u8","streamc.xyz","streamvsmov","embed.php","master.m3u8","currentEpisode","server_data"]:
    print("COUNT",k,t.lower().count(k.lower()))
for pat in [r'https?://[^"\'<>\s]+',r'fetch\(([^)]{0,300})\)',r'axios[^;]{0,500}',r'/api/[^"\'<>\s]+']:
    vals=re.findall(pat,t,re.I)
    print("PAT",pat,"N",len(vals))
    for v in vals[:40]: print(str(v)[:500])
for k in ["link_embed","link_m3u8","server_data","currentEpisode","episodes"]:
    for m in list(re.finditer(k,t,re.I))[:8]:
        print("SNIP",k, t[max(0,m.start()-350):m.start()+1000].replace("\n"," ")[:1500])
