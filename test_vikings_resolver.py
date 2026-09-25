import json,os
import app_full as core

CAT='rophim_catalog.json'
d=json.load(open(CAT,encoding='utf-8'))
core._catalog_cache.update(at=10**18,data=d)
rows=[x for x in d.get('movies',[]) if 'huyen-thoai-vikings-phan-1' in (x.get('url') or '')]
x=rows[0]
m=core.base_meta(x,True)
vid=next(v['id'] for v in m.get('videos',[]) if v.get('season')==1 and v.get('episode')==1)
with core.app.test_request_context():
    resp=core.stream('series',vid)
    data=resp.get_json()
print('VIDEO_ID',vid)
print(json.dumps(data,ensure_ascii=False,indent=2))
streams=data.get('streams') or []
assert streams, 'VIKINGS_STREAM_EMPTY'
assert any('streamvsmov.com/stream/' in s.get('url','') and 'master.m3u8' in s.get('url','') for s in streams), streams
print('VIKINGS_OK',streams[0]['url'])
