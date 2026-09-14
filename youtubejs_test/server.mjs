import http from 'node:http';
import youtubedl from 'youtube-dl-exec';

const PORT=Number(process.env.PORT||10000);
const MUX='https://ivy-ytmux-backend.onrender.com';
const DEFAULT_ID='AjSxpi8E9WE';
const CHANNEL_HANDLE='KhoaiLangThang';
const ADDON_ID='community.ivy.youtube.khoailangthang';
const CATALOG_ID='ivy-khoai-lang-thang';
const videoMap=new Map();
const qualityCache=new Map();
let catalogLoading=false,catalogLoadedAt=0;
videoMap.set(DEFAULT_ID,{id:DEFAULT_ID,title:'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu'});

function jh(){return{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','access-control-allow-methods':'GET,HEAD,OPTIONS','access-control-allow-headers':'*'};}
function send(res,code,body){res.writeHead(code,jh());res.end(JSON.stringify(body));}
function metaFromVideo(v){return{id:`yt:${v.id}`,type:'movie',name:v.title||`YouTube ${v.id}`,poster:`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`,background:`https://i.ytimg.com/vi/${v.id}/maxresdefault.jpg`,description:v.description||'Khoai Lang Thang / Food & Travel',genres:['YouTube','Khoai Lang Thang','Travel'],releaseInfo:'YouTube'};}
function qLabel(q){return q===2160?'4K • 2160p':q===1440?'2K • 1440p':`${q}p`;}

async function scanTab(tab){try{const data=await youtubedl(`https://www.youtube.com/@${CHANNEL_HANDLE}/${tab}`,{dumpSingleJson:true,flatPlaylist:true,skipDownload:true,noWarnings:true,ignoreErrors:true});const entries=Array.isArray(data?.entries)?data.entries:[];for(const e of entries){if(!e?.id||!/^[A-Za-z0-9_-]{11}$/.test(e.id))continue;const old=videoMap.get(e.id)||{};videoMap.set(e.id,{...old,id:e.id,title:e.title||old.title||`YouTube ${e.id}`,description:e.description||old.description||'Khoai Lang Thang / Food & Travel'});}console.log('[CHANNEL-SCAN]',tab,entries.length);}catch(e){console.error('[CHANNEL-SCAN-FAIL]',tab,String(e));}}
async function refreshCatalog(force=false){if(catalogLoading)return;if(!force&&catalogLoadedAt&&Date.now()-catalogLoadedAt<6*60*60*1000)return;catalogLoading=true;try{await scanTab('videos');await scanTab('shorts');catalogLoadedAt=Date.now();console.log('[CHANNEL-CATALOG-READY]',videoMap.size);}finally{catalogLoading=false;}}
async function getQualities(id){const hit=qualityCache.get(id);if(hit&&hit.expires>Date.now())return hit.data;const r=await fetch(`${MUX}/availability/${id}.json`,{signal:AbortSignal.timeout(15000)});const j=await r.json().catch(()=>null);if(!r.ok||!Array.isArray(j?.supported))throw new Error(`availability ${r.status}`);const supported=j.supported.filter(q=>[2160,1440,1080,720,480,360].includes(Number(q))).map(Number).sort((a,b)=>b-a);const data={supported,maxHeight:supported[0]||0,title:j.title};qualityCache.set(id,{data,expires:Date.now()+10*60*1000});console.log('[REAL-QUALITIES]',id,supported.join(','));return data;}

const manifest={id:ADDON_ID,version:'8.8.0',name:'Ivy ❤️ Khoai Lang Thang',description:'Per-video real resolution listing. Only qualities actually reported for each YouTube video are shown; every selection is exact, never downgraded silently.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Khoai Lang Thang • Full Channel'}],idPrefixes:['yt:']};

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,jh());return res.end();}const u=new URL(req.url,'http://localhost');let path;try{path=decodeURIComponent(u.pathname)}catch{path=u.pathname}console.log(req.method,path);
if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,videos:videoMap.size,qualityCache:qualityCache.size});
if(path==='/manifest.json')return send(res,200,manifest);
if(path===`/catalog/movie/${CATALOG_ID}.json`){void refreshCatalog(false);return send(res,200,{metas:[...videoMap.values()].map(metaFromVideo)});}
const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm){const v=videoMap.get(mm[1]);return send(res,200,{meta:v?metaFromVideo(v):null});}
const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const id=sm[1];const q=await getQualities(id);const streams=q.supported.map(n=>({name:`Ivy YouTube • ${qLabel(n)}`,title:`Khoai Lang Thang • exact ${n}p`,url:`${MUX}/stream/${id}/${n}.mp4`}));console.log('[STREAM-EXACT]',id,q.supported.join(','));return send(res,200,{streams});}
return send(res,404,{error:'not found',path});}catch(e){console.error('[request-error]',String(e));return send(res,502,{error:String(e)})}});
server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy exact-quality addon listening',PORT);void refreshCatalog(true);});