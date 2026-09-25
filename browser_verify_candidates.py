import os, re, json, time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

REPORT=os.environ.get("IVY_TARGETED_REPORT","targeted_playback_report.json")
OUT=os.environ.get("IVY_BROWSER_REPORT","browser_playback_verification.json")
WORKERS=max(1,int(os.environ.get("IVY_BROWSER_WORKERS","4")))
PAGE_TIMEOUT=max(15000,int(os.environ.get("IVY_BROWSER_PAGE_TIMEOUT","45000")))
WAIT_MS=max(3000,int(os.environ.get("IVY_BROWSER_WAIT_MS","9000")))

MEDIA_EXTS=(".m3u8",".mpd",".mp4",".m4s",".ts")

def is_media(u):
    x=(u or "").lower()
    return any(ext in x for ext in MEDIA_EXTS)

def click_play(page):
    sels=[
        'button[aria-label*="play" i]',
        'button:has-text("Play")',
        'button:has-text("Xem")',
        '[class*="play" i]',
        '[id*="play" i]',
        'video'
    ]
    for sel in sels:
        try:
            loc=page.locator(sel).first
            if loc.count():
                if sel=="video":
                    page.evaluate("""() => { const v=document.querySelector('video'); if(v){v.muted=true;v.play().catch(()=>{});} }""")
                else:
                    loc.click(timeout=1500)
                return sel
        except: pass
    try:
        ok=page.evaluate("""() => {
          const es=[...document.querySelectorAll('button,a,[role=button],div')];
          const e=es.find(x=>/play|xem phim|xem ngay/i.test((x.innerText||'').trim()));
          if(e){e.click();return true} return false;
        }""")
        if ok:return "text-fallback"
    except: pass
    return ""

def to_watch_url(url, episode=None):
    u=str(url or "")
    u=u.replace("/phim/","/xem-phim/",1)
    if episode:
        u=u.split("?",1)[0]+f"?tap=tap-{int(episode)}&sv=0"
    return u

def one(item):
    title=item.get("title") or ""
    src=item.get("url") or ""
    kind=item.get("kind") or ""
    episode=None
    for issue in item.get("issues") or []:
        try:
            ep=issue.get("episode")
            if ep:
                episode=int(ep);break
        except: pass
    target=to_watch_url(src,episode)
    out={"kind":kind,"title":title,"url":src,"target":target,"episode":episode,"webPlayable":False,"playlists":[],"media":[],"statusCodes":[],"click":"","error":""}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
            ctx=browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
                viewport={"width":1365,"height":900},
                locale="vi-VN"
            )
            page=ctx.new_page()
            seen=[]
            def on_response(res):
                try:
                    u=res.url
                    if is_media(u):
                        seen.append((res.status,u))
                except: pass
            page.on("response",on_response)
            page.goto(target,wait_until="domcontentloaded",timeout=PAGE_TIMEOUT)
            page.wait_for_timeout(1500)
            out["click"]=click_play(page)
            deadline=time.time()+WAIT_MS/1000
            while time.time()<deadline:
                try:
                    page.evaluate("""() => { const v=document.querySelector('video'); if(v){v.muted=true;if(v.paused)v.play().catch(()=>{});} }""")
                except: pass
                if any(s<400 and (".m3u8" in u.lower() or ".mpd" in u.lower()) for s,u in seen):
                    page.wait_for_timeout(1200);break
                page.wait_for_timeout(400)
            good=[u for s,u in seen if s<400]
            out["media"]=list(dict.fromkeys(good))
            out["playlists"]=list(dict.fromkeys([u for u in good if ".m3u8" in u.lower() or ".mpd" in u.lower()]))
            out["statusCodes"]=[{"status":s,"url":u} for s,u in seen[-30:]]
            out["webPlayable"]=bool(out["playlists"])
            browser.close()
    except Exception as e:
        out["error"]=repr(e)
    return out

def worker(item):
    return one(item)

def main():
    with open(REPORT,encoding="utf-8") as f:r=json.load(f)
    candidates=r.get("browserCandidates") or []
    print(f"BROWSER_VERIFY candidates={len(candidates)} workers={WORKERS}",flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(worker,x):x for x in candidates}
        done=0
        for fut in as_completed(futs):
            done+=1
            try:res=fut.result()
            except Exception as e:
                x=futs[fut];res={"kind":x.get("kind"),"title":x.get("title"),"url":x.get("url"),"webPlayable":False,"error":repr(e)}
            results.append(res)
            print(f"[{done}/{len(candidates)}] {'WEB_OK' if res.get('webPlayable') else 'WEB_FAIL'} {res.get('title','')}",flush=True)
    web_ok=[x for x in results if x.get("webPlayable")]
    web_fail=[x for x in results if not x.get("webPlayable")]
    out={
      "generatedAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
      "candidates":len(candidates),
      "webPlayableAddonSuspect":len(web_ok),
      "webAlsoFailedOrUnconfirmed":len(web_fail),
      "resolverBugCandidates":web_ok,
      "webFailedOrUnconfirmed":web_fail
    }
    with open(OUT,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print("BROWSER_VERIFY_DONE",json.dumps({k:out[k] for k in ("candidates","webPlayableAddonSuspect","webAlsoFailedOrUnconfirmed")},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
