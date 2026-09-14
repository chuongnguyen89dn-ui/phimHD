import http from 'node:http';
import crypto from 'node:crypto';
import youtubedl from 'youtube-dl-exec';

const PORT=Number(process.env.PORT||10000);
const ORIGIN='https://ivy-youtubejs-direct-test.onrender.com';
const DEFAULT_ID='AjSxpi8E9WE';
const CHANNEL_HANDLE='KhoaiLangThang';
const CHANNEL_ID='UCZE88kYvCKUKjM-G0uc8Duw';
const ADDON_ID='community.ivy.youtube.khoailangthang';
const CATALOG_ID='ivy-khoai-lang-thang';
const KEY=Buffer.from('C5D58EF67A7584E4A29F6C35BBC4EB12','hex');
const DISCOVERY=['https://media.savetube.vip/api/random-cdn','https://media.savetube.me/api/random-cdn'];
const QUALITIES=['2160','1440','1080','720','480','360'];
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const mediaCache=new Map();
const ctxCache=new Map();
const inFlight=new Map();
const negativeCache=new Map();
const verified=new Map();
const highProbe=new Set();
const videoMap=new Map();
let catalogLoading=false,catalogLoadedAt=0;
videoMap.set(DEFAULT_ID,{id:DEFAULT_ID,title:'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu'});

