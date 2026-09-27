import re
from curl_cffi import requests
for slug in ['loi-tinh-doi-lua-phan-1','nguoi-thu-ba']:
    u='https://rophims.team/phim/'+slug
    r=requests.get(u,impersonate='chrome',timeout=30)
    h=r.text.replace('\\/','/')
    pm=re.search(r'''var\s+moviePosterUrl\s*=\s*["']([^"']+)''',h,re.I)
    tm=re.search(r'''var\s+movieThumbUrl\s*=\s*["']([^"']+)''',h,re.I)
    title=re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',h,re.I)
    print(slug,'HTTP',r.status_code)
    print('TITLE',title.group(1) if title else None)
    print('POSTER',pm.group(1) if pm else None)
    print('THUMB',tm.group(1) if tm else None)
