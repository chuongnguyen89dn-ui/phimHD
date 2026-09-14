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
const PREFETCH=['1080','720','360'];
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const mediaCache=new Map();
const ctxCache=new Map();
const prefetching=new Set();
const videoMap=new Map();
let catalogLoading=false,catalogLoadedAt=0;
videoMap.set(DEFAULT_ID,{id:DEFAULT_ID,title:'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu'});

function jh(){return{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','access-control-allow-methods':'GET,HEAD,OPTIONS','access-control-allow-headers':'*'};}
function send(res,code,body){res.writeHead(code,jh());res.end(JSON.stringify(body));}
function signal(ms){return AbortSignal.timeout(ms);}
function decrypt(enc){const raw=Buffer.from(String(enc).replace(/\s/g,''),'base64');const iv=raw.subarray(0,16);const d=crypto.createDecipheriv('aes-128-cbc',KEY,iv);return JSON.parse(Buffer.concat([d.update(raw.subarray(16)),d.final()]).toString('utf8'));}
function metaFromVideo(v){return{id:`yt:${v.id}`,type:'movie',name:v.title||`YouTube ${v.id}`,poster:`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`,background:`https://i.ytimg.com/vi/${v.id}/maxresdefault.jpg`,description:v.description||'Khoai Lang Thang / Food & Travel',genres:['YouTube','Khoai Lang Thang','Travel'],releaseInfo:'YouTube'};}

async function scanTab(tab){try{const data=await youtubedl(`https://www.youtube.com/@${CHANNEL_HANDLE}/${tab}`,{dumpSingleJson:true,flatPlaylist:true,skipDownload:true,noWarnings:true,ignoreErrors:true});const entries=Array.isArray(data?.entries)?data.entries:[];for(const e of entries){if(!e?.id||!/^[A-Za-z0-9_-]{11}$/.test(e.id))continue;const old=videoMap.get(e.id)||{};videoMap.set(e.id,{...old,id:e.id,title:e.title||old.title||`YouTube ${e.id}`,description:e.description||old.description||'Khoai Lang Thang / Food & Travel'});}console.log('[CHANNEL-SCAN]',tab,entries.length);return entries.length;}catch(e){console.error('[CHANNEL-SCAN-FAIL]',tab,String(e));return 0;}}
async function refreshCatalog(force=false){if(catalogLoading)return;if(!force&&catalogLoadedAt&&Date.now()-catalogLoadedAt<6*60*60*1000)return;catalogLoading=true;try{await scanTab('videos');await scanTab('shorts');catalogLoadedAt=Date.now();console.log('[CHANNEL-CATALOG-READY]',videoMap.size);}finally{catalogLoading=false;}}

async function getCdn(){for(const ep of DISCOVERY){try{const r=await fetch(ep,{headers:{'User-Agent':UA,Accept:'application/json',Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'},signal:signal(8000)});const j=await r.json();if(r.ok&&j?.cdn)return j.cdn;}catch{}}throw new Error('No SaveTube CDN');}
async function getCtx(id){const cached=ctxCache.get(id);if(cached&&cached.expires>Date.now())return cached.ctx;const cdn=await getCdn();const base=`https://${cdn}`;const headers={'Content-Type':'application/json',Accept:'application/json','User-Agent':UA,Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'};const r=await fetch(`${base}/v2/info`,{method:'POST',headers,body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:signal(15000)});const j=await r.json();if(!r.ok||!j?.data)throw new Error(`info ${r.status}`);const info=decrypt(j.data);if(info?.title){const old=videoMap.get(id)||{id};videoMap.set(id,{...old,id,title:info.title});}const ctx={base,headers,info};ctxCache.set(id,{ctx,expires:Date.now()+15*60*1000});return ctx;}
async function resolveMedia(id,q){const key=`${id}:${q}`;const hit=mediaCache.get(key);if(hit&&hit.expires>Date.now()){console.log('[CACHE-HIT]',key);return hit.url;}const c=await getCtx(id);const tryQs=q==='360'?['360']:[q,'360'];for(const qq of tryQs){try{const r=await fetch(`${c.base}/download`,{method:'POST',headers:c.headers,body:JSON.stringify({id,downloadType:'video',quality:qq,key:c.info.key}),signal:signal(20000)});const t=await r.text();let j=null;try{j=JSON.parse(t)}catch{}const url=j?.data?.downloadUrl||j?.data?.url||j?.downloadUrl;if(r.ok&&url){mediaCache.set(key,{url,expires:Date.now()+20*60*1000});console.log('[PLAY-RESOLVED]',id,q,'=>',qq);return url;}}catch(e){console.log('[PLAY-MISS]',id,qq,String(e));}}throw new Error('No media URL');}
function prefetch(id){if(prefetching.has(id))return;prefetching.add(id);Promise.allSettled(PREFETCH.map(q=>resolveMedia(id,q))).then(()=>console.log('[PREFETCH-DONE]',id)).finally(()=>setTimeout(()=>prefetching.delete(id),60000));}

const manifest={id:ADDON_ID,version:'8.2.0',name:'Ivy ❤️ Khoai Lang Thang',description:'Full Khoai Lang Thang channel with SaveTube prefetch/cache.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Khoai Lang Thang • Full Channel'}],idPrefixes:['yt:']};

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,jh());return res.end();}const u=new URL(req.url,'http://localhost');let path;try{path=decodeURIComponent(u.pathname)}catch{path=u.pathname}console.log(req.method,path);
if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,videos:videoMap.size,loading:catalogLoading,mediaCache:mediaCache.size,ctxCache:ctxCache.size});
if(path==='/manifest.json')return send(res,200,manifest);
if(path===`/catalog/movie/${CATALOG_ID}.json`){void refreshCatalog(false);return send(res,200,{metas:[...videoMap.values()].map(metaFromVideo)});}
if(path==='/diag.json')return send(res,200,{videos:videoMap.size,catalogLoading,catalogLoadedAt,mediaCache:[...mediaCache.keys()],ctxCache:[...ctxCache.keys()],prefetching:[...prefetching]});
const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm){const v=videoMap.get(mm[1]);if(v)prefetch(mm[1]);return send(res,200,{meta:v?metaFromVideo(v):null});}
const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const id=sm[1];prefetch(id);const streams=QUALITIES.map(q=>({name:`Ivy YouTube • ${q==='2160'?'4K ':''}${q}p`,title:`Khoai Lang Thang • ${q}p`,url:`${ORIGIN}/play/${id}/${q}.mp4`}));console.log('[STREAM-INSTANT]',id,streams.length);return send(res,200,{streams});}
const pm=path.match(/^\/play\/([A-Za-z0-9_-]{11})\/(2160|1440|1080|720|480|360)\.mp4$/);if(pm){const [,id,q]=pm;const target=await resolveMedia(id,q);res.writeHead(302,{Location:target,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}
return send(res,404,{error:'not found',path});}catch(e){console.error('[request-error]',String(e));return send(res,502,{error:String(e)})}});
server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy Khoai Lang Thang prefetch addon listening',PORT);void refreshCatalog(true);});
