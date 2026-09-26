import asyncio,json
from playwright.async_api import async_playwright

URLS=[
 "https://embed13.streamc.xyz/embed.php?hash=7d16a34b60bd28dee122fa48cf872573",
 "https://embed14.streamc.xyz/embed.php?hash=b898a6c0d2a800adf5065595f1ae9ea3",
]

async def one(browser,url):
    ctx=await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146 Safari/537.36",
                                  extra_http_headers={"Referer":"https://rophims.team/"})
    page=await ctx.new_page()
    events=[]
    async def on_response(resp):
        req=resp.request
        u=resp.url
        rt=req.resource_type
        ct=(resp.headers.get("content-type") or "")
        interesting=rt in ("xhr","fetch","media") or any(k in u.lower() for k in ("m3u8","bootstrap","grant","playlist","stream","embed.php"))
        if not interesting:return
        row={"url":u,"status":resp.status,"resourceType":rt,"contentType":ct,"method":req.method,
             "postData":req.post_data}
        if ("json" in ct or rt in ("xhr","fetch")) and resp.status<500:
            try:
                txt=await resp.text()
                row["body"]=txt[:12000]
            except Exception as e: row["bodyError"]=repr(e)
        events.append(row)
    page.on("response",on_response)
    try:
        await page.goto(url,wait_until="domcontentloaded",timeout=45000)
        await page.mouse.click(400,300)
        await page.wait_for_timeout(12000)
    except Exception as e:
        events.append({"pageError":repr(e)})
    await ctx.close()
    # de-duplicate preserving useful body variants
    return {"input":url,"events":events}

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--autoplay-policy=no-user-gesture-required"])
        out=[]
        for u in URLS: out.append(await one(browser,u))
        await browser.close()
    json.dump({"results":out},open("streamc_browser_capture.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
    for r in out:
        print("INPUT",r["input"])
        for e in r["events"]:
            if isinstance(e,dict) and e.get("url"):
                print(e.get("status"),e.get("resourceType"),e.get("method"),e.get("url"),"BODY",str(e.get("body",""))[:300].replace("\n"," "))

asyncio.run(main())
