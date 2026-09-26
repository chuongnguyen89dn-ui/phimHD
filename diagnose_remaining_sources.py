import json,re,html,urllib.parse
from curl_cffi import requests

UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1"
SAMPLES=[
("streamc13","https://embed13.streamc.xyz/embed.php?hash=7d16a34b60bd28dee122fa48cf872573"),
("streamc14","https://embed14.streamc.xyz/embed.php?hash=b898a6c0d2a800adf5065595f1ae9ea3"),
("shameless6","https://rophims.team/phim/mat-day-phan-6"),
("shameless7","https://rophims.team/phim/mat-day-phan-7"),
]
def scan(name,u):
    out={"name":name,"url":u}
    try:
        r=requests.get(u,headers={"User-Agent":UA,"Referer":"https://rophims.team/"},timeout=25,impersonate="chrome",allow_redirects=True)
        t=r.text.replace("\\/","/")
        out.update(status=r.status_code,final=str(r.url),length=len(t))
        out["m3u8"]=list(dict.fromkeys(re.findall(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',t,re.I)))[:20]
        out["iframes"]=list(dict.fromkeys(re.findall(r'<iframe[^>]+src=["\']([^"\']+)',t,re.I)))[:20]
        out["scripts"]=list(dict.fromkeys(re.findall(r'<script[^>]+src=["\']([^"\']+)',t,re.I)))[:30]
        imgs=[]
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
        ]: imgs += re.findall(pat,t,re.I)
        out["metaImages"]=list(dict.fromkeys(html.unescape(x) for x in imgs))[:20]
        # relevant snippets only
        snippets=[]
        for key in ["m3u8","sources","file:","source:","playlist","jwplayer","hash","poster","image"]:
            for m in list(re.finditer(key,t,re.I))[:5]:
                snippets.append(t[max(0,m.start()-180):m.start()+420])
        out["snippets"]=snippets[:30]
        # inspect external player scripts for embedded HLS/endpoint clues
        js=[]
        for s in out["scripts"][:12]:
            su=urllib.parse.urljoin(str(r.url),html.unescape(s))
            if not su.startswith("http"): continue
            try:
                rr=requests.get(su,headers={"User-Agent":UA,"Referer":str(r.url)},timeout=12,impersonate="chrome")
                body=rr.text.replace("\\/","/")
                hits=list(dict.fromkeys(re.findall(r'https?://[^"\'<>\\\s]+?\.m3u8(?:\?[^"\'<>\\\s]*)?',body,re.I)))
                clues=[]
                for k in ["m3u8","ajax","api","hash","playlist","source","file"]:
                    if re.search(k,body,re.I): clues.append(k)
                if hits or clues:
                    js.append({"url":su,"status":rr.status_code,"length":len(body),"m3u8":hits[:10],"clues":clues,
                               "snippets":[body[max(0,m.start()-120):m.start()+300] for m in list(re.finditer(r"m3u8|ajax|api|hash|playlist",body,re.I))[:8]]})
            except Exception as e: js.append({"url":su,"error":repr(e)})
        out["scriptInspection"]=js[:12]
        if "streamc.xyz" in str(r.url):
            proto=[]
            for j in js:
                for sn in j.get("snippets",[]):
                    if any(k in sn for k in ["request_grant","bootstrap_format","fetch(","playlist_format","grant","bootstrap"]):
                        proto.append(sn)
            out["protocolContexts"]=proto[:40]
    except Exception as e: out["error"]=repr(e)
    return out
json.dump({"results":[scan(n,u) for n,u in SAMPLES]},open("remaining_source_diagnostics.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps([{"name":x["name"],"status":x.get("status"),"length":x.get("length"),"m3u8":len(x.get("m3u8",[])),"images":x.get("metaImages")} for x in json.load(open("remaining_source_diagnostics.json"))["results"]],ensure_ascii=False))