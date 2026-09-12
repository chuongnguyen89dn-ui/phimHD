import os, sys, json, time, re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from cloakbrowser import launch

CATALOG = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_catalog.json")
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_resolved.json")
LOG = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_batch_resolver.log")

PAGE_TIMEOUT = 90000
WAIT_AFTER_OPEN_MS = 1800
WAIT_FOR_MEDIA_SEC = 12
CHECKPOINT_EVERY = 1

sys.stdout.reconfigure(line_buffering=True, write_through=True)

MEDIA_EXTS = (".m3u8", ".mpd", ".mp4", ".m4s", ".ts")
MASTER_HINTS = ("master.m3u8", "index.m3u8")

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

def is_media(u):
    u = (u or "").lower()
    return any(x in u for x in MEDIA_EXTS)

def is_playlist(u):
    u = (u or "").lower()
    return ".m3u8" in u or ".mpd" in u

def checkpoint(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)

def load_catalog():
    with open(CATALOG, "r", encoding="utf-8") as f:
        return json.load(f)

def load_existing():
    if not os.path.exists(OUT):
        return {"generatedAt": None, "source": CATALOG, "items": {}, "stats": {}}
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            x = json.load(f)
            if isinstance(x, dict) and isinstance(x.get("items"), dict):
                return x
    except:
        pass
    return {"generatedAt": None, "source": CATALOG, "items": {}, "stats": {}}

def normalize_movie_list(cat):
    movies = cat.get("movies") or []
    out = []
    seen = set()
    for m in movies:
        if not isinstance(m, dict):
            continue
        u = str(m.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(m)
    return out

def try_click_play(page):
    selectors = [
        'button[aria-label*="play" i]',
        'button:has-text("Play")',
        'button:has-text("Xem")',
        '[class*="play" i]',
        '[id*="play" i]',
        'video'
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                if sel == "video":
                    page.evaluate("""() => {
                        const v = document.querySelector('video');
                        if (v) { v.muted = true; v.play().catch(()=>{}); }
                    }""")
                else:
                    loc.click(timeout=1800)
                return sel
        except:
            pass
    try:
        ok = page.evaluate("""() => {
            const els = [...document.querySelectorAll('button,a,div')];
            const e = els.find(x => /play|xem phim|xem ngay/i.test((x.innerText||'').trim()));
            if (e) { e.click(); return true; }
            return false;
        }""")
        if ok:
            return "text-fallback"
    except:
        pass
    return ""

def collect_variants(page):
    variants = []
    try:
        entries = page.evaluate("""() => performance.getEntriesByType('resource').map(x => x.name)""") or []
        for u in entries:
            if ".m3u8" in str(u).lower():
                variants.append(str(u))
    except:
        pass
    return list(dict.fromkeys(variants))

def choose_master(urls):
    urls = list(dict.fromkeys(urls))
    masters = [u for u in urls if any(h in u.lower() for h in MASTER_HINTS)]
    if masters:
        masters.sort(key=len)
        return masters[0]
    pls = [u for u in urls if ".m3u8" in u.lower()]
    return pls[0] if pls else ""

def resolve_one(context, movie, idx, total):
    url = str(movie.get("url") or "")
    title = str(movie.get("title") or movie.get("slug") or url)
    slug = str(movie.get("slug") or urlparse(url).path.rstrip("/").split("/")[-1])

    page = context.new_page()
    requests = []
    good = []
    statuses = []
    api = []

    def on_request(req):
        try:
            u = req.url
            if is_media(u) or "/api/" in u.lower():
                requests.append({"method": req.method, "url": u})
        except:
            pass

    def on_response(res):
        try:
            u = res.url
            low = u.lower()
            if is_media(u):
                statuses.append({"status": res.status, "url": u})
                if res.status < 400 and u not in good:
                    good.append(u)
            elif "/api/" in low and res.status < 500:
                api.append({"status": res.status, "url": u})
        except:
            pass

    page.on("request", on_request)
    page.on("response", on_response)

    item = {
        "url": url,
        "slug": slug,
        "title": title,
        "type": movie.get("type") or "movie",
        "poster": movie.get("poster") or "",
        "duration": movie.get("duration") or "",
        "resolvedAt": datetime.now().isoformat(timespec="seconds"),
        "ok": False,
        "master": "",
        "playlists": [],
        "media": [],
        "api": [],
        "click": "",
        "error": ""
    }

    try:
        log(f"[{idx}/{total}] OPEN {title} | {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(WAIT_AFTER_OPEN_MS)
        item["click"] = try_click_play(page)

        deadline = time.time() + WAIT_FOR_MEDIA_SEC
        while time.time() < deadline:
            try:
                page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (v) { v.muted = true; if (v.paused) v.play().catch(()=>{}); }
                }""")
            except:
                pass
            if any(".m3u8" in u.lower() and s.get("status",999) < 400 for s in statuses for u in [s.get("url","")]):
                page.wait_for_timeout(1600)
                break
            page.wait_for_timeout(500)

        confirmed = [x["url"] for x in statuses if x.get("status",999) < 400]
        playlists = [u for u in confirmed if is_playlist(u)]
        media = [u for u in confirmed if is_media(u)]

        item["playlists"] = list(dict.fromkeys(playlists))
        item["media"] = list(dict.fromkeys(media))
        item["master"] = choose_master(item["playlists"])
        item["api"] = api[-80:]
        item["ok"] = bool(item["master"] or item["playlists"])

        if item["ok"]:
            log(f"  OK master={item['master'] or item['playlists'][0]}")
        else:
            log("  NO PLAYLIST")
    except Exception as e:
        item["error"] = repr(e)
        log(f"  ERROR {repr(e)}")
    finally:
        try:
            page.close()
        except:
            pass

    return item

def main():
    if not os.path.exists(CATALOG):
        print(f"Không thấy {CATALOG}")
        print("Hãy để rophim_catalog_crawler.py chạy xong hoặc có file rophim_catalog.json trên Desktop.")
        return

    cat = load_catalog()
    movies = normalize_movie_list(cat)
    if not movies:
        print("rophim_catalog.json chưa có movies.")
        return

    data = load_existing()
    items = data["items"]

    log(f"START total={len(movies)} existing={len(items)}")

    browser = launch(headless=True, humanize=True)
    context = browser.new_context()

    try:
        for i, movie in enumerate(movies, 1):
            url = str(movie.get("url") or "")
            old = items.get(url)
            if isinstance(old, dict) and old.get("ok"):
                log(f"[{i}/{len(movies)}] SKIP OK {old.get('title') or url}")
                continue

            item = resolve_one(context, movie, i, len(movies))
            items[url] = item

            ok_count = sum(1 for x in items.values() if isinstance(x, dict) and x.get("ok"))
            fail_count = sum(1 for x in items.values() if isinstance(x, dict) and not x.get("ok"))
            data["generatedAt"] = datetime.now().isoformat(timespec="seconds")
            data["stats"] = {
                "catalogTotal": len(movies),
                "processed": len(items),
                "ok": ok_count,
                "failed": fail_count
            }
            checkpoint(data)
            log(f"  CHECKPOINT processed={len(items)} ok={ok_count} failed={fail_count}")
    finally:
        try:
            browser.close()
        except:
            pass

    log("DONE")

if __name__ == "__main__":
    main()
