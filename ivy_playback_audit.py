import json, os, re, html, time
from urllib.request import Request, urlopen

CATALOG=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
HLS_RE=re.compile(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',re.I)
URL_RE=re.compile(r'https?://[^"\'<>\\\s]+',re.I)
LIMIT=int(os.environ.get('IVY_PLAYBACK_AUDIT_LIMIT','0'))

def fetch(u):
    headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8','Referer':'https://rophim.loan/'}
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

def probe(x):
    h=fetch(x.get('url',''))
    direct=list(dict.fromkeys(HLS_RE.findall(h)))
    arr=extract_array_after(h,'var episodes =') or extract_array_after(h,'episodes =') or []
    sources=[]
    if isinstance(arr,list):
        for srv in arr:
            if not isinstance(srv,dict):continue
            sname=str(srv.get('server_name') or srv.get('name') or 'Nguồn')
            for item in srv.get('server_data') or []:
                if not isinstance(item,dict):continue
                u=item.get('link_m3u8') or item.get('link_embed') or ''
                if u:sources.append({'server':sname,'name':str(item.get('name') or item.get('slug') or ''),'url':u})
    return {'direct':direct[:8],'episodeSources':sources[:100],'hasPlayback':bool(direct or sources),'fetchOk':bool(h)}

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
    ok=0;bad=[]
    targets=ordered if LIMIT<=0 else ordered[:LIMIT]
    for i,u in enumerate(targets,1):
        x=by[u];p=probe(x)
        if p.get('fetchOk'):
            x['playbackHints']={k:v for k,v in p.items() if k!='fetchOk'}
        if p['hasPlayback']:ok+=1
        else:bad.append({'title':x.get('title'),'url':u,'fetchOk':p.get('fetchOk',False)})
        print(f"[playback] {i}/{len(targets)} {'OK' if p['hasPlayback'] else 'NO-LINK'} {x.get('title','')}",flush=True)
        time.sleep(.03)
    d['playbackAudit']={'checked':len(targets),'playable':ok,'missing':len(bad),'missingItems':bad[:50]}
    tmp=CATALOG+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
    os.replace(tmp,CATALOG)
    print('PLAYBACK_AUDIT',json.dumps(d['playbackAudit'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
