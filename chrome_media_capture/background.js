const MAX=100;
const key='ivyMediaRequests';
async function save(row){const old=await chrome.storage.local.get(key);let rows=old[key]||[];const i=rows.findIndex(x=>x.url===row.url);if(i>=0)rows[i]={...rows[i],...row};else rows.unshift(row);rows=rows.slice(0,MAX);await chrome.storage.local.set({[key]:rows});}
function isMedia(u){return /googlevideo\.com\/videoplayback/i.test(u)||/[?&](mime|itag)=/i.test(u);}
chrome.webRequest.onBeforeRequest.addListener(d=>{if(isMedia(d.url))save({url:d.url,tabId:d.tabId,type:d.type,startedAt:new Date().toISOString()});},{urls:['https://*.googlevideo.com/*']});
chrome.webRequest.onResponseStarted.addListener(d=>{if(isMedia(d.url))save({url:d.url,tabId:d.tabId,type:d.type,status:d.statusCode,responseAt:new Date().toISOString()});},{urls:['https://*.googlevideo.com/*']});