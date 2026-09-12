import os, sys, json, time, multiprocessing as mp
from datetime import datetime
from urllib.parse import urlparse
from cloakbrowser import launch

CATALOG = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_catalog.json")
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_parallel_resolved.json")
LOG = os.path.join(os.path.expanduser("~"), "Desktop", "rophim_parallel_resolver.log")

WORKERS = int(os.environ.get("ROPHIM_WORKERS", "6"))
PAGE_TIMEOUT = 90000
WAIT_AFTER_OPEN_MS = 1200
WAIT_FOR_MEDIA_SEC = 8

MEDIA_EXTS = (".m3u8", ".mpd", ".mp4", ".m4s", ".ts")
PLAYLIST_EXTS = (".m3u8", ".mpd")

def now():
    return datetime.now().isoformat(timespec="seconds")

def is_media(u):
    x=(u or "").lower()
    return any(e in x for e in MEDIA_EXTS)

def is_playlist(u):
    x=(u or "").lower()
    return any(e in x for e in PLAYLIST_EXTS)

def choose_master(urls):
    urls=list(dict.fromkeys(urls))
    masters=[u for u in urls if "master.m3u8" in u.lower()]
    if masters:
        masters.sort(key=len)
        return masters[0]
    roots=[u for u in urls if u.lower().endswith("/index.m3u8")]
    if roots:
        roots.sort(key=len)
        return roots[0]
    return urls[0] if urls else ""

def try_click_play(page):
    selectors=[
        'button[aria-label*="play" i]',
        'button:has-text("Play")',
        'button:has-text("Xem")',
        '[class*="play" i]',
        '[id*="play" i]',
        'video'
    ]
    for sel in selectors:
        try:
            loc=page.locator(sel).first
            if loc.count()>0:
                if sel=="video":
                    page.evaluate("""() => {
                        const v=document.querySelector('video');
                        if(v){v.muted=true;v.play().catch(()=>{});}
                    }""")
                else:
                    loc.click(timeout=1500)
                return sel
        except:
            pass
    try:
        ok=page.evaluate("""() => {
          const es=[...document.querySelectorAll('button,a,[role=button],div')];
          const e=es.find(x=>/play|xem phim|xem ngay/i.test((x.innerText||'').trim()));
          if(e){e.click();return true} return false;
        }""")
        if ok:
            return "text-fallback"
    except:
        pass
    return ""

def resolve_item(page, movie):
    url=str(movie.get("url") or "")
    title=str(movie.get("title") or movie.get("slug") or url)
    slug=str(movie.get("slug") or urlparse(url).path.rstrip("/").split("/")[-1])

    statuses=[]
    api=[]
    good=[]

    def on_response(res):
        try:
            u=res.url
            if is_media(u):
                statuses.append({"status":res.status,"url":u})
                if res.status < 400 and u not in good:
                    good.append(u)
            elif "/api/" in u.lower() and res.status < 500:
                api.append({"status":res.status,"url":u})
        except:
            pass

    page.on("response", on_response)

    item={
        "url":url,
        "slug":slug,
        "title":title,
        "type":movie.get("type") or "movie",
        "poster":movie.get("poster") or "",
        "duration":movie.get("duration") or "",
        "resolvedAt":now(),
        "ok":False,
        "master":"",
        "playlists":[],
        "media":[],
        "api":[],
        "click":"",
        "error":""
    }

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(WAIT_AFTER_OPEN_MS)
        item["click"]=try_click_play(page)

        deadline=time.time()+WAIT_FOR_MEDIA_SEC
        while time.time()<deadline:
            try:
                page.evaluate("""() => {
                  const v=document.querySelector('video');
                  if(v){v.muted=true;if(v.paused)v.play().catch(()=>{});}
                }""")
            except:
                pass
            if any(".m3u8" in x["url"].lower() and x["status"] < 400 for x in statuses):
                page.wait_for_timeout(1200)
                break
            page.wait_for_timeout(350)

        confirmed=[x["url"] for x in statuses if x["status"] < 400]
        item["playlists"]=list(dict.fromkeys([u for u in confirmed if is_playlist(u)]))
        item["media"]=list(dict.fromkeys([u for u in confirmed if is_media(u)]))
        item["master"]=choose_master(item["playlists"])
        item["api"]=api[-60:]
        item["ok"]=bool(item["master"] or item["playlists"])
    except Exception as e:
        item["error"]=repr(e)
    return item

def worker_main(worker_id, task_q, result_q):
    browser=None
    try:
        browser=launch(headless=True, humanize=True)
        ctx=browser.new_context()
        page=ctx.new_page()

        while True:
            task=task_q.get()
            if task is None:
                break
            idx,total,movie=task
            started=time.time()
            try:
                item=resolve_item(page,movie)
                item["worker"]=worker_id
                item["elapsedSec"]=round(time.time()-started,2)
                result_q.put(("result",idx,total,item))
            except Exception as e:
                result_q.put(("result",idx,total,{
                    "url":str(movie.get("url") or ""),
                    "title":str(movie.get("title") or ""),
                    "ok":False,
                    "error":repr(e),
                    "worker":worker_id,
                    "elapsedSec":round(time.time()-started,2),
                    "resolvedAt":now()
                }))
            finally:
                try:
                    page.close()
                except:
                    pass
                page=ctx.new_page()
    except Exception as e:
        result_q.put(("worker_error",worker_id,repr(e)))
    finally:
        try:
            if browser:
                browser.close()
        except:
            pass
        result_q.put(("worker_done",worker_id))

def load_catalog():
    with open(CATALOG,"r",encoding="utf-8") as f:
        return json.load(f)

def load_existing():
    if not os.path.exists(OUT):
        return {"generatedAt":None,"workers":WORKERS,"items":{},"stats":{}}
    try:
        with open(OUT,"r",encoding="utf-8") as f:
            d=json.load(f)
            if isinstance(d,dict) and isinstance(d.get("items"),dict):
                return d
    except:
        pass
    return {"generatedAt":None,"workers":WORKERS,"items":{},"stats":{}}

def save_checkpoint(data):
    tmp=OUT+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,OUT)

def append_log(line):
    s=f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
    print(s,flush=True)
    with open(LOG,"a",encoding="utf-8") as f:
        f.write(s+"\n")
        f.flush()

def main():
    if not os.path.exists(CATALOG):
        print("Không thấy:",CATALOG)
        return

    cat=load_catalog()
    movies=[x for x in (cat.get("movies") or []) if isinstance(x,dict) and x.get("url")]
    if not movies:
        print("Catalog chưa có phim.")
        return

    data=load_existing()
    items=data["items"]

    pending=[]
    for i,m in enumerate(movies,1):
        u=str(m.get("url"))
        old=items.get(u)
        if isinstance(old,dict) and old.get("ok"):
            continue
        pending.append((i,len(movies),m))

    append_log(f"START total={len(movies)} pending={len(pending)} workers={WORKERS}")

    ctx=mp.get_context("spawn")
    task_q=ctx.Queue(maxsize=max(WORKERS*3,12))
    result_q=ctx.Queue()

    workers=[]
    for wid in range(1,WORKERS+1):
        p=ctx.Process(target=worker_main,args=(wid,task_q,result_q),daemon=True)
        p.start()
        workers.append(p)

    for task in pending:
        task_q.put(task)
    for _ in workers:
        task_q.put(None)

    done_workers=0
    processed=0

    while done_workers < len(workers):
        msg=result_q.get()
        kind=msg[0]

        if kind=="result":
            _,idx,total,item=msg
            u=item.get("url","")
            items[u]=item
            processed+=1

            ok_count=sum(1 for x in items.values() if isinstance(x,dict) and x.get("ok"))
            fail_count=sum(1 for x in items.values() if isinstance(x,dict) and not x.get("ok"))

            data["generatedAt"]=now()
            data["workers"]=WORKERS
            data["stats"]={
                "catalogTotal":len(movies),
                "resolvedStored":len(items),
                "processedThisRun":processed,
                "ok":ok_count,
                "failed":fail_count,
                "pendingAtStart":len(pending)
            }
            save_checkpoint(data)

            state="OK" if item.get("ok") else "FAIL"
            append_log(
                f"[{idx}/{total}] W{item.get('worker')} {state} "
                f"{item.get('elapsedSec')}s | {item.get('title')} | "
                f"{item.get('master') or item.get('error','')}"
            )

        elif kind=="worker_error":
            append_log(f"WORKER ERROR W{msg[1]} {msg[2]}")

        elif kind=="worker_done":
            done_workers += 1
            append_log(f"WORKER DONE W{msg[1]} ({done_workers}/{len(workers)})")

    for p in workers:
        p.join(timeout=5)

    save_checkpoint(data)
    append_log("DONE")

if __name__=="__main__":
    mp.freeze_support()
    main()
