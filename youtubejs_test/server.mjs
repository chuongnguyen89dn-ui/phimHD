import http from 'node:http';
import crypto from 'node:crypto';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.savetube.multiq';
const CATALOG_ID = 'ivy-youtube-savetube-multiq';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;
const KEY = Buffer.from('C5D58EF67A7584E4A29F6C35BBC4EB12', 'hex');
const DISCOVERY = ['https://media.savetube.vip/api/random-cdn','https://media.savetube.me/api/random-cdn'];
const QUALITY_ORDER = ['2160','1440','1080','720','480','360'];
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';

function headers(){return {'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','access-control-allow-methods':'GET,OPTIONS','access-control-allow-headers':'*'};}
function send(res,code,body){res.writeHead(code,headers());res.end(JSON.stringify(body));}
function signal(ms){return AbortSignal.timeout(ms);}
function decrypt(enc){const raw=Buffer.from(String(enc).replace(/\s/g,''),'base64');const iv=raw.subarray(0,16);const d=crypto.createDecipheriv('aes-128-cbc',KEY,iv);return JSON.parse(Buffer.concat([d.update(raw.subarray(16)),d.final()]).toString('utf8'));}

async function readLimited(r,limit=32768){const reader=r.body?.getReader();if(!reader)return new Uint8Array();const parts=[];let total=0;try{while(total<limit){const x=await reader.read();if(x.done)break;parts.push(x.value);total+=x.value.byteLength;}}finally{try{await reader.cancel();}catch{}}const out=new Uint8Array(Math.min(total,limit));let off=0;for(const p of parts){const s=p.subarray(0,Math.min(p.byteLength,out.length-off));out.set(s,off);off+=s.byteLength;if(off>=out.length)break;}return out;}

async function probe(url){try{const r=await fetch(url,{headers:{Range:'bytes=0-32767','User-Agent':UA,Accept:'*/*'},redirect:'follow',signal:signal(25000)});const b=await readLimited(r);return{ok:(r.status===200||r.status===206)&&b.byteLength>0,status:r.status,contentType:r.headers.get('content-type')||'',bytes:b.byteLength,finalUrl:r.url};}catch(e){return{ok:false,error:String(e)}}}

async function cdn(){for(const ep of DISCOVERY){try{const r=await fetch(ep,{headers:{'User-Agent':UA,Accept:'application/json',Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'},signal:signal(15000)});const j=await r.json();if(r.ok&&j?.cdn)return j.cdn;}catch{}}throw new Error('No SaveTube CDN');}

async function getContext(id){const c=await cdn();const base=`https://${c}`;const h={'Content-Type':'application/json',Accept:'application/json','User-Agent':UA,Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'};const r=await fetch(`${base}/v2/info`,{method:'POST',headers:h,body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:signal(30000)});const j=await r.json();if(!r.ok||!j?.data)throw new Error(`SaveTube info ${r.status}`);const info=decrypt(j.data);return{base,cdn:c,headers:h,info};}

async function requestQuality(ctx,id,q){try{const r=await fetch(`${ctx.base}/download`,{method:'POST',headers:ctx.headers,body:JSON.stringify({id,downloadType:'video',quality:q,key:ctx.info.key}),signal:signal(45000)});const text=await r.text();let j=null;try{j=JSON.parse(text)}catch{}const url=j?.data?.downloadUrl||j?.data?.url||j?.downloadUrl||null;if(!r.ok||!url)return{quality:q,ok:false,status:r.status,body:j||text.slice(0,160)};const p=await probe(url);return{quality:q,ok:p.ok,url,probe:p};}catch(e){return{quality:q,ok:false,error:String(e)}}}

async function resolveAll(id){const ctx=await getContext(id);const advertised=(ctx.info.video_formats||[]).map(v=>String(v.quality)).filter(Boolean);const results=[];for(const q of QUALITY_ORDER){const x=await requestQuality(ctx,id,q);results.push(x);console.log('[QUALITY]',JSON.stringify(x));}
const verified=results.filter(x=>x.ok);return{ok:verified.length>0,title:ctx.info.title,cdn:ctx.cdn,advertised,verified,results};}

const manifest={id:ADDON_ID,version:'6.0.0',name:'Ivy ❤️ YouTube Multi Quality',description:'SaveTube-backed YouTube playback with verified qualities up to 4K.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Ivy ❤️ YouTube Multi Quality'}],idPrefixes:['yt:']};
const meta={id:`yt:${DEFAULT_ID}`,type:'movie',name:TITLE,poster:POSTER,background:`https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,description:'Verified SaveTube multi-quality YouTube playback.',genres:['YouTube','Travel'],releaseInfo:'YouTube'};

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,headers());return res.end();}const u=new URL(req.url,'http://localhost');let path;try{path=decodeURIComponent(u.pathname)}catch{path=u.pathname}console.log(req.method,path);
if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,manifest:'/manifest.json'});
if(path==='/manifest.json')return send(res,200,manifest);
if(path===`/catalog/movie/${CATALOG_ID}.json`)return send(res,200,{metas:[meta]});
if(path==='/diag.json')return send(res,200,await resolveAll(DEFAULT_ID));
const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm)return send(res,200,{meta:mm[1]===DEFAULT_ID?meta:null});
const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const r=await resolveAll(sm[1]);console.log('[MULTIQ-STREAM]',JSON.stringify({title:r.title,advertised:r.advertised,verified:r.verified.map(x=>({q:x.quality,status:x.probe?.status,ct:x.probe?.contentType}))}));const streams=r.verified.map(x=>({name:`Ivy YouTube • ${x.quality==='2160'?'4K ':''}${x.quality}p`,title:`SaveTube • HTTP ${x.probe.status} • ${x.probe.contentType}`,url:x.url}));return send(res,200,{streams});}
return send(res,404,{error:'not found',path});}catch(e){console.error('[request-error]',String(e));return send(res,500,{error:String(e)})}});

server.listen(PORT,'0.0.0.0',async()=>{console.log('Ivy YouTube multi-quality demo listening',PORT);try{const r=await resolveAll(DEFAULT_ID);console.log('[MULTIQ-SELFTEST]',JSON.stringify({ok:r.ok,title:r.title,advertised:r.advertised,verified:r.verified.map(x=>({quality:x.quality,status:x.probe?.status,contentType:x.probe?.contentType,bytes:x.probe?.bytes,url:x.url}))}));}catch(e){console.error('[MULTIQ-SELFTEST-FAIL]',String(e));}});
