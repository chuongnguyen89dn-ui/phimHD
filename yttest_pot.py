import re, time
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError
from flask import jsonify, Response, request, stream_with_context
from app_trailer import app

TEST_YT='AjSxpi8E9WE'
POT_URL='https://ivy-pot-test.onrender.com'
_cache={}

def _probe(obj):
    if not obj or not obj.get('url'): return False
    h=dict(obj.get('headers') or {});h['Range']='bytes=0-1'
    try:
        with urlopen(UrlRequest(obj['url'],headers=h),timeout=15) as r:
            ok=getattr(r,'status',200) in (200,206) and bool(r.read(2))
            print('yttestpot probe',obj.get('format_id'),getattr(r,'status',200),ok,flush=True)
            return ok
    except Exception as e:
        print('yttestpot probe fail',type(e).__name__,str(e)[:220],flush=True);return False

def _resolve(yid):
    now=time.time();c=_cache.get(yid)
    if c and now-c[0]<300:return c[1]
    try:
        import yt_dlp
        opts={
            'quiet':True,'no_warnings':False,'noplaylist':True,'socket_timeout':20,'retries':1,
            'format':'18/best[ext=mp4][vcodec!=none][acodec!=none]',
            'extractor_args':{
                'youtube':{'player_client':['mweb']},
                'youtubepot-bgutilhttp':{'base_url':[POT_URL]}
            }
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info=ydl.extract_info('https://www.youtube.com/watch?v='+yid,download=False)
        obj={'url':info.get('url'),'headers':info.get('http_headers') or {},'format_id':str(info.get('format_id') or '')}
        if obj['url'] and _probe(obj):
            _cache[yid]=(now,obj);return obj
    except Exception as e:
        print('yttestpot resolve fail',yid,type(e).__name__,str(e)[:300],flush=True)
    return None

def proxy(yid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',yid):return Response('bad id',400)
    obj=_resolve(yid)
    if not obj:return Response('PO-token YouTube resolve failed',502)
    h=dict(obj.get('headers') or {})
    if request.headers.get('Range'):h['Range']=request.headers['Range']
    try:up=urlopen(UrlRequest(obj['url'],headers=h),timeout=30)
    except HTTPError as e:
        _cache.pop(yid,None);print('yttestpot upstream http',e.code,flush=True);return Response('upstream http '+str(e.code),502)
    except Exception as e:
        print('yttestpot upstream fail',type(e).__name__,str(e)[:220],flush=True);return Response('upstream failed',502)
    status=getattr(up,'status',200);oh={}
    for k in ('Content-Type','Content-Length','Content-Range','Accept-Ranges','Cache-Control'):
        if up.headers.get(k):oh[k]=up.headers[k]
    oh['Accept-Ranges']='bytes';print('yttestpot proxy hit',yid,obj.get('format_id'),status,request.headers.get('Range',''),flush=True)
    def gen():
        try:
            while True:
                b=up.read(256*1024)
                if not b:break
                yield b
        finally:
            try:up.close()
            except:pass
    return Response(stream_with_context(gen()),status=status,headers=oh,direct_passthrough=True)

def manifest():
    return jsonify({'id':'community.ivy.youtube.pot.test','version':'1.0.0','name':'Ivy❤️ YouTube POT Test','description':'Isolated mweb + PO-token test only','resources':['catalog','meta','stream'],'types':['movie'],'catalogs':[{'type':'movie','id':'ivy_yt_pot_test','name':'🧪 Ivy • YouTube POT Test'}],'idPrefixes':['ivypot_']})

def catalog():
    return jsonify({'metas':[{'id':'ivypot_'+TEST_YT,'type':'movie','name':'YouTube POT Test • '+TEST_YT,'poster':'https://i.ytimg.com/vi/'+TEST_YT+'/hqdefault.jpg','description':'mweb + bgutil PO-token isolated playback test.'}]})

def meta(item_id):
    y=item_id[7:] if item_id.startswith('ivypot_') else TEST_YT
    return jsonify({'meta':{'id':'ivypot_'+y,'type':'movie','name':'YouTube POT Test • '+y,'poster':'https://i.ytimg.com/vi/'+y+'/hqdefault.jpg','description':'Isolated PO-token playback test.'}})

def stream(item_id):
    y=item_id[7:] if item_id.startswith('ivypot_') else TEST_YT
    return jsonify({'streams':[{'name':'Ivy❤️ POT TEST','title':'🧪 YouTube mweb + PO Token','url':'https://phimhd.onrender.com/yttestpot/proxy/'+y+'.mp4','behaviorHints':{'notWebReady':True}}]})

app.add_url_rule('/yttestpot/manifest.json','yttestpot_manifest',manifest)
app.add_url_rule('/yttestpot/catalog/movie/ivy_yt_pot_test.json','yttestpot_catalog',catalog)
app.add_url_rule('/yttestpot/meta/movie/<item_id>.json','yttestpot_meta',meta)
app.add_url_rule('/yttestpot/stream/movie/<item_id>.json','yttestpot_stream',stream)
app.add_url_rule('/yttestpot/proxy/<yid>.mp4','yttestpot_proxy',proxy)
