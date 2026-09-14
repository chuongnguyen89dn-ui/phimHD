import http from 'node:http';
import {spawn} from 'node:child_process';
import youtubedl from 'youtube-dl-exec';
import ffmpegPath from 'ffmpeg-static';

const PORT=Number(process.env.PORT||10000);
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';
const CLIENTS=['web_safari','tv_embedded','android_vr','ios','web'];
const infoCache=new Map();

function send(res,code,obj){res.writeHead(code,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*'});res.end(JSON.stringify(obj));}
function summarizeFormats(info){const fs=Array.isArray(info?.formats)?info.formats:[];const heights=[...new Set(fs.map(f=>f.height).filter(Boolean))].sort((a,b)=>b-a);return{count:fs.length,heights,maxHeight:heights[0]||0,muxed:fs.filter(f=>f.url&&f.vcodec&&f.vcodec!=='none'&&f.acodec&&f.acodec!=='none').length,videoOnly:fs.filter(f=>f.url&&f.vcodec&&f.vcodec!=='none'&&(!f.acodec||f.acodec==='none')).length,audioOnly:fs.filter(f=>f.url&&f.acodec&&f.acodec!=='none'&&(!f.vcodec||f.vcodec==='none')).length};}

async function extractWithClient(id,client){const url=`https://www.youtube.com/watch?v=${id}`;const started=Date.now();const info=await youtubedl(url,{dumpSingleJson:true,skipDownload:true,noWarnings:true,ignoreErrors:true,userAgent:UA,extractorArgs:`youtube:player_client=${client}`});return{client,ms:Date.now()-started,info};}
async function extractBest(id){const hit=infoCache.get(id);if(hit&&hit.expires>Date.now())return hit;const attempts=[];let winner=null;for(const client of CLIENTS){try{const r=await extractWithClient(id,client);const s=summarizeFormats(r.info);attempts.push({client,ms:r.ms,...s});if(s.count>0&&(!winner||s.maxHeight>winner.summary.maxHeight||s.count>winner.summary.count)){winner={client,info:r.info,summary:s};}if(s.maxHeight>=2160&&s.audioOnly>0)break;}catch(e){attempts.push({client,error:String(e)});}}if(!winner)throw Object.assign(new Error('No yt-dlp formats'),{attempts});const out={...winner,attempts,expires:Date.now()+10*60*1000};infoCache.set(id,out);return out;}

async function testYoutubeOne(id){const r=await fetch('https://youtubeone.vercel.app/api/info',{method:'POST',headers:{'content-type':'application/json','user-agent':UA},body:JSON.stringify({url:`https://www.youtube.com/watch?v=${id}`}),signal:AbortSignal.timeout(30000)});const j=await r.json().catch(()=>null);const fs=Array.isArray(j?.formats)?j.formats:[];const heights=[...new Set(fs.map(f=>f.height).filter(Boolean))].sort((a,b)=>b-a);console.log('[YOUTUBEONE]',JSON.stringify({status:r.status,ok:r.ok,title:j?.title,proxied:j?.proxied,node:j?.node,count:fs.length,heights,maxHeight:heights[0]||0,types:{muxed:fs.filter(f=>f.type==='muxed').length,video:fs.filter(f=>f.type==='video').length,audio:fs.filter(f=>f.type==='audio').length},error:j?.error||null}));}

function pickSources(info,q){const fs=(info.formats||[]).filter(f=>f.url);const target=Number(q);const exactMuxed=fs.filter(f=>f.height===target&&f.vcodec&&f.vcodec!=='none'&&f.acodec&&f.acodec!=='none').sort((a,b)=>(b.tbr||0)-(a.tbr||0))[0];if(exactMuxed)return{kind:'direct',url:exactMuxed.url,formatId:exactMuxed.format_id,height:exactMuxed.height,ext:exactMuxed.ext};
const videos=fs.filter(f=>f.height&&f.height<=target&&f.vcodec&&f.vcodec!=='none'&&(!f.acodec||f.acodec==='none')).sort((a,b)=>(b.height-a.height)||((b.tbr||0)-(a.tbr||0)));
const audios=fs.filter(f=>f.acodec&&f.acodec!=='none'&&(!f.vcodec||f.vcodec==='none')).sort((a,b)=>(b.abr||0)-(a.abr||0));
if(videos[0]&&audios[0])return{kind:'mux',video:videos[0],audio:audios[0],height:videos[0].height};
const fallback=fs.filter(f=>f.height&&f.height<=target&&f.vcodec&&f.vcodec!=='none'&&f.acodec&&f.acodec!=='none').sort((a,b)=>(b.height-a.height)||((b.tbr||0)-(a.tbr||0)))[0];if(fallback)return{kind:'direct',url:fallback.url,formatId:fallback.format_id,height:fallback.height,ext:fallback.ext};
return null;}

const server=http.createServer(async(req,res)=>{try{if(req.method==='OPTIONS'){res.writeHead(204,{'access-control-allow-origin':'*','access-control-allow-methods':'GET,HEAD,OPTIONS'});return res.end();}const u=new URL(req.url,'http://localhost');const path=u.pathname;
if(path==='/')return send(res,200,{service:'Ivy yt-dlp mux backend',version:'0.1.2',clients:CLIENTS,ffmpeg:Boolean(ffmpegPath)});
let m=path.match(/^\/probe\/([A-Za-z0-9_-]{11})\.json$/);if(m){const r=await extractBest(m[1]);return send(res,200,{ok:true,id:m[1],winner:r.client,summary:r.summary,attempts:r.attempts,title:r.info?.title});}
m=path.match(/^\/stream\/([A-Za-z0-9_-]{11})\/(2160|1440|1080|720|480|360)\.mp4$/);if(m){const [,id,q]=m;const r=await extractBest(id);const picked=pickSources(r.info,q);if(!picked)return send(res,404,{error:'no suitable format',id,q,winner:r.client,summary:r.summary});if(picked.kind==='direct'){res.writeHead(302,{Location:picked.url,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});return res.end();}
res.writeHead(200,{'Content-Type':'video/mp4','Cache-Control':'no-store','Access-Control-Allow-Origin':'*','Accept-Ranges':'none','Transfer-Encoding':'chunked'});
const args=['-loglevel','warning','-user_agent',UA,'-i',picked.video.url,'-user_agent',UA,'-i',picked.audio.url,'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','frag_keyframe+empty_moov+default_base_moof','-f','mp4','pipe:1'];
const ff=spawn(ffmpegPath,args,{stdio:['ignore','pipe','pipe']});ff.stdout.pipe(res);ff.stderr.on('data',d=>console.log('[FFMPEG]',String(d).trim()));ff.on('close',code=>{console.log('[FFMPEG-CLOSE]',id,q,picked.height,code);if(!res.writableEnded)res.end();});req.on('close',()=>{if(!ff.killed)ff.kill('SIGKILL');});return;}
return send(res,404,{error:'not found',path});}catch(e){console.error('[ERROR]',String(e));return send(res,502,{error:String(e),attempts:e?.attempts||undefined});}});
server.listen(PORT,'0.0.0.0',()=>{console.log('Ivy yt-dlp mux backend listening',PORT);void extractBest('AjSxpi8E9WE').then(r=>console.log('[SELFTEST]',JSON.stringify({winner:r.client,summary:r.summary,attempts:r.attempts,title:r.info?.title}))).catch(e=>console.error('[SELFTEST-FAIL]',String(e),JSON.stringify(e?.attempts||[])));void testYoutubeOne('AjSxpi8E9WE').catch(e=>console.error('[YOUTUBEONE-FAIL]',String(e)));});