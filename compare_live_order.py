import json,re,html
from urllib.parse import urljoin,urlparse
from curl_cffi import requests

SRC="https://rophims.team/phimhay"
PROD="https://phimhd-upos.onrender.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

def get(u):
    r=requests.get(u,headers={"User-Agent":UA,"Accept":"application/json,text/html,*/*","Referer":"https://rophims.team/"},timeout=30,impersonate="chrome",allow_redirects=True)
    print("GET",u,r.status_code,len(r.text),flush=True)
    r.raise_for_status()
    return r.text

def canon(u):
    if not u:return ""
    p=urlparse(u)
    path=p.path.rstrip("/")
    return path.lower()

labels=["Điện ảnh Hàn Quốc","Mọt phim Hoa Ngữ","Thiên đường Phim Thái","Phim US-UK Mới","Phim Điện Ảnh Mới Cóng","Phim Điện Ảnh Mới Cóong","Dấu ấn điện ảnh Việt","Đêm Kinh Hoàng","Mê Cung Phim Nhật","Phim Bộ Đã Hoàn Thành","Hành Động Nghẹt Thở","Trinh Thám & Bí Ẩn","Tinh Hoa Điện Ảnh Hồng Kông","Top 10 phim bộ hôm nay","Top 10 phim lẻ hôm nay","Thế giới Anime","Cổ Trang Trung Quốc","Mãn Nhãn với Phim Chiếu Rạp","Sắp Lên Sóng"]

h=get(SRC)
# find actual section positions in page order
pos=[]
for lab in labels:
    for pat in [lab,html.escape(lab,quote=False)]:
        i=h.find(pat)
        if i>=0:
            pos.append((i,lab));break
# de-dupe aliases for movie section, preserving earliest
pos.sort()
seenlab=set();ordered=[]
for i,lab in pos:
    norm="Phim Điện Ảnh Mới Cóng" if lab in ("Phim Điện Ảnh Mới Cóng","Phim Điện Ảnh Mới Cóong") else lab
    if norm in seenlab:continue
    seenlab.add(norm);ordered.append((i,norm))

source={}
for n,(p,lab) in enumerate(ordered):
    end=ordered[n+1][0] if n+1<len(ordered) else len(h)
    seg=h[p:end]
    urls=[]
    for href in re.findall(r'href=["\']([^"\']+)',seg,re.I):
        u=urljoin(SRC,html.unescape(href))
        if "/phim/" in u:
            k=canon(u)
            if k and k not in [canon(x) for x in urls]:urls.append(u)
    source[lab]=urls

man=json.loads(get(PROD+"/manifest.json"))
cats=man.get("catalogs") or []
home=[c for c in cats if str(c.get("id","")).startswith("ivy_home_")]
prod_labels=[re.sub(r"^❤️\s*Ivy\s*•\s*","",str(c.get("name") or "")).strip() for c in home]

report={
 "productionVersion":man.get("version"),
 "sourceSectionOrder":[lab for _,lab in ordered],
 "addonSectionOrder":prod_labels,
 "sectionOrderExact":prod_labels==[lab for _,lab in ordered],
 "rows":[]
}
for c,lab in zip(home,prod_labels):
    cid=c["id"]; typ=c.get("type") or "movie"
    try:d=json.loads(get(f"{PROD}/catalog/{typ}/{cid}.json"))
    except Exception as e:
        report["rows"].append({"label":lab,"error":str(e)});continue
    metas=d.get("metas") or []
    add=[canon(m.get("website")) for m in metas if m.get("website")]
    src=[canon(u) for u in source.get(lab,[])][:len(add)]
    match=sum(1 for a,b in zip(add,src) if a==b)
    report["rows"].append({
      "label":lab,"catalogId":cid,"type":typ,
      "sourceVisibleCount":len(source.get(lab,[])),
      "addonCount":len(metas),
      "compared":min(len(add),len(src)),
      "positionMatches":match,
      "exactPrefix":add[:len(src)]==src if src else False,
      "sourceFirst10":src[:10],
      "addonFirst10":add[:10]
    })

json.dump(report,open("production_order_comparison.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({
 "productionVersion":report["productionVersion"],
 "sectionOrderExact":report["sectionOrderExact"],
 "sourceSectionOrder":report["sourceSectionOrder"],
 "addonSectionOrder":report["addonSectionOrder"],
 "rows":[{k:r.get(k) for k in ("label","compared","positionMatches","exactPrefix","sourceVisibleCount","addonCount","error")} for r in report["rows"]]
},ensure_ascii=False,indent=2))
