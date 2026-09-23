import json, os, re, html, time
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

CATALOG=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
URL_RE=re.compile(r'https?://[^"\'<>\\\s]+',re.I)
LIMIT=int(os.environ.get('IVY_PLAYBACK_AUDIT_LIMIT','0'))
PLAYBACK_WORKERS=int(os.environ.get('IVY_PLAYBACK_WORKERS','24'))

def fetch(u):
    headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8','Referer':'https://rophims.team/'}
    try:
        from curl_cffi import requests as curl_requests
        r=curl_requests.get(u,headers=headers,timeout=18,impersonate='chrome',allow_redirects=True)
        if r.status_code < 400 and r.text:return r.text.replace('\\/','/')
        print('[audit fetch curl]',r.status_code,u,flush=True)
    except Exception as e:
        print('[audit fetch curl]',type(e).__name__,str(e)[:160],u,flush=True)
    try:
        with urlopen(Request(u,headers=headers),timeout=15) as r:
            return r.read().decode('utf-8','replace').replace('\\/','/')
    except Exception as e:
        print('[audit fetch urllib]',type(e).__name__,str(e)[:160],u,flush=True)
        return ''

def extract_array_after(h,marker):
    p=h.find(marker)
    if p<0:return None
    p=h.find('[',p)
    if p<0:return None
    depth=0;quote=None;esc=False
    for i in range(p,len(h)):
        ch=h[i]
        if quote:
            if esc:esc=False
            elif ch=='\\':esc=True
            elif ch==quote:quote=None
            continue
        if ch in ('"',"'"):quote=ch;continue
        if ch=='[':depth+=1
        elif ch==']':
            depth-=1
            if depth==0:
                try:return json.loads(h[p:i+1])
                except:return None
    return None

def episode_no(item):
    text=' '.join(str(item.get(k) or '') for k in ('slug','name','filename'))
    m=re.search(r'(?i)(?:tập|tap|episode)[-_ ]*(\d+)',text)
    if not m:m=re.search(r'\b(\d+)\b',text)
    return int(m.group(1)) if m else None

def collect_sources(arr,out):
    if not isinstance(arr,list):return
    seen={(str(x.get('server') or '').strip().lower(),x.get('episode'),str(x.get('url') or '').strip()) for x in out}
    for srv in arr:
        if not isinstance(srv,dict):continue
        sname=str(srv.get('server_name') or srv.get('name') or 'Nguồn')
        for item in srv.get('server_data') or []:
            if not isinstance(item,dict):continue
            m3u8=item.get('link_m3u8') or ''
            embed=item.get('link_embed') or ''
            u=m3u8 or embed
            if not u:continue
            ep=episode_no(item)
            row={
                'server':sname,
                'episode':ep,
                'name':str(item.get('name') or item.get('slug') or item.get('filename') or ''),
                'slug':str(item.get('slug') or ''),
                'link_m3u8':m3u8,
                'link_embed':embed,
                'url':u
            }
            k=(row['server'].strip().lower(),row['episode'],row['url'].strip())
            if k not in seen:
                seen.add(k);out.append(row)

