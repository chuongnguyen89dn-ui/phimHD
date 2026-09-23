import os, re, json, time, html
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

BASE = os.environ.get("ROPHIM_BASE","https://rophims.team").rstrip("/")
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_catalog.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

CATEGORY_HINTS = [
    "/phimhay", "/phim-le", "/phim-bo", "/hoat-hinh",
    "/phim-chieu-rap", "/tv-shows"
]

def fetch(url, timeout=25):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": BASE + "/"
    })
    with urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.headers.get("Content-Type",""), r.read()

def text(b):
    return b.decode("utf-8", "replace")

def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return re.sub(r"\s+", " ", s).strip()

def abs_url(u, base=BASE):
    try:
        v = urljoin(base, html.unescape(u))
        p = urlparse(v)
        if p.scheme in ("http","https") and p.hostname in ("rophims.team","www.rophims.team","rophim.loan","www.rophim.loan"):
            if p.hostname in ("rophim.loan","www.rophim.loan"):
                b=urlparse(BASE);v=urlunparse((b.scheme,b.netloc,p.path,p.params,p.query,""))
            return v.split("#",1)[0]
    except:
        pass
    return ""

def anchors(page_html, base_url):
    out = set()
    for m in re.finditer(r'href\s*=\s*["\']([^"\'#]+)', page_html, re.I):
        u = abs_url(m.group(1), base_url)
        if u:
            out.add(u)
    return out

def meta_content(page_html, prop):
    pats = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(prop)}["\']'
    ]
    for p in pats:
        m = re.search(p, page_html, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

def parse_jsonld(page_html):
    items = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page_html, re.I|re.S):
        raw = html.unescape(m.group(1)).strip()
        try:
            j = json.loads(raw)
            if isinstance(j, list):
                items.extend(j)
            else:
                items.append(j)
        except:
            pass
    return items

