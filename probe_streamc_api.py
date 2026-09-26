import json
from curl_cffi import requests

URL="https://embed13.streamc.xyz/embed.php?hash=7d16a34b60bd28dee122fa48cf872573"
HEAD={
 "User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1",
 "Referer":"https://rophims.team/",
 "Origin":"https://embed13.streamc.xyz",
 "Accept":"*/*",
 "Content-Type":"application/json",
}
base={
 "action":"bootstrap",
 "referrer":"https://rophims.team/",
 "frame_origins":["https://rophims.team"],
 "request_grant":True,
 "playlist_format":"hls",
 "pretty_url":True,
 "path_chunks":True,
}
variants=[
 ("omit_bootstrap",dict(base)),
 ("json",{**base,"bootstrap_format":"json"}),
 ("plain",{**base,"bootstrap_format":"plain"}),
 ("hls",{**base,"bootstrap_format":"hls"}),
 ("aesgcm-v1",{**base,"bootstrap_format":"aesgcm-v1"}),
]
out=[]
for name,payload in variants:
    try:
        r=requests.post(URL,headers=HEAD,json=payload,timeout=25,impersonate="chrome",allow_redirects=True)
        row={"name":name,"status":r.status_code,"headers":dict(r.headers),"text":r.text[:30000]}
        try: row["json"]=r.json()
        except: pass
        out.append(row)
        print(name,r.status_code,r.headers.get("content-type"),r.text[:500].replace("\n"," "))
    except Exception as e:
        out.append({"name":name,"error":repr(e)})
json.dump({"url":URL,"results":out},open("streamc_api_probe.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
