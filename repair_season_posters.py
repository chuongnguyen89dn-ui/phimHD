import json,re,html,time,sys,collections
from curl_cffi import requests

CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def family_key(title):
    s=str(title or "").lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*\d+\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" -–—:()")

def season_no(title):
    m=re.search(r"(?i)(?:phần|season)\s*(\d+)",str(title or ""))
    return int(m.group(1)) if m else None

def fetch_poster(url):
    try:
        r=requests.get(url,headers={"User-Agent":UA,"Referer":"https://rophims.team/"},timeout=20,impersonate="chrome",allow_redirects=True)
        if r.status_code>=400:return None
        t=r.text.replace("\\/","/")
        m=re.search(r'''var\s+moviePosterUrl\s*=\s*["']([^"']+)''',t,re.I)
        if not m:return None
        return html.unescape(m.group(1)).strip()
    except Exception as e:
        print("fetch_error",url,repr(e),flush=True);return None

d=json.load(open(CAT,encoding="utf-8"))
rows=[x for x in d.get("movies",[]) if isinstance(x,dict)]
fams=collections.defaultdict(list)
for x in rows:
    if season_no(x.get("title")):
        fams[family_key(x.get("title"))].append(x)

targets=[]
for k,grp in fams.items():
    if len(grp)<2:continue
    posters=[x.get("poster") for x in grp if x.get("poster")]
    if len(posters)>=2 and len(set(posters))<len(posters):
        targets.append((k,grp))

changed=0;resolved=0
for idx,(k,grp) in enumerate(targets,1):
    family_changed=0
    for x in grp:
        u=x.get("url")
        if not u:continue
        p=fetch_poster(u)
        if p and p!=x.get("poster"):
            print("poster",x.get("title"),"->",p,flush=True)
            x["poster"]=p;changed+=1;family_changed+=1
        time.sleep(0.08)
    after=[x.get("poster") for x in grp if x.get("poster")]
    if len(after)>=2 and len(set(after))==len(after):resolved+=1
    print(f"[{idx}/{len(targets)}] {k} changed={family_changed} unique={len(set(after))}/{len(after)}",flush=True)

json.dump(d,open(CAT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print({"duplicateFamiliesBefore":len(targets),"familiesResolved":resolved,"postersChanged":changed},flush=True)