function jh(){return{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','access-control-allow-methods':'GET,HEAD,OPTIONS','access-control-allow-headers':'*'};}
function send(res,code,body){res.writeHead(code,jh());res.end(JSON.stringify(body));}
function signal(ms){return AbortSignal.timeout(ms);}
function decrypt(enc){const raw=Buffer.from(String(enc).replace(/\s/g,''),'base64');const iv=raw.subarray(0,16);const d=crypto.createDecipheriv('aes-128-cbc',KEY,iv);return JSON.parse(Buffer.concat([d.update(raw.subarray(16)),d.final()]).toString('utf8'));}
function metaFromVideo(v){return{id:`yt:${v.id}`,type:'movie',name:v.title||`YouTube ${v.id}`,poster:`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`,background:`https://i.ytimg.com/vi/${v.id}/maxresdefault.jpg`,description:v.description||'Khoai Lang Thang / Food & Travel',genres:['YouTube','Khoai Lang Thang','Travel'],releaseInfo:'YouTube'};}
function markVerified(id,q){if(!verified.has(id))verified.set(id,new Set());verified.get(id).add(q);}

async function scanTab(tab){try{const data=await youtubedl(`https://www.youtube.com/@${CHANNEL_HANDLE}/${tab}`,{dumpSingleJson:true,flatPlaylist:true,skipDownload:true,noWarnings:true,ignoreErrors:true});const entries=Array.isArray(data?.entries)?data.entries:[];for(const e of entries){if(!e?.id||!/^[A-Za-z0-9_-]{11}$/.test(e.id))continue;const old=videoMap.get(e.id)||{};videoMap.set(e.id,{...old,id:e.id,title:e.title||old.title||`YouTube ${e.id}`,description:e.description||old.description||'Khoai Lang Thang / Food & Travel'});}console.log('[CHANNEL-SCAN]',tab,entries.length);return entries.length;}catch(e){console.error('[CHANNEL-SCAN-FAIL]',tab,String(e));return 0;}}
async function refreshCatalog(force=false){if(catalogLoading)return;if(!force&&catalogLoadedAt&&Date.now()-catalogLoadedAt<6*60*60*1000)return;catalogLoading=true;try{await scanTab('videos');await scanTab('shorts');catalogLoadedAt=Date.now();console.log('[CHANNEL-CATALOG-READY]',videoMap.size);}finally{catalogLoading=false;}}

async function discoverCdns(max=3){const seen=new Set();for(let round=0;round<4&&seen.size<max;round++){for(const ep of DISCOVERY){try{const r=await fetch(ep,{headers:{'User-Agent':UA,Accept:'application/json',Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'},signal:signal(5000)});const j=await r.json();if(r.ok&&j?.cdn)seen.add(j.cdn);}catch{}}}return [...seen].slice(0,max);}
async function getCtxForCdn(id,cdn){const ck=`${id}@${cdn}`;const hit=ctxCache.get(ck);if(hit&&hit.expires>Date.now())return hit.ctx;const base=`https://${cdn}`;const headers={'Content-Type':'application/json',Accept:'application/json','User-Agent':UA,Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'};const r=await fetch(`${base}/v2/info`,{method:'POST',headers,body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:signal(10000)});const j=await r.json();if(!r.ok||!j?.data)throw new Error(`info ${r.status}`);const info=decrypt(j.data);if(info?.title){const old=videoMap.get(id)||{id};videoMap.set(id,{...old,id,title:info.title});}const ctx={base,headers,info,cdn};ctxCache.set(ck,{ctx,expires:Date.now()+20*60*1000});return ctx;}
async function resolveOnCdn(id,q,cdn,timeoutMs){const c=await getCtxForCdn(id,cdn);const r=await fetch(`${c.base}/download`,{method:'POST',headers:c.headers,body:JSON.stringify({id,downloadType:'video',quality:q,key:c.info.key}),signal:signal(timeoutMs)});const t=await r.text();let j=null;try{j=JSON.parse(t)}catch{}const url=j?.data?.downloadUrl||j?.data?.url||j?.downloadUrl;if(r.ok&&url)return url;throw new Error(`download ${r.status}`);}

async function doResolve(id,q,{maxCdns=2,timeoutMs=12000}={}){const cdns=await discoverCdns(maxCdns);if(!cdns.length)throw new Error('No SaveTube CDN');let last=null;for(const cdn of cdns){try{const url=await resolveOnCdn(id,q,cdn,timeoutMs);markVerified(id,q);mediaCache.set(`${id}:${q}`,{url,provider:`savetube:${cdn}`,expires:Date.now()+2*60*60*1000});console.log('[PLAY-RESOLVED]',id,q,cdn);return url;}catch(e){last=e;ctxCache.delete(`${id}@${cdn}`);console.log('[CDN-MISS]',id,q,cdn,String(e));}}throw last||new Error(`No exact ${q}p media URL`);}
async function resolveMedia(id,q,opts){const key=`${id}:${q}`;const hit=mediaCache.get(key);if(hit&&hit.expires>Date.now()){console.log('[CACHE-HIT]',key,hit.provider);return hit.url;}const neg=negativeCache.get(key);if(neg&&neg>Date.now())throw new Error(`Recent ${q}p failure`);if(inFlight.has(key))return inFlight.get(key);const p=doResolve(id,q,opts).catch(e=>{negativeCache.set(key,Date.now()+30000);throw e;}).finally(()=>inFlight.delete(key));inFlight.set(key,p);return p;}
async function resolveAuto(id){for(const q of ['1080','720','480','360']){try{return{url:await resolveMedia(id,q,{maxCdns:2,timeoutMs:9000}),q};}catch(e){console.log('[AUTO-MISS]',id,q,String(e));}}throw new Error('No AUTO media URL');}
function probeHigh(id){if(highProbe.has(id))return;highProbe.add(id);(async()=>{try{await resolveMedia(id,'2160',{maxCdns:2,timeoutMs:12000});console.log('[HIGH-PROBE-4K]',id,'ok');}catch{try{await resolveMedia(id,'1440',{maxCdns:2,timeoutMs:10000});console.log('[HIGH-PROBE-2K]',id,'ok');}catch{}}})().finally(()=>setTimeout(()=>highProbe.delete(id),5*60*1000));}

const manifest={id:ADDON_ID,version:'8.5.0',name:'Ivy ❤️ Khoai Lang Thang',description:'Optimized SaveTube resolver with multi-CDN retry, single-flight cache and verified quality exposure.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Khoai Lang Thang • Full Channel'}],idPrefixes:['yt:']};

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,jh());return res.end();}const u=new URL(req.url,'http://localhost');let path;try{path=decodeURIComponent(u.pathname)}catch{path=u.pathname}console.log(req.method,path);
if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,videos:videoMap.size,loading:catalogLoading,mediaCache:mediaCache.size,inFlight:inFlight.size});
if(path==='/manifest.json')return send(res,200,manifest);
if(path===`/catalog/movie/${CATALOG_ID}.json`){void refreshCatalog(false);return send(res,200,{metas:[...videoMap.values()].map(metaFromVideo)});}
if(path==='/diag.json')return send(res,200,{videos:videoMap.size,catalogLoading,catalogLoadedAt,mediaCache:[...mediaCache.entries()].map(([k,v])=>({key:k,provider:v.provider})),verified:[...verified.entries()].map(([id,s])=>({id,qualities:[...s]})),inFlight:[...inFlight.keys()]});
const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm){const id=mm[1],v=videoMap.get(id);if(v)void probeHigh(id);return send(res,200,{meta:v?metaFromVideo(v):null});}
const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const id=sm[1];const known=[...(verified.get(id)||new Set())].sort((a,b)=>Number(b)-Number(a));const streams=[{name:'Ivy YouTube • AUTO',title:'Khoai Lang Thang • best stable',url:`${ORIGIN}/play/${id}/auto.mp4`},...known.map(q=>({name:`Ivy YouTube • ${q==='2160'?'4K ':q==='1440'?'2K ':''}${q}p ✓`,title:`Khoai Lang Thang • verified ${q}p`,url:`${ORIGIN}/play/${id}/${q}.mp4`}))];console.log('[STREAM-VERIFIED]',id,known);return send(res,200,{streams});}
const am=path.match(/^\/play\/([A-Za-z0-9_-]{11})\/auto\.mp4$/);if(am){const r=await resolveAuto(am[1]);console.log('[AUTO-RESOLVED]',am[1],r.q);res.writeHead(302,{Location:r.url,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}
const pm=path.match(/^\/play\/([A-Za-z0-9_-]{11})\/(2160|1440|1080|720|480|360)\.mp4$/);if(pm){const [,id,q]=pm;const target=await resolveMedia(id,q,{maxCdns:3,timeoutMs:Number(q)>=1440?15000:12000});res.writeHead(302,{Location:target,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}
return send(res,404,{error:'not found',path});}catch(e){console.error('[request-error]',String(e));return send(res,502,{error:String(e)})}});
server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy Khoai Lang Thang optimized resolver listening',PORT);void refreshCatalog(true);});
