import http from 'node:http';
import youtubedl from 'youtube-dl-exec';
const PORT=Number(process.env.PORT||10000),MUX='https://ivy-ytmux-backend.onrender.com',DEFAULT_ID='AjSxpi8E9WE',CHANNEL_HANDLE='KhoaiLangThang',ADDON_ID='community.ivy.youtube.khoailangthang',CATALOG_ID='ivy-khoai-lang-thang';
const videoMap=new Map(),qc=new Map(),sc=new Map();let loading=false,loaded=0;
videoMap.set(DEFAULT_ID,{id:DEFAULT_ID,title:'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu'});
function send(r,c,b){r.writeHead(c,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*'});r.end(JSON.stringify(b))}
function meta(v){return{id:`yt:${v.id}`,type:'movie',name:v.title||`YouTube ${v.id}`,poster:`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`,background:`https://i.ytimg.com/vi/${v.id}/maxresdefault.jpg`,description:v.description||'Khoai Lang Thang / Food & Travel',genres:['YouTube','Khoai Lang Thang','Travel'],releaseInfo:'YouTube'}}
async function scan(t){try{let d=await youtubedl(`https://www.youtube.com/@${CHANNEL_HANDLE}/${t}`,{dumpSingleJson:true,flatPlaylist:true,skipDownload:true,noWarnings:true,ignoreErrors:true});for(const e of d?.entries||[])if(/^[\w-]{11}$/.test(e?.id||''))videoMap.set(e.id,{id:e.id,title:e.title,description:e.description})}catch(e){console.log('[SCAN-FAIL]',t,String(e))}}
async function refresh(){if(loading||Date.now()-loaded<216e5)return;loading=true;try{await scan('videos');await scan('shorts');loaded=Date.now();console.log('[CATALOG]',videoMap.size)}finally{loading=false}}
async function transport(id){let c=qc.get(id);if(c&&c.e>Date.now())return c.v;try{let r=await fetch(`${MUX}/qualities/${id}.json`,{signal:AbortSignal.timeout(90000)}),v=await r.json();if(!r.ok)throw Error(`HTTP ${r.status}`);qc.set(id,{v,e:Date.now()+(v.complete?216e5:15000)});return v}catch(e){console.log('[TRANSPORT-FAIL]',id,String(e));return null}}
async function source(id){let c=sc.get(id);if(c&&c.e>Date.now())return c.v;try{let d=await youtubedl(`https://www.youtube.com/watch?v=${id}`,{dumpSingleJson:true,skipDownload:true,noWarnings:true,ignoreErrors:true,extractorArgs:'youtube:player_client=web'});let hs=[...new Set((d?.formats||[]).filter(f=>f&&f.vcodec&&f.vcodec!=='none'&&Number(f.height)>0).map(f=>Number(f.height)))].sort((a,b)=>b-a);let v={ok:hs.length>0,qualities:hs,max:hs[0]||null};sc.set(id,{v,e:Date.now()+216e5});console.log('[SOURCE-YOUTUBE]',id,hs.join(','));return v}catch(e){console.log('[SOURCE-YOUTUBE-FAIL]',id,String(e));return{ok:false,qualities:[],max:null}}}
const manifest={id:ADDON_ID,version:'11.1.2',name:'Ivy ❤️ Khoai Lang Thang',description:'Independent source quality when available; safe playable fallback when source inspection is blocked.',resources:['catalog','meta','stream'],types:['movie'],catalogs:[{type:'movie',id:CATALOG_ID,name:'Khoai Lang Thang • Full Channel'}],idPrefixes:['yt:']};
http.createServer(async(req,res)=>{try{
 if(req.method==='OPTIONS'){res.writeHead(204,{'access-control-allow-origin':'*'});return res.end()}
 let p=decodeURIComponent(new URL(req.url,'http://x').pathname);
 if(p==='/')return send(res,200,{service:manifest.name,version:manifest.version,videos:videoMap.size});if(p==='/manifest.json')return send(res,200,manifest);
 if(p===`/catalog/movie/${CATALOG_ID}.json`){void refresh();return send(res,200,{metas:[...videoMap.values()].map(meta)})}
 let m=p.match(/^\/meta\/movie\/yt:([\w-]{11})\.json$/);if(m)return send(res,200,{meta:meta(videoMap.get(m[1])||{id:m[1]})});
 m=p.match(/^\/stream\/movie\/yt:([\w-]{11})\.json$/);if(m){let id=m[1],[src,tr]=await Promise.all([source(id),transport(id)]),arr=[],tq=new Map((tr?.qualities||[]).map(x=>[x.quality,x]));
  if(src.ok){let genuine=src.qualities.filter(q=>tq.has(q));if(genuine.length){let top=genuine[0],x=tq.get(top);arr.push({name:`AUTO • ${top}p`,title:`Source verified ${top}p • ${x.codec}`,url:`${MUX}/stream/${id}/${top}.mp4`,behaviorHints:{notWebReady:true}});for(const q of genuine){let z=tq.get(q);arr.push({name:`Ivy YouTube • ${q}p`,title:`Source verified ${q}p • ${z.codec}`,url:`${MUX}/stream/${id}/${q}.mp4`,behaviorHints:{notWebReady:true}})}console.log('[AUTO-SOURCE]',id,src.max)}
  if(!arr.length){let safe=[360,240,144].filter(q=>tq.has(q));for(const q of safe){let z=tq.get(q);arr.push({name:`Ivy YouTube • ${q}p`,title:`PLAYABLE FALLBACK • source max not verified • ${z.codec}`,url:`${MUX}/stream/${id}/${q}.mp4`,behaviorHints:{notWebReady:true}})}console.log('[SOURCE-BLOCKED-FALLBACK]',id,safe.join(','))}
  return send(res,200,{streams:arr})}
 return send(res,404,{error:'not found'});
}catch(e){console.log('[ERROR]',String(e));return send(res,502,{error:String(e)})}}).listen(PORT,'0.0.0.0',()=>{console.log('[START v11.1.2]',PORT);void refresh()});
