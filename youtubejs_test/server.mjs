import http from 'node:http';
import { Innertube, UniversalCache } from 'youtubei.js';

const PORT=Number(process.env.PORT||10000);
const DEFAULT_ID='AjSxpi8E9WE';
let yt;
async function client(){ if(!yt) yt=await Innertube.create({cache:new UniversalCache(false),generate_session_locally:true}); return yt; }
function send(res,code,obj){res.writeHead(code,{'content-type':'application/json; charset=utf-8','cache-control':'no-store'});res.end(JSON.stringify(obj,null,2));}
async function probe(url){try{const r=await fetch(url,{headers:{Range:'bytes=0-1'},redirect:'follow'});const b=await r.arrayBuffer();return {ok:(r.status===200||r.status===206)&&b.byteLength>0,status:r.status,bytes:b.byteLength,contentType:r.headers.get('content-type')};}catch(e){return {ok:false,error:String(e).slice(0,240)}}}
async function inspect(id){
 const y=await client();
 const info=await y.getBasicInfo(id);
 const all=[...(info.streaming_data?.formats||[]),...(info.streaming_data?.adaptive_formats||[])];
 const rows=[];
 for(const f of all){
   try{
    const url=await f.decipher(y.session.player);
    if(!url) continue;
    const p=await probe(url);
    rows.push({itag:f.itag,quality:f.quality_label||f.quality,container:f.container,mimeType:f.mime_type?.toString?.()||String(f.mime_type||''),bitrate:f.bitrate,contentLength:f.content_length,hasVideo:f.has_video,hasAudio:f.has_audio,verified:p.ok,probe:p,urlHost:new URL(url).host,urlPrefix:url.slice(0,90)});
   }catch(e){rows.push({itag:f.itag,quality:f.quality_label||f.quality,error:String(e).slice(0,240),verified:false});}
 }
 rows.sort((a,b)=>(Number(String(b.quality||'').replace(/\D/g,''))||0)-(Number(String(a.quality||'').replace(/\D/g,''))||0));
 return {ok:rows.some(x=>x.verified),videoId:id,total:rows.length,verifiedCount:rows.filter(x=>x.verified).length,formats:rows};
}
const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://localhost');
 if(u.pathname==='/'){return send(res,200,{service:'Ivy YouTube.js isolated extractor',test:'/inspect/AjSxpi8E9WE'});}
 const m=u.pathname.match(/^\/inspect\/([A-Za-z0-9_-]{11})$/);if(m)return send(res,200,await inspect(m[1]));
 if(u.pathname==='/test')return send(res,200,await inspect(DEFAULT_ID));
 return send(res,404,{error:'not found'});
}catch(e){console.error(e);return send(res,502,{ok:false,error:String(e),stack:String(e?.stack||'').split('\n').slice(0,5)});}});
server.listen(PORT,'0.0.0.0',()=>console.log('Ivy YouTube.js test listening',PORT));
