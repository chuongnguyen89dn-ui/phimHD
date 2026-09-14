import http from 'node:http';
import crypto from 'node:crypto';
import youtubedl from 'youtube-dl-exec';

const PORT=Number(process.env.PORT||10000);
const ORIGIN='https://ivy-youtubejs-direct-test.onrender.com';
const MUX='https://ivy-ytmux-backend.onrender.com';
const DEFAULT_ID='AjSxpi8E9WE';
const CHANNEL_HANDLE='KhoaiLangThang';
const ADDON_ID='community.ivy.youtube.khoailangthang';
const CATALOG_ID='ivy-khoai-lang-thang';
const KEY=Buffer.from('C5D58EF67A7584E4A29F6C35BBC4EB12','hex');
const DISCOVERY=['https://media.savetube.vip/api/random-cdn','https://media.savetube.me/api/random-cdn'];
const QUALITIES=[2160,1440,1080,720,480,360];
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const videoMap=new Map(),qualityCache=new Map(),mediaCache=new Map();
let catalogLoading=false,catalogLoadedAt=0;
videoMap.set(DEFAULT_ID,{id:DEFAULT_ID,title:'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu'});

function send(res,code,body){res.writeHead(code,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*'});res.end(JSON.stringify(body));}
function signal(ms){return AbortSignal.timeout(ms);}
function decrypt(enc){const raw=Buffer.from(String(enc).replace(/\s/g,''),'base64'),iv=raw.subarray(0,16),d=crypto.createDecipheriv('aes-128-cbc',KEY,iv);return JSON.parse(Buffer.concat([d.update(raw.subarray(16)),d.final()]).toString('utf8'));}
function qLabel(q){return q===2160?'4K • 2160p':q===1440?'2K • 1440p':`${q}p`;}
function metaFromVideo(v){return{id:`yt:${v.id}`,type:'movie',name:v.title||`YouTube ${v.id}`,poster:`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`,background:`https://i.ytimg.com/vi/${v.id}/maxresdefault.jpg`,description:v.description||'Khoai Lang Thang / Food & Travel',genres:['YouTube','Khoai Lang Thang','Travel'],releaseInfo:'YouTube'};}
async function scanTab(tab){try{const d=await youtubedl(`https://www.youtube.com/@${CHANNEL_HANDLE}/${tab}`,{dumpSingleJson:true,flatPlaylist:true,skipDownload:true,noWarnings:true,ignoreErrors:true});for(const e of Array.isArray(d?.entries)?d.entries:[]){if(e?.id&&/^[A-Za-z0-9_-]{11}$/.test(e.id))videoMap.set(e.id,{id:e.id,title:e.title||`YouTube ${e.id}`,description:e.description});}console.log('[CHANNEL-SCAN]',tab);}catch(e){console.log('[CHANNEL-SCAN-FAIL]',tab,String(e));}}
async function refreshCatalog(){if(catalogLoading||Date.now()-catalogLoadedAt<21600000)return;catalogLoading=true;try{await scanTab('videos');await scanTab('shorts');catalogLoadedAt=Date.now();console.log('[CHANNEL-CATALOG-READY]',videoMap.size);}finally{catalogLoading=false;}}
async function getQualities(id){const h=qualityCache.get(id);if(h&&h.exp>Date.now())return h.q;try{const r=await fetch(`${MUX}/availability/${id}.json`,{signal:signal(9000)}),j=await r.json();const q=(j.supported||[]).map(Number).filter(x=>QUALITIES.includes(x)).sort((a,b)=>b-a);if(q.length){qualityCache.set(id,{q,exp:Date.now()+600000});console.log('[FAST-QUALITIES]',id,q.join(','));return q;}}catch(e){console.log('[FAST-QUALITIES-FAIL]',id,String(e));}return [1080,720,360];}
async function getCtx(id){for(const ep of DISCOVERY){try{const rr=await fetch(ep,{headers:{'User-Agent':UA},signal:signal(3000)}),jj=await rr.json();if(!rr.ok||!jj?.cdn)continue;const base=`https://${jj.cdn}`,headers={'Content-Type':'application/json','User-Agent':UA},r=await fetch(`${base}/v2/info`,{method:'POST',headers,body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:signal(6000)}),j=await r.json();if(r.ok&&j?.data)return{base,headers,info:decrypt(j.data),cdn:jj.cdn};}catch{}}throw new Error('SaveTube unavailable');}
async function resolveSaveTube(id,q){const key=`${id}:${q}`,h=mediaCache.get(key);if(h&&h.exp>Date.now())return h.url;const c=await getCtx(id),r=await fetch(`${c.base}/download`,{method:'POST',headers:c.headers,body:JSON.stringify({id,downloadType:'video',quality:String(q),key:c.info.key}),signal:signal(6500)}),j=await r.json().catch(()=>null),url=j?.data?.downloadUrl||j?.data?.url||j?.downloadUrl;if(!r.ok||!url)throw new Error(`SaveTube ${r.status}`);mediaCache.set(key,{url,exp:Date.now()+3600000});console.log('[SAVE-RESOLVED]',id,q,c.cdn);return url;}
async function play(id,q,res){try{const url=await resolveSaveTube(id,q);console.log('[PLAY-SAVETUBE]',id,q);res.writeHead(302,{Location:url,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}catch(e){console.log('[PLAY-MUX-FALLBACK]',id,q,String(e));res.writeHead(302,{Location:`${MUX}/stream/${id}/${q}.mp4`,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}}

const manifest={id:ADDON_ID,version:'9.0.0',name:'Ivy ❤️ Khoai Lang Thang',description:'Fast exact-quality multi-provider playback. Quality list comes from residential YouTube metadata; playback uses SaveTube first and residential mux fallback.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Khoai Lang Thang • Full Channel'}],idPrefixes:['yt:']};
const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,{'access-control-allow-origin':'*'});return res.end();}const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);console.log(req.method,path);if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,videos:videoMap.size});if(path==='/manifest.json')return send(res,200,manifest);if(path===`/catalog/movie/${CATALOG_ID}.json`){void refreshCatalog();return send(res,200,{metas:[...videoMap.values()].map(metaFromVideo)});}const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm)return send(res,200,{meta:metaFromVideo(videoMap.get(mm[1])||{id:mm[1]})});const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const id=sm[1],q=await getQualities(id),streams=q.map(n=>({name:`Ivy YouTube • ${qLabel(n)}`,title:`Exact ${n}p`,url:`${ORIGIN}/play/${id}/${n}.mp4`}));console.log('[STREAM-MULTI]',id,q.join(','));return send(res,200,{streams});}const pm=path.match(/^\/play\/([A-Za-z0-9_-]{11})\/(2160|1440|1080|720|480|360)\.mp4$/);if(pm)return play(pm[1],Number(pm[2]),res);return send(res,404,{error:'not found'});}catch(e){console.log('[ERROR]',String(e));return send(res,502,{error:String(e)})}});
server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy v9 multi-provider listening',PORT);void refreshCatalog();});