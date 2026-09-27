import re
from curl_cffi import requests
u='https://rophims.team/phim/loi-tinh-doi-lua-phan-1'
r=requests.get(u,impersonate='chrome',timeout=30)
print('HTTP',r.status_code,'LEN',len(r.text))
h=r.text.replace('\\/','/')
for pat in [r'datePublished',r'year',r'release',r'tmdbData',r'moviePosterUrl',r'2050',r'2026']:
    print('\nPATTERN',pat)
    ms=list(re.finditer(pat,h,re.I))
    print('COUNT',len(ms))
    for m in ms[:20]:
        print(h[max(0,m.start()-180):m.end()+260].replace('\n',' '))
