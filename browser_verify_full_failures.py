import os, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

REPORT=os.environ.get("IVY_FULL_AUDIT_REPORT","full_playback_audit.json")
OUT=os.environ.get("IVY_BROWSER_FULL_OUT","browser_full_verify_part.json")
SHARD=int(os.environ.get("IVY_BROWSER_SHARD_INDEX","0"))
SHARDS=max(1,int(os.environ.get("IVY_BROWSER_SHARD_TOTAL","1")))
WORKERS=max(1,int(os.environ.get("IVY_BROWSER_WORKERS","2")))
PAGE_TIMEOUT=max(15000,int(os.environ.get("IVY_BROWSER_PAGE_TIMEOUT","45000")))
WAIT_MS=max(3000,int(os.environ.get("IVY_BROWSER_WAIT_MS","8500")))

MEDIA_EXTS=(".m3u8",".mpd",".mp4",".m4s",".ts")

def is_media(u):
    s=(u or "").lower()
    return any(x in s for x in MEDIA_EXTS)

def to_watch_url(url, episode=None):
    u=str(url or "")
    u=u.replace("/phim/","/xem-phim/",1)
    if episode:
        u=u.split("?",1)[0]+f"?tap=tap-{int(episode)}&sv=0"
    return u

def choose_episode(item):
    fails=item.get("failedEpisodes") or []
    for x in fails:
        try:
            ep=int(x.get("episode"))
            if ep>0:return ep, x.get("season"), x.get("videoId")
        except: pass
    return None,None,None

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
                    page.evaluate("""() => {const v=document.querySelector('video'); if(v){v.muted=true;v.play().catch(()=>{});}}""")
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

def verify(item):
    ep,season,video_id=choose_episode(item)
    target=to_watch_url(item.get("url"),ep)
    out={
      "kind":item.get("kind"),"title":item.get("title"),"url":item.get("url"),
      "target":target,"season":season,"episode":ep,"videoId":video_id,
      "webPlayable":False,"playlists":[],"media":[],"click":"","httpStatus":None,
      "error":"","addonFailureReason":item.get("reason") or ("failed_episode" if ep else "empty_stream")
    }
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
                if out["httpStatus"] is None and res.request.resource_type=="document":
                    out["httpStatus"]=res.status
                u=res.url
                if is_media(u): seen.append((res.status,u))
            except: pass
        page.on("response",on_response)
        page.goto(target,wait_until="domcontentloaded",timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(1200)
        out["click"]=click_play(page)
        deadline=time.time()+WAIT_MS/1000
        while time.time()<deadline:
            try:
                page.evaluate("""() => {const v=document.querySelector('video');if(v){v.muted=true;if(v.paused)v.play().catch(()=>{});}}""")
            except: pass
            if any(s<400 and (".m3u8" in u.lower() or ".mpd" in u.lower()) for s,u in seen):
                page.wait_for_timeout(1000); break
            page.wait_for_timeout(350)
        good=[u for s,u in seen if s<400]
        out["media"]=list(dict.fromkeys(good))
        out["playlists"]=list(dict.fromkeys([u for u in good if ".m3u8" in u.lower() or ".mpd" in u.lower()]))
        out["webPlayable"]=bool(out["playlists"])
        browser.close()
    except Exception as e:
        out["error"]=repr(e)
    return out

def main():
    with open(REPORT,encoding="utf-8") as f:d=json.load(f)
    allc=d.get("browserCandidates") or [x for x in (d.get("results") or []) if not x.get("ok")]
    candidates=[x for i,x in enumerate(allc) if i%SHARDS==SHARD]
    print(f"FULL_BROWSER shard={SHARD}/{SHARDS} totalCandidates={len(allc)} subset={len(candidates)} workers={WORKERS}",flush=True)
    results=[];ok=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(verify,x):x for x in candidates}
        done=0
        for fut in as_completed(futs):
            done+=1
            try:r=fut.result()
            except Exception as e:
                x=futs[fut]
                r={"kind":x.get("kind"),"title":x.get("title"),"url":x.get("url"),"webPlayable":False,"error":repr(e)}
            results.append(r)
            if r.get("webPlayable"):ok+=1
            print(f"[{done}/{len(candidates)}] {'WEB_OK' if r.get('webPlayable') else 'NO_MEDIA'} {r.get('title','')} ep={r.get('episode')}",flush=True)
    out={
      "generatedAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
      "shardIndex":SHARD,"shardTotal":SHARDS,"checked":len(results),
      "webPlayableAddonFailed":ok,"unconfirmed":len(results)-ok,
      "results":results
    }
    with open(OUT,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print("FULL_BROWSER_DONE",json.dumps({k:out[k] for k in ("checked","webPlayableAddonFailed","unconfirmed")}),flush=True)

if __name__=="__main__":
    main()
