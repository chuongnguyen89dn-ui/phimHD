import http from 'node:http';
import {spawn} from 'node:child_process';
import ffmpegPath from 'ffmpeg-static';

const PORT=Number(process.env.PORT||10000);
const PROVIDER='https://youtubeone.vercel.app';
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const cache=new Map(),inFlight=new Map();

function send(res,code,obj){res.writeHead(code,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*'});res.end(JSON.stringify(obj));}
async function getInfo(id){const hit=cache.get(id);if(hit&&hit.expires>Date.now())return hit.info;if(inFlight.has(id))return inFlight.get(id);const p=(async()=>{const r=await fetch(`${PROVIDER}/api/info`,{method:'POST',headers:{'content-type':'application/json','user-agent':UA},body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:AbortSignal.timeout(30000)});const j=await r.json().catch(()=>null);if(!r.ok||!Array.isArray(j?.formats))throw new Error(`provider info ${r.status} ${j?.error||''}`.trim());cache.set(id,{info:j,expires:Date.now()+10*60*1000});console.log('[YO-INFO]',id,'node',j.node,'formats',j.formats.length);return j;})().finally(()=>inFlight.delete(id));inFlight.set(id,p);return p;}
function streamProxy(info,f,filename){const p=new URL(`${PROVIDER}/api/stream`);p.searchParams.set('url',f.url);p.searchParams.set('filename',filename);if(info.proxied){p.searchParams.set('proxied','1');p.searchParams.set('node',String(info.node));}return p.toString();}
function codecRank(f,q){const m=String(f.mimeType||'').toLowerCase();let r=0;if(m.includes('avc1'))r+=q<=1080?100:20;if(m.includes('vp9')||m.includes('vp09'))r+=q>1080?100:40;if(m.includes('av01'))r+=q>1080?80:10;if(m.startsWith('video/mp4'))r+=20;return r+(f.bitrate||0)/1e8;}
function pickExact(info,q){const fs=info.formats||[];const muxed=fs.filter(f=>f.type==='muxed'&&f.url&&f.height===q).sort((a,b)=>(b.bitrate||0)-(a.bitrate||0))[0];if(muxed)return{kind:'direct',format:muxed,height:q};const videos=fs.filter(f=>f.type==='video'&&f.url&&f.height===q).sort((a,b)=>codecRank(b,q)-codecRank(a,q));const audios=fs.filter(f=>f.type==='audio'&&f.url).sort((a,b)=>{const A=String(a.mimeType||'').includes('mp4')?1:0,B=String(b.mimeType||'').includes('mp4')?1:0;return(B-A)||((b.bitrate||0)-(a.bitrate||0));});if(videos[0]&&audios[0])return{kind:'mux',video:videos[0],audio:audios[0],height:q};return null;}
function availability(info){const heights=[...new Set((info.formats||[]).filter(f=>f.url&&f.height&&['video','muxed'].includes(f.type)).map(f=>Number(f.height)))].sort((a,b)=>b-a);const supported=heights.filter(h=>[2160,1440,1080,720,480,360].includes(h));return{title:info.title,proxied:info.proxied,node:info.node,heights,supported,maxHeight:supported[0]||0,formats:info.formats.length};}

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,{'access-control-allow-origin':'*','access-control-allow-methods':'GET,HEAD,OPTIONS'});return res.end();}const path=new URL(req.url,'http://localhost').pathname;if(path==='/')return send(res,200,{service:'Ivy exact-resolution YouTube backend',version:'0.3.1'});
let m=path.match(/^\/availability\/([A-Za-z0-9_-]{11})\.json$/);if(m){const info=await getInfo(m[1]);return send(res,200,{ok:true,id:m[1],...availability(info)});}
m=path.match(/^\/stream\/([A-Za-z0-9_-]{11})\/(2160|1440|1080|720|480|360)\.mp4$/);if(m){const [,id,qs]=m,q=Number(qs),info=await getInfo(id),picked=pickExact(info,q);if(!picked){console.log('[EXACT-NO-FORMAT]',id,q);return send(res,404,{error:`${q}p not available`,id,q,...availability(info)});}console.log('[EXACT-PICK]',id,q,picked.kind,picked.kind==='mux'?picked.video.mimeType:picked.format.mimeType);
if(picked.kind==='direct'){const url=streamProxy(info,picked.format,`${id}-${q}.mp4`);res.writeHead(302,{Location:url,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*','X-Ivy-Height':String(q)});return res.end();}
const vurl=streamProxy(info,picked.video,`${id}-${q}-video`),aurl=streamProxy(info,picked.audio,`${id}-${q}-audio`);
res.writeHead(200,{'Content-Type':'video/mp4','Cache-Control':'no-store','Access-Control-Allow-Origin':'*','Accept-Ranges':'none','Transfer-Encoding':'chunked','X-Ivy-Height':String(q)});
const args=['-hide_banner','-loglevel','warning','-i',vurl,'-i',aurl,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','160k','-movflags','frag_keyframe+empty_moov+default_base_moof','-f','mp4','pipe:1'];
const ff=spawn(ffmpegPath,args,{stdio:['ignore','pipe','pipe']});let bytes=0,started=false;
const watchdog=setTimeout(()=>{if(!ff.killed){console.log('[FFMPEG-TIMEOUT]',id,q,'bytes',bytes);ff.kill('SIGKILL');}},90000);
ff.stdout.on('data',c=>{bytes+=c.length;if(!started){started=true;console.log('[FIRST-BYTES]',id,q,c.length);} });
ff.stdout.pipe(res);
ff.stderr.on('data',d=>console.log('[FFMPEG]',id,q,String(d).trim()));
ff.on('error',e=>console.log('[FFMPEG-SPAWN-ERROR]',id,q,String(e)));
ff.on('close',(code,signal)=>{clearTimeout(watchdog);console.log('[EXACT-CLOSE]',id,q,'code',code,'signal',signal,'bytes',bytes);if(!res.writableEnded)res.end();});
res.on('close',()=>console.log('[CLIENT-CLOSE]',id,q,'bytes',bytes,'ended',res.writableEnded));
return;}
return send(res,404,{error:'not found',path});}catch(e){console.error('[ERROR]',String(e));return send(res,502,{error:String(e)})}});
server.listen(PORT,'0.0.0.0',()=>console.log('Ivy exact-resolution backend listening',PORT));