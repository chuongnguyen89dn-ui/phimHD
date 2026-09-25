import json,os,re
import app_full as core

CAT='rophim_catalog.json'
d=json.load(open(CAT,encoding='utf-8'))
core._catalog_cache.update(at=10**18,data=d)
rows=[x for x in d.get('movies',[]) if 'huyen-thoai-vikings-phan-1' in (x.get('url') or '')]
print('MATCHES',len(rows))
for x in rows:
    print('TITLE',x.get('title'))
    print('URL',x.get('url'))
    print('HINTS',json.dumps(x.get('playbackHints') or {},ensure_ascii=False)[:12000])
    watch=core.source_watch_url(x.get('url'),1)
    print('WATCH',watch)
    h=core.fetch_text(watch,0,x.get('url'))
    print('WATCH_LEN',len(h))
    for key in ['streamvsmov','iframe','episodes','link_embed','link_m3u8','jwplayer','master.m3u8']:
        print('KEY',key,'COUNT',h.lower().count(key.lower()))
    for m in re.finditer(r'.{0,300}(?:streamvsmov|iframe|link_embed|link_m3u8|episodes).{0,700}',h,re.I|re.S):
        print('SNIP',m.group(0)[:1200].replace('\n',' '))
        break
    print('EXACT',json.dumps(core.exact_watch_episode_sources(watch,1,x.get('url')),ensure_ascii=False)[:8000])