def probe(x):
    detail_url=x.get('url','')
    detail=fetch(detail_url)
    path=re.sub(r'^https?://[^/]+','',detail_url)
    base_watch='https://rophims.team'+path.replace('/phim/','/xem-phim/',1)
    first_watch=base_watch.split('?',1)[0]+'?tap=tap-1&sv=0'
    watch=fetch(first_watch)

    bodies=[detail,watch]
    direct=[]
    sources=[]
    for body in bodies:
        for hls in HLS_RE.findall(body or ''):
            hls=hls.strip()
            if hls and hls not in direct:direct.append(hls)
        arr=extract_array_after(body or '','var episodes =') or extract_array_after(body or '','episodes =') or []
        collect_sources(arr,sources)

    watch_urls=[]
    for href in re.findall(r'href=["\']([^"\']*?/xem-phim/[^"\']*)["\']',detail or '',re.I):
        u=html.unescape(href).replace('\\/','/')
        if u.startswith('/'):u='https://rophims.team'+u
        elif not u.startswith('http'):u='https://rophims.team/'+u.lstrip('/')
        if u not in watch_urls:watch_urls.append(u)
    if first_watch not in watch_urls:watch_urls.insert(0,first_watch)

    # If the source already exposed its full episode/server table, keep those
    # exact links. Only fetch extra watch pages for episodes that still have no
    # harvested source, avoiding thousands of redundant requests.
    known_eps={s.get('episode') for s in sources if s.get('episode')}
    missing=[]
    for u in watch_urls:
        m=re.search(r'(?i)(?:tap=)?tap[-_ ]?(\d+)',u)
        ep=int(m.group(1)) if m else None
        if ep and ep not in known_eps:missing.append((ep,u))
    for ep,u in missing[:80]:
        body=fetch(u)
        for hls in HLS_RE.findall(body or ''):
            if hls not in direct:direct.append(hls)
        arr=extract_array_after(body or '','var episodes =') or extract_array_after(body or '','episodes =') or []
        before=len(sources);collect_sources(arr,sources)
        if len(sources)==before:
            # Preserve the real watch URL as a source even if the player hides
            # the final HLS behind its own embed JavaScript.
            sources.append({'server':'RoPhim','episode':ep,'name':f'Tập {ep}','slug':f'tap-{ep}','link_m3u8':'','link_embed':u,'url':u})

    return {
        'direct':direct[:32],
        'episodeSources':sources,
        'watchUrls':watch_urls,
        'hasPlayback':bool(direct or sources),
        'fetchOk':bool(detail or watch),
        'watchUrl':first_watch,
        'harvestedFrom':'https://rophims.team'
    }

def main():
    with open(CATALOG,encoding='utf-8') as f:d=json.load(f)
    movies=d.get('movies') or [];by={x.get('url'):x for x in movies if x.get('url')}
    orders=d.get('sourceOrders') or {};ordered=[]
    for key in ('home','movies','series'):
        for u in orders.get(key) or []:
            if u in by and u not in ordered:ordered.append(u)
    for x in movies:
        u=x.get('url')
        if u and u not in ordered:ordered.append(u)
    targets=ordered if LIMIT<=0 else ordered[:LIMIT]
    results={};done=0
    with ThreadPoolExecutor(max_workers=PLAYBACK_WORKERS) as ex:
        fs={ex.submit(probe,by[u]):u for u in targets}
        for f in as_completed(fs):
            u=fs[f];done+=1
            try:p=f.result()
            except Exception as e:p={'direct':[],'episodeSources':[],'hasPlayback':False,'fetchOk':False,'watchUrl':'','error':str(e)}
            results[u]=p
            print(f"[harvest] {done}/{len(targets)} {'OK' if p.get('hasPlayback') else 'NO-LINK'} {by[u].get('title','')}",flush=True)
    ok=0;bad=[]
    for u in targets:
        x=by[u];p=results.get(u) or {}
        if p.get('fetchOk'):
            x['playbackHints']={k:v for k,v in p.items() if k!='fetchOk'}
        if p.get('hasPlayback'):ok+=1
        else:bad.append({'title':x.get('title'),'url':u,'fetchOk':p.get('fetchOk',False),'error':p.get('error','')})
    d['playbackHarvest']={'checked':len(targets),'withLinks':ok,'missing':len(bad),'workers':PLAYBACK_WORKERS,'missingItems':bad[:100]}
    d['playbackAudit']={'checked':len(targets),'playable':ok,'missing':len(bad),'workers':PLAYBACK_WORKERS,'missingItems':bad[:100]}
    tmp=CATALOG+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
    os.replace(tmp,CATALOG)
    print('PLAYBACK_HARVEST',json.dumps(d['playbackHarvest'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
