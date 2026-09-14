import json, re, html, os, time
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/')
OUT=os.environ.get('IVY_SITEMAP_OUT','ivy_sitemap.json')
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1'
SECTIONS=[
 'Điện ảnh Hàn Quốc','Mọt phim Hoa Ngữ','Thiên đường Phim Thái','Phim US-UK Mới',
 'Phim Điện Ảnh Mới Cóong','Dấu ấn điện ảnh Việt','Đêm Kinh Hoàng','Mê Cung Phim Nhật',
 'Phim Bộ Đã Hoàn Thành','Hành Động Nghẹt Thở','Trinh Thám & Bí Ẩn','Tinh Hoa Điện Ảnh Hồng Kông',
 'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Thế giới Anime','Cổ Trang Trung Quốc',
 'Mãn Nhãn với Phim Chiếu Rạp','Sắp Lên Sóng'
]
TOP10={'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay'}
MAX_PAGES=180
BATCH=12


def fetch(u,timeout=20):
    try:
        req=Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Referer':BASE+'/'})
        with urlopen(req,timeout=timeout) as r:return r.read().decode('utf-8','replace').replace('\\/','/')
    except Exception as e:
        print('fetch failed',u,type(e).__name__,e);return ''


def movie_urls(txt):
    out=[]
    for href in re.findall(r'href=["\']([^"\']+)',txt,re.I):
        if '/phim/' not in href:continue
        u=urljoin(BASE+'/',html.unescape(href)).split('#')[0]
        if u not in out:out.append(u)
    return out


def pos(txt,label,start=0):
    vals=(label,html.escape(label,quote=False));ps=[]
    for v in vals:
        p=txt.find(v,start)
        if p>=0:ps.append(p)
    return min(ps) if ps else -1


def listing_link(seg):
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',seg,re.I|re.S):
        text=html.unescape(re.sub('<[^>]+>',' ',m.group(2)))
        if re.search(r'(?i)xem\s*(?:thêm|toàn\s*bộ|tất\s*cả)|tất\s*cả',text):
            u=urljoin(BASE+'/',html.unescape(m.group(1))).split('#')[0]
            if '/phim/' not in u:return u
    return None


def page_num(u):
    q=parse_qs(urlparse(u).query)
    if q.get('page') and str(q['page'][0]).isdigit():return int(q['page'][0])
    m=re.search(r'/(?:page|trang)[-/](\d+)',u,re.I)
    return int(m.group(1)) if m else None


def page_url(seed,n):
    if n<=1:return seed
    if re.search(r'([?&])page=\d+',seed):return re.sub(r'([?&])page=\d+',r'\1page='+str(n),seed)
    return seed+('&' if '?' in seed else '?')+'page='+str(n)


def crawl_listing(seed):
    first=fetch(seed)
    if not first:return [],0
    urls=movie_urls(first);seen=set(urls);last_good=1
    # Source only exposes nearby page links (1,2,...) on page 1. Do not treat 2 as the last page.
    # Probe in parallel batches until two consecutive pages contain no new movie URLs.
    consecutive_empty=0
    start=2
    while start<=MAX_PAGES and consecutive_empty<2:
        nums=list(range(start,min(MAX_PAGES+1,start+BATCH)))
        pages={}
        with ThreadPoolExecutor(max_workers=len(nums)) as ex:
            futs={ex.submit(fetch,page_url(seed,n)):n for n in nums}
            for f in as_completed(futs):pages[futs[f]]=f.result()
        stop=False
        for n in nums:
            rows=movie_urls(pages.get(n,''))
            new=[u for u in rows if u not in seen]
            if new:
                consecutive_empty=0;last_good=n
                urls.extend(new);seen.update(new)
            else:
                consecutive_empty+=1
                if consecutive_empty>=2:
                    stop=True;break
        if stop:break
        start+=BATCH
    return urls,last_good


def main():
    home=fetch(BASE+'/phimhay')
    if not home:raise SystemExit('cannot fetch source home')
    start=max(0,pos(home,'Bạn đang quan tâm gì?'))
    found=[]
    for i,label in enumerate(SECTIONS):
        p=pos(home,label,start)
        if p>=0:found.append((p,i,label))
    found.sort();out={'source':BASE,'generatedAt':int(time.time()),'sections':[]}
    for idx,(p,i,label) in enumerate(found):
        end=found[idx+1][0] if idx+1<len(found) else len(home)
        seg=home[p:end];home_urls=movie_urls(seg);listing=listing_link(seg)
        if label in TOP10 or not listing:
            all_urls=home_urls;pages=1
        else:
            crawled,pages=crawl_listing(listing)
            all_urls=[]
            for u in home_urls+crawled:
                if u not in all_urls:all_urls.append(u)
        row={'label':label,'home':home_urls,'listing':listing,'pages':pages,'count':len(all_urls),'urls':all_urls}
        out['sections'].append(row)
        print(label,'home=',len(home_urls),'pages=',pages,'items=',len(all_urls),'listing=',listing)
    with open(OUT,'w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
    print('wrote',OUT,'sections=',len(out['sections']))

if __name__=='__main__':main()
