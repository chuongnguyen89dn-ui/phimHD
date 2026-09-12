import os, re, json, time, html
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

BASE = "https://rophim.loan"
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_catalog_clean.json")
LOG = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_catalog_clean.log")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36"

ROOT_SITEMAPS = [
    BASE + "/sitemap.xml",
    BASE + "/sitemap_index.xml",
    BASE + "/sitemap-index.xml",
]

SEED_PAGES = [
    BASE + "/",
    BASE + "/phimhay",
    BASE + "/phim-le",
    BASE + "/phim-bo",
    BASE + "/hoat-hinh",
    BASE + "/phim-chieu-rap",
    BASE + "/tv-shows",
]

MOVIE_PATH_RE = re.compile(r"^/phim/[^/?#]+/?$", re.I)

def stamp():
    return datetime.now(timezone.utc).isoformat()

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

def fetch(url, timeout=25):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": BASE + "/",
    })
    with urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read()

def abs_url(u, base=BASE):
    try:
        v = urljoin(base, html.unescape(u)).split("#", 1)[0]
        p = urlparse(v)
        if p.scheme in ("http", "https") and p.hostname in ("rophim.loan", "www.rophim.loan"):
            return v
    except:
        pass
    return ""

def is_movie_url(u):
    try:
        p = urlparse(u)
        if p.hostname not in ("rophim.loan", "www.rophim.loan"):
            return False
        return bool(MOVIE_PATH_RE.match(p.path))
    except:
        return False

def anchors(page_html, base_url):
    out = set()
    for m in re.finditer(r'href\s*=\s*["\']([^"\'#]+)', page_html, re.I):
        u = abs_url(m.group(1), base_url)
        if u and is_movie_url(u):
            out.add(u)
    return out

def xml_locs(body):
    try:
        root = ET.fromstring(body)
        return root.tag.lower(), [
            x.text.strip()
            for x in root.iter()
            if x.tag.lower().endswith("loc") and x.text
        ]
    except:
        return "", []

def meta_content(page_html, prop):
    pats = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(prop)}["\']',
    ]
    for p in pats:
        m = re.search(p, page_html, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return re.sub(r"\s+", " ", s).strip()

def parse_jsonld(page_html):
    items = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        re.I | re.S,
    ):
        try:
            j = json.loads(html.unescape(m.group(1)).strip())
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
    parts = []
    if h:
        parts.append(f"{h}h")
    if mi:
        parts.append(f"{mi}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts)

def parse_movie(url, page_html):
    jsonlds = parse_jsonld(page_html)
    picked = None
    for j in jsonlds:
        if isinstance(j, dict):
            typ = str(j.get("@type", "")).lower()
            if any(x in typ for x in ("movie", "tvseries", "tvseason")):
                picked = j
                break

    canonical = ""
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
        page_html,
        re.I,
    )
    if m:
        c = abs_url(m.group(1), url)
        if is_movie_url(c):
            canonical = c

    final = canonical or url
    visible = clean(page_html)
    item = {
        "url": final,
        "slug": urlparse(final).path.rstrip("/").split("/")[-1],
        "title": clean(meta_content(page_html, "og:title")),
        "originalTitle": "",
        "poster": meta_content(page_html, "og:image"),
        "backdrop": meta_content(page_html, "og:image"),
        "description": clean(meta_content(page_html, "og:description") or meta_content(page_html, "description")),
        "year": None,
        "duration": "",
        "durationRaw": "",
        "genres": [],
        "actors": [],
        "director": [],
        "quality": "",
        "type": "movie",
        "source": "rophim.loan",
    }

    if picked:
        item["title"] = clean(picked.get("name") or item["title"])
        item["description"] = clean(picked.get("description") or item["description"])
        image = picked.get("image")
        if isinstance(image, dict): image = image.get("url")
        if isinstance(image, list) and image: image = image[0]
        if image: item["poster"] = str(image)
        dur = picked.get("duration")
        if dur:
            item["durationRaw"] = str(dur)
            item["duration"] = duration_to_text(str(dur))
        d = str(picked.get("datePublished") or "")
        y = re.search(r"\b(19|20)\d{2}\b", d)
        if y: item["year"] = int(y.group(0))
        g = picked.get("genre")
        if isinstance(g, str): item["genres"] = [clean(x) for x in g.split(",") if clean(x)]
        elif isinstance(g, list): item["genres"] = [clean(x) for x in g if clean(x)]
        if "tv" in str(picked.get("@type", "")).lower(): item["type"] = "series"

    if not item["year"]:
        y = re.search(r"\b(19|20)\d{2}\b", visible)
        if y: item["year"] = int(y.group(0))
    if not item["duration"]:
        m = re.search(r"\b(\d{1,2})h\s*(\d{1,2})m(?:/tập)?\b", visible, re.I)
        if m:
            item["duration"] = f"{m.group(1)}h {m.group(2)}m"
        else:
            m = re.search(r"\b(\d{1,3})\s*(?:phút|minutes?|min)\b", visible, re.I)
            if m: item["duration"] = f"{m.group(1)}m"
    for q in ("4K", "FHD", "HD", "CAM"):
        if re.search(rf"\b{q}\b", visible, re.I):
            item["quality"] = q
            break
    return item

