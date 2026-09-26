import re,html
from curl_cffi import requests
from urllib.parse import urljoin
u="https://rophims.team/phimhay"
r=requests.get(u,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"vi-VN,vi;q=0.9"},timeout=30,impersonate="chrome")
r.raise_for_status()
h=r.text.replace("\\/","/")
label="Phim Điện Ảnh Mới Cóng"
p=h.find(label)
print("POS",p,"LEN",len(h))
if p<0:
    raise SystemExit(2)
# find next known section label
labels=["Dấu ấn điện ảnh Việt","Đêm Kinh Hoàng","Mê Cung Phim Nhật"]
ends=[h.find(x,p+len(label)) for x in labels if h.find(x,p+len(label))>0]
end=min(ends) if ends else min(len(h),p+50000)
seg=h[p:end]
print("SEG_LEN",len(seg))
for m in re.finditer(r'href=["\']([^"\']+)["\']',seg,re.I):
    href=html.unescape(m.group(1))
    print("HREF",href)
print("PHIM_HREF_COUNT",sum(1 for x in re.findall(r'href=["\']([^"\']+)["\']',seg,re.I) if "/phim/" in x))
print("XEM_HREF_COUNT",sum(1 for x in re.findall(r'href=["\']([^"\']+)["\']',seg,re.I) if "/xem-phim/" in x))
print("SNIP",re.sub(r"\s+"," ",seg[:12000]))