def duration_to_text(v):
    if not isinstance(v, str):
        return ""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v)
    if not m:
        return v
    h, mi, s = [int(x or 0) for x in m.groups()]
    parts=[]
    if h:
        parts.append(f"{h}h")
    if mi:
        parts.append(f"{mi}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts)

def movie_like(url, page_html, jsonlds):
    path = urlparse(url).path.lower()
    for j in jsonlds:
        if isinstance(j, dict):
            t = str(j.get("@type","")).lower()
            if any(x in t for x in ["movie","tvseries","tvseason","episode"]):
                return True
    if "/api/movie-extras/" in page_html or "movie_slug" in page_html:
        return True
    if path in ("/","/phimhay","/phim-le","/phim-bo","/hoat-hinh","/phim-chieu-rap","/tv-shows"):
        return False
    if any(x in path for x in ["/dieu-khoan", "/chinh-sach", "/lien-he", "/gioi-thieu"]):
        return False
    return False

def parse_movie(url, page_html):
    jsonlds = parse_jsonld(page_html)
    picked = None
    for j in jsonlds:
        if isinstance(j, dict):
            t = str(j.get("@type","")).lower()
            if any(x in t for x in ["movie","tvseries","tvseason"]):
                picked = j
                break

    title = meta_content(page_html, "og:title")
    poster = meta_content(page_html, "og:image")
    description = meta_content(page_html, "og:description") or meta_content(page_html, "description")
    canonical = ""
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', page_html, re.I)
    if m:
        canonical = abs_url(m.group(1), url)

    item = {
        "url": canonical or url,
        "slug": urlparse(canonical or url).path.strip("/").split("/")[-1],
        "title": clean(title),
        "originalTitle": "",
        "poster": poster,
        "backdrop": meta_content(page_html, "og:image"),
        "description": clean(description),
        "year": None,
        "duration": "",
        "durationRaw": "",
        "genres": [],
        "actors": [],
        "director": [],
        "quality": "",
        "type": "movie",
        "source": "rophims.team"
    }

    if picked:
        item["title"] = clean(picked.get("name") or item["title"])
        item["description"] = clean(picked.get("description") or item["description"])
        image = picked.get("image")
        if isinstance(image, dict):
            image = image.get("url")
        if isinstance(image, list) and image:
            image = image[0]
        if image:
            item["poster"] = str(image)
        dur = picked.get("duration")
        if dur:
            item["durationRaw"] = str(dur)
            item["duration"] = duration_to_text(str(dur))
        d = picked.get("datePublished") or ""
        y = re.search(r"\b(19|20)\d{2}\b", str(d))
        if y:
            item["year"] = int(y.group(0))
        g = picked.get("genre")
        if isinstance(g, str):
            item["genres"] = [clean(x) for x in g.split(",") if clean(x)]
        elif isinstance(g, list):
            item["genres"] = [clean(x) for x in g if clean(x)]
        typ = str(picked.get("@type","")).lower()
        if "tv" in typ:
            item["type"] = "series"

    visible = clean(page_html)
    if not item["year"]:
        y = re.search(r"\b(19|20)\d{2}\b", visible)
        if y:
            item["year"] = int(y.group(0))
    if not item["duration"]:
        m = re.search(r"\b(\d{1,2})h\s*(\d{1,2})m(?:/tập)?\b", visible, re.I)
        if m:
            item["duration"] = f"{m.group(1)}h {m.group(2)}m"
        else:
            m = re.search(r"\b(\d{1,3})\s*(?:phút|minutes?|min)\b", visible, re.I)
            if m:
                item["duration"] = f"{m.group(1)}m"

    for q in ["4K","FHD","HD","CAM"]:
        if re.search(rf"\b{q}\b", visible, re.I):
            item["quality"] = q
            break

    return item

def parse_sitemap_xml(url, body):
    urls, child_maps = set(), set()
    try:
        root = ET.fromstring(body)
        root_tag = root.tag.lower()
        is_index = root_tag.endswith("sitemapindex")
        for loc in root.iter():
            if loc.tag.lower().endswith("loc") and loc.text:
                u = loc.text.strip()
                if is_index:
                    child_maps.add(u)
                else:
                    urls.add(u)
    except:
        pass
    return urls, child_maps

def discover_sitemaps():
    seeds = [BASE+"/sitemap.xml", BASE+"/sitemap_index.xml", BASE+"/sitemap-index.xml"]
    found_urls=set()
    seen_maps=set()
    queue=list(seeds)
    while queue:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            final, ct, body = fetch(sm)
            if b"<urlset" not in body and b"<sitemapindex" not in body:
                continue
            urls, children = parse_sitemap_xml(final, body)
            found_urls.update(urls)
            for c in children:
                if c not in seen_maps:
                    queue.append(c)
            print(f"[sitemap] {final}: +{len(urls)} urls, +{len(children)} child maps", flush=True)
        except Exception as e:
            print(f"[sitemap] {sm}: {e}", flush=True)
    return found_urls, seen_maps

def main():
    started = datetime.now(timezone.utc).isoformat()
    print("RoPhim catalog crawler", flush=True)
    print("Output:", OUT, flush=True)

    sitemap_urls, sitemap_files = discover_sitemaps()
    discovered=set(sitemap_urls)
    categories=set()
    pages_scanned=0

    seed_pages=[BASE+"/"] + [BASE+x for x in CATEGORY_HINTS]
    for u in seed_pages:
        try:
            final, ct, body = fetch(u)
            h = text(body)
            pages_scanned += 1
            links = anchors(h, final)
            discovered.update(links)
            for x in links:
                path=urlparse(x).path
                if path.count("/") <= 2 and not re.search(r"\.(jpg|jpeg|png|webp|svg|css|js|ico)$", path, re.I):
                    categories.add(x)
            print(f"[seed] {final}: {len(links)} links", flush=True)
        except Exception as e:
            print(f"[seed] {u}: {e}", flush=True)

    candidates = sorted(discovered)
    movies=[]
    seen_movie_urls=set()
    errors=[]

    for i,u in enumerate(candidates,1):
        p=urlparse(u)
        if p.hostname not in ("rophims.team","www.rophims.team","rophim.loan","www.rophim.loan"):
            continue
        if re.search(r"\.(jpg|jpeg|png|webp|svg|css|js|ico|woff2?|ttf|zip|pdf)$", p.path, re.I):
            continue
        try:
            final, ct, body = fetch(u)
            if "text/html" not in ct and b"<html" not in body[:500].lower():
                continue
            h=text(body)
            pages_scanned += 1
            jlds=parse_jsonld(h)
            if movie_like(final,h,jlds):
                item=parse_movie(final,h)
                if item["url"] not in seen_movie_urls:
                    seen_movie_urls.add(item["url"])
                    movies.append(item)
                    print(f"[movie {len(movies)}] {item['title'] or item['slug']}", flush=True)
            if p.path.count("/") <= 2:
                for x in anchors(h, final):
                    discovered.add(x)
        except Exception as e:
            errors.append({"url":u,"error":str(e)})
        if i % 25 == 0:
            print(f"[progress] {i}/{len(candidates)} candidates, movies={len(movies)}", flush=True)
        time.sleep(0.08)

    data={
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "startedAt": started,
        "baseUrl": BASE,
        "sitemaps": sorted(sitemap_files),
        "categories": sorted(categories),
        "allDiscoveredUrls": sorted(discovered),
        "stats": {
            "sitemapUrlCount": len(sitemap_urls),
            "discoveredUrlCount": len(discovered),
            "pagesScanned": pages_scanned,
            "movieCount": len(movies),
            "errorCount": len(errors)
        },
        "movies": movies,
        "errors": errors
    }
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    print("\nDONE", flush=True)
    print(json.dumps(data["stats"],ensure_ascii=False), flush=True)
    print("Saved:", OUT, flush=True)

if __name__=="__main__":
    main()
