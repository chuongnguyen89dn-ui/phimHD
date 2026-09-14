import http from 'node:http';
import crypto from 'node:crypto';

const PORT=Number(process.env.PORT||10000);
const DEFAULT_ID='AjSxpi8E9WE';
const ADDON_ID='community.ivy.youtube.savetube.fast';
const CATALOG_ID='ivy-youtube-savetube-fast';
const TITLE='Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER=`https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;
const KEY=Buffer.from('C5D58EF67A7584E4A29F6C35BBC4EB12','hex');
const DISCOVERY=['https://media.savetube.vip/api/random-cdn','https://media.savetube.me/api/random-cdn'];
const HIGH=['2160','1440','1080','720','480'];
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const cache=new Map();
const resolving=new Set();

cache.set(DEFAULT_ID,[{quality:'360',url:'https://cdn403.savetube.vip/media/AjSxpi8E9WE/hanh-trinh-xuyen-dao-nui-lua-iceland-p5-du-lich-chau-au-360-ytshorts.savetube.me.mp4',probe:{ok:true,status:206,contentType:'video/mp4',bytes:65536},source:'last-verified'}]);

function headers(){return{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','access-control-allow-methods':'GET,OPTIONS','access-control-allow-headers':'*'};}
function send(res,code,body){res.writeHead(code,headers());res.end(JSON.stringify(body));}
function signal(ms){return AbortSignal.timeout(ms);}
function decrypt(enc){const raw=Buffer.from(String(enc).replace(/\s/g,''),'base64');const iv=raw.subarray(0,16);const d=crypto.createDecipheriv('aes-128-cbc',KEY,iv);return JSON.parse(Buffer.concat([d.update(raw.subarray(16)),d.final()]).toString('utf8'));}
async function readLimited(r,limit=16384){const rd=r.body?.getReader();if(!rd)return new Uint8Array();let total=0;const parts=[];try{while(total<limit){const x=await rd.read();if(x.done)break;parts.push(x.value);total+=x.value.byteLength;}}finally{try{await rd.cancel();}catch{}}const out=new Uint8Array(Math.min(total,limit));let o=0;for(const p of parts){const s=p.subarray(0,Math.min(p.byteLength,out.length-o));out.set(s,o);o+=s.byteLength;if(o>=out.length)break;}return out;}
async function probe(url){try{const r=await fetch(url,{headers:{Range:'bytes=0-16383','User-Agent':UA,Accept:'*/*'},redirect:'follow',signal:signal(10000)});const b=await readLimited(r);return{ok:(r.status===200||r.status===206)&&b.byteLength>0,status:r.status,contentType:r.headers.get('content-type')||'',bytes:b.byteLength};}catch(e){return{ok:false,error:String(e)}}}
async function cdn(){for(const ep of DISCOVERY){try{const r=await fetch(ep,{headers:{'User-Agent':UA,Accept:'application/json',Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'},signal:signal(8000)});const j=await r.json();if(r.ok&&j?.cdn)return j.cdn;}catch{}}throw new Error('No SaveTube CDN');}
async function ctx(id){const c=await cdn();const base=`https://${c}`;const h={'Content-Type':'application/json',Accept:'application/json','User-Agent':UA,Origin:'https://yt.savetube.me',Referer:'https://yt.savetube.me/'};const r=await fetch(`${base}/v2/info`,{method:'POST',headers:h,body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:signal(15000)});const j=await r.json();if(!r.ok||!j?.data)throw new Error(`info ${r.status}`);return{base,headers:h,info:decrypt(j.data)};}
async function quality(c,id,q,timeout=15000){try{const r=await fetch(`${c.base}/download`,{method:'POST',headers:c.headers,body:JSON.stringify({id,downloadType:'video',quality:q,key:c.info.key}),signal:signal(timeout)});const t=await r.text();let j=null;try{j=JSON.parse(t)}catch{}const url=j?.data?.downloadUrl||j?.data?.url||j?.downloadUrl;if(!r.ok||!url)return null;const p=await probe(url);return p.ok?{quality:q,url,probe:p,source:'SaveTube'}:null;}catch{return null;}}
function sortStreams(a){return [...a].sort((x,y)=>Number(y.quality)-Number(x.quality));}
async function refresh(id){if(resolving.has(id))return;resolving.add(id);try{const c=await ctx(id);const existing=cache.get(id)||[];const q360=await quality(c,id,'360',18000);let merged=q360?[...existing.filter(x=>x.quality!=='360'),q360]:existing;cache.set(id,sortStreams(merged));console.log('[FAST-360]',JSON.stringify(cache.get(id).map(x=>x.quality)));
for(const q of HIGH){const x=await quality(c,id,q,12000);if(x){merged=[...cache.get(id).filter(s=>s.quality!==q),x];cache.set(id,sortStreams(merged));console.log('[HD-FOUND]',q,x.probe.status,x.probe.contentType);}else console.log('[HD-MISS]',q);}}
catch(e){console.error('[REFRESH-FAIL]',String(e));}finally{resolving.delete(id);}}
function toStreams(items){return sortStreams(items).map(x=>({name:`Ivy YouTube • ${x.quality==='2160'?'4K ':''}${x.quality}p`,title:`SaveTube • ${x.probe?.contentType||'video/mp4'}`,url:x.url}));}

const manifest={id:ADDON_ID,version:'7.0.0',name:'Ivy ❤️ YouTube Fast HD',description:'Returns cached playable stream immediately; discovers HD/4K in background.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Ivy ❤️ YouTube Fast HD'}],idPrefixes:['yt:']};
const meta={id:`yt:${DEFAULT_ID}`,type:'movie',name:TITLE,poster:POSTER,background:`https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,description:'Fast YouTube playback with background HD/4K discovery.',genres:['YouTube','Travel'],releaseInfo:'YouTube'};

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,headers());return res.end();}const u=new URL(req.url,'http://localhost');let path;try{path=decodeURIComponent(u.pathname)}catch{path=u.pathname}console.log(req.method,path);
if(path==='/')return send(res,200,{service:manifest.name,version:manifest.version,manifest:'/manifest.json',cache:Object.fromEntries([...cache].map(([k,v])=>[k,v.map(x=>x.quality)]))});
if(path==='/manifest.json')return send(res,200,manifest);
if(path===`/catalog/movie/${CATALOG_ID}.json`)return send(res,200,{metas:[meta]});
if(path==='/diag.json')return send(res,200,{cached:cache.get(DEFAULT_ID)||[],resolving:[...resolving]});
const mm=path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(mm)return send(res,200,{meta:mm[1]===DEFAULT_ID?meta:null});
const sm=path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);if(sm){const id=sm[1];const ready=cache.get(id)||[];if(ready.length){void refresh(id);console.log('[STREAM-FAST]',id,ready.map(x=>x.quality).join(','));return send(res,200,{streams:toStreams(ready)});}const c=await ctx(id);const x=await quality(c,id,'360',18000);if(x){cache.set(id,[x]);void refresh(id);return send(res,200,{streams:toStreams([x])});}return send(res,200,{streams:[]});}
return send(res,404,{error:'not found',path});}catch(e){console.error('[request-error]',String(e));return send(res,500,{error:String(e)})}});

server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy YouTube Fast HD listening',PORT);void refresh(DEFAULT_ID);});