def save(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)

def discover_initial_urls():
    movie_maps = set()
    movie_urls = set()
    for root_url in ROOT_SITEMAPS:
        try:
            final, ct, body = fetch(root_url)
            _, locs = xml_locs(body)
            for u in locs:
                if "movies-sitemap" in u.lower():
                    movie_maps.add(u)
            if movie_maps:
                log(f"ROOT {final}: {len(movie_maps)} movie sitemaps")
                break
        except Exception as e:
            log(f"ROOT_ERR {root_url}: {e}")
    for sm in sorted(movie_maps):
        try:
            final, ct, body = fetch(sm)
            if b"<urlset" not in body:
                continue
            _, locs = xml_locs(body)
            added = 0
            for u in locs:
                if is_movie_url(u):
                    movie_urls.add(u)
                    added += 1
            log(f"SITEMAP {urlparse(final).path}: +{added}")
        except Exception as e:
            log(f"SITEMAP_ERR {sm}: {e}")
    for seed in SEED_PAGES:
        try:
            final, ct, body = fetch(seed)
            h = body.decode("utf-8", "replace")
            links = anchors(h, final)
            before = len(movie_urls)
            movie_urls.update(links)
            log(f"SEED {urlparse(final).path or '/'}: +{len(movie_urls)-before}")
        except Exception as e:
            log(f"SEED_ERR {seed}: {e}")
    return movie_urls

def main():
    urls = sorted(discover_initial_urls())
    total = len(urls)
    data = {
        "generatedAt": stamp(),
        "crawlComplete": False,
        "baseUrl": BASE,
        "stats": {"totalQueued": total, "processed": 0, "movieCount": 0, "failed": 0, "remaining": total, "duplicates": 0},
        "movies": [],
        "errors": [],
    }
    save(data)
    log(f"START UNIQUE_MOVIE_URLS={total}")
    seen_canonical = set()
    for idx, url in enumerate(urls, 1):
        try:
            final, ct, body = fetch(url)
            h = body.decode("utf-8", "replace")
            item = parse_movie(final, h)
            if not is_movie_url(item["url"]):
                raise ValueError("canonical_not_movie")
            if item["url"] in seen_canonical:
                data["stats"]["duplicates"] += 1
            else:
                seen_canonical.add(item["url"])
                data["movies"].append(item)
                data["stats"]["movieCount"] = len(data["movies"])
            log(f"{idx}/{total} MOVIE={data['stats']['movieCount']} DUP={data['stats']['duplicates']} LEFT={total-idx} | {item['title'] or item['slug']}")
        except Exception as e:
            data["errors"].append({"url": url, "error": str(e)})
            data["stats"]["failed"] = len(data["errors"])
            log(f"{idx}/{total} FAIL LEFT={total-idx} | {url} | {e}")
        data["stats"]["processed"] = idx
        data["stats"]["remaining"] = total - idx
        data["generatedAt"] = stamp()
        save(data)
    data["crawlComplete"] = True
    data["generatedAt"] = stamp()
    save(data)
    log(f"DONE processed={data['stats']['processed']} movies={data['stats']['movieCount']} duplicates={data['stats']['duplicates']} failed={data['stats']['failed']}")

if __name__ == "__main__":
    main()
