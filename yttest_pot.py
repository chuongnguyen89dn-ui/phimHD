import os, re, time
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError
from flask import jsonify, Response, request, stream_with_context
from app_trailer import app

TEST_YT='AjSxpi8E9WE'
POT_URL=os.environ.get('YOUTUBE_POT_URL','https://ivy-pot-test.onrender.com')
_cache={};_formats={};_diag={}

def _probe(obj):
    if not obj or not obj.get('url'): return False
    h=dict(obj.get('headers') or {});h['Range']='bytes=0-1'
    try:
        with urlopen(UrlRequest(obj['url'],headers=h),timeout=15) as r:
            ok=getattr(r,'status',200) in (200,206) and bool(r.read(2));print('yttestpot probe',obj.get('format_id'),getattr(r,'status',200),ok,flush=True);return ok
    except Exception as e: print('yttestpot probe fail',obj.get('format_id'),type(e).__name__,str(e)[:220],flush=True);return False

def _extract(yid):
    import yt_dlp
    # Try current clients individually. This avoids a URL/token from one client being
    # accidentally paired with another client's context.
    clients=['web_embedded','android_vr','mweb','web_safari']
    errors=[]
    for client in clients:
        opts={'quiet':True,'no_warnings':False,'noplaylist':True,'socket_timeout':20,'retries':1,'extract_flat':False,
              'extractor_args':{'youtube':{'player_client':[client]},'youtubepot-bgutilhttp':{'base_url':[POT_URL]}}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info=ydl.extract_info('https://www.youtube.com/watch?v='+yid,download=False)
            n=len(info.get('formats') or []);print('yttestpot extract',client,'formats',n,flush=True)
            if n:_diag[yid]={'client':client,'formatsSeen':n,'errors':errors};return info,client
            errors.append(client+': no formats')
        except Exception as e:
            msg=type(e).__name__+': '+str(e)[:260];errors.append(client+': '+msg);print('yttestpot extract fail',client,msg,flush=True)
    _diag[yid]={'client':None,'formatsSeen':0,'errors':errors};raise RuntimeError('all clients failed')

def formats(yid):
    now=time.time();c=_formats.get(yid)
    if c and now-c[0]<300:return c[1]
    try:
        info,client=_extract(yid);rows=[]
        for f in info.get('formats') or []:
            u=f.get('url')
            if not u:continue
            obj={'url':u,'headers':f.get('http_headers') or info.get('http_headers') or {},'format_id':str(f.get('format_id') or '')}
            if _probe(obj):rows.append({'format_id':obj['format_id'],'height':f.get('height'),'ext':f.get('ext'),'vcodec':f.get('vcodec'),'acodec':f.get('acodec'),'fps':f.get('fps'),'filesize':f.get('filesize') or f.get('filesize_approx'),'client':client,'url':u,'headers':obj['headers']})
        rows.sort(key=lambda x:(x.get('height') or 0,x.get('filesize') or 0),reverse=True);_formats[yid]=(now,rows)
        _diag.setdefault(yid,{}).update({'verifiedCount':len(rows)});print('yttestpot verified formats',yid,[(x['format_id'],x['height'],x['ext']) for x in rows[:20]],flush=True);return rows
    except Exception as e:print('yttestpot formats fail',yid,type(e).__name__,str(e)[:300],flush=True);return []

def _resolve(yid):
    now=time.time();c=_cache.get(yid)
    if c and now-c[0]<300:return c[1]
    rows=formats(yid);candidates=[x for x in rows if x.get('ext')=='mp4' and x.get('vcodec') not in (None,'none') and x.get('acodec') not in (None,'none')]
    if not candidates:candidates=rows
    if not candidates:return None
    obj=candidates[0];_cache[yid]=(now,obj);return obj

def status(yid):
    rows=formats(yid);safe=[{k:v for k,v in x.items() if k not in ('url','headers')} for x in rows]
    return jsonify({'ok':bool(rows),'videoId':yid,'verifiedCount':len(rows),'potProvider':POT_URL,'diagnostic':_diag.get(yid,{}),'formats':safe})

def proxy(yid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',yid):return Response('bad id',400)
    obj=_resolve(yid)
    if not obj:return Response('No verified YouTube media URL',502)
    h=dict(obj.get('headers') or {})
    if request.headers.get('Range'):h['Range']=request.headers['Range']
    try:up=urlopen(UrlRequest(obj['url'],headers=h),timeout=30)
    except HTTPError as e:_cache.pop(yid,None);print('yttestpot upstream http',e.code,flush=True);return Response('upstream http '+str(e.code),502)
    except Exception as e:print('yttestpot upstream fail',type(e).__name__,str(e)[:220],flush=True);return Response('upstream failed',502)
    status_code=getattr(up,'status',200);oh={}
    for k in ('Content-Type','Content-Length','Content-Range','Accept-Ranges','Cache-Control'):
        if up.headers.get(k):oh[k]=up.headers[k]
    oh['Accept-Ranges']='bytes';print('yttestpot proxy hit',yid,obj.get('format_id'),status_code,request.headers.get('Range',''),flush=True)
    def gen():
        try:
            while True:
                b=up.read(256*1024)
                if not b:break
                yield b
        finally:
            try:up.close()
            except:pass
    return Response(stream_with_context(gen()),status=status_code,headers=oh,direct_passthrough=True)

def manifest():return jsonify({'id':'community.ivy.youtube.pot.test','version':'1.3.0','name':'Ivy❤️ YouTube Test','description':'Isolated verified-format test only','resources':['catalog','meta','stream'],'types':['movie'],'catalogs':[{'type':'movie','id':'ivy_yt_pot_test','name':'🧪 Ivy • YouTube Test'}],'idPrefixes':['ivypot_']})
def catalog():return jsonify({'metas':[{'id':'ivypot_'+TEST_YT,'type':'movie','name':'YouTube Test • '+TEST_YT,'poster':'https://i.ytimg.com/vi/'+TEST_YT+'/hqdefault.jpg'}]})
def meta(item_id):
    y=item_id[7:] if item_id.startswith('ivypot_') else TEST_YT
    return jsonify({'meta':{'id':'ivypot_'+y,'type':'movie','name':'YouTube Test • '+y,'poster':'https://i.ytimg.com/vi/'+y+'/hqdefault.jpg'}})
def stream(item_id):
    y=item_id[7:] if item_id.startswith('ivypot_') else TEST_YT;base=request.host_url.rstrip('/')
    return jsonify({'streams':[{'name':'Ivy❤️ TEST','title':'🧪 Verified YouTube media','url':base+'/yttestpot/proxy/'+y+'.mp4','behaviorHints':{'notWebReady':True}}]})

app.add_url_rule('/yttestpot/manifest.json','yttestpot_manifest',manifest)
app.add_url_rule('/yttestpot/catalog/movie/ivy_yt_pot_test.json','yttestpot_catalog',catalog)
app.add_url_rule('/yttestpot/meta/movie/<item_id>.json','yttestpot_meta',meta)
app.add_url_rule('/yttestpot/stream/movie/<item_id>.json','yttestpot_stream',stream)
app.add_url_rule('/yttestpot/status/<yid>.json','yttestpot_status',status)
app.add_url_rule('/yttestpot/proxy/<yid>.mp4','yttestpot_proxy',proxy)
