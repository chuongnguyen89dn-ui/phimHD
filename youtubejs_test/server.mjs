import http from 'node:http';
import { Readable } from 'node:stream';
import { Innertube, UniversalCache } from 'youtubei.js';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.demo';
const CATALOG_ID = 'ivy-youtube-demo';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;
let yt;

async function client() {
  if (!yt) yt = await Innertube.create({ cache: new UniversalCache(false), generate_session_locally: true });
  return yt;
}

function jsonHeaders() {
  return {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,HEAD,OPTIONS',
    'access-control-allow-headers': '*'
  };
}

function send(res, code, obj) {
  res.writeHead(code, jsonHeaders());
  res.end(JSON.stringify(obj));
}

async function resolveFormats(id) {
  const y = await client();
  const info = await y.getBasicInfo(id);
  const all = [...(info.streaming_data?.formats || []), ...(info.streaming_data?.adaptive_formats || [])];
  const rows = [];
  for (const f of all) {
    try {
      const url = await f.decipher(y.session.player);
      if (!url) continue;
      rows.push({
        itag: Number(f.itag),
        quality: f.quality_label || f.quality || 'auto',
        mimeType: f.mime_type?.toString?.() || String(f.mime_type || ''),
        bitrate: Number(f.bitrate || 0),
        hasVideo: Boolean(f.has_video),
        hasAudio: Boolean(f.has_audio),
        url
      });
    } catch (e) {
      console.log('decipher-fail', f.itag, String(e).slice(0, 180));
    }
  }
  rows.sort((a, b) => (Number(String(b.quality).replace(/\D/g, '')) || 0) - (Number(String(a.quality).replace(/\D/g, '')) || 0));
  return rows;
}

async function inspect(id) {
  const rows = await resolveFormats(id);
  return {
    ok: rows.length > 0,
    videoId: id,
    total: rows.length,
    progressive: rows.filter(x => x.hasVideo && x.hasAudio).map(x => ({ itag: x.itag, quality: x.quality, mimeType: x.mimeType })),
    adaptive: rows.filter(x => !(x.hasVideo && x.hasAudio)).map(x => ({ itag: x.itag, quality: x.quality, hasVideo: x.hasVideo, hasAudio: x.hasAudio, mimeType: x.mimeType }))
  };
}

function originFromReq(req) {
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0].trim();
  const host = String(req.headers['x-forwarded-host'] || req.headers.host || 'ivy-youtubejs-direct-test.onrender.com').split(',')[0].trim();
  return `${proto}://${host}`;
}

async function stremioStreams(id, req) {
  const rows = await resolveFormats(id);
  const progressive = rows.filter(f => f.hasVideo && f.hasAudio);
  const chosen = progressive.length ? progressive : rows.filter(f => f.hasVideo);
  console.log('stream-formats', JSON.stringify({ id, total: rows.length, progressive: progressive.map(x => [x.itag, x.quality]), chosen: chosen.slice(0, 6).map(x => [x.itag, x.quality]) }));
  const origin = originFromReq(req);
  return chosen.slice(0, 6).map(f => ({
    name: `Ivy YouTube • ${f.quality}`,
    title: `${TITLE}\nYouTube ID: ${id} • itag ${f.itag}`,
    url: `${origin}/play/${id}/${f.itag}`
  }));
}

async function proxyMedia(req, res, id, itag) {
  const rows = await resolveFormats(id);
  const fmt = rows.find(f => f.itag === Number(itag));
  if (!fmt) return send(res, 404, { error: 'itag not found', id, itag: Number(itag) });

  const headers = {
    'user-agent': String(req.headers['user-agent'] || 'Mozilla/5.0'),
    'accept': '*/*'
  };
  if (req.headers.range) headers.range = String(req.headers.range);

  console.log('proxy-start', id, itag, req.headers.range || 'full');
  const upstream = await fetch(fmt.url, { headers, redirect: 'follow' });
  console.log('proxy-upstream', upstream.status, upstream.headers.get('content-type'), upstream.headers.get('content-length'), upstream.headers.get('content-range'));

  const outHeaders = {
    'access-control-allow-origin': '*',
    'accept-ranges': upstream.headers.get('accept-ranges') || 'bytes',
    'cache-control': 'no-store'
  };
  for (const h of ['content-type', 'content-length', 'content-range', 'etag', 'last-modified']) {
    const v = upstream.headers.get(h);
    if (v) outHeaders[h] = v;
  }

  res.writeHead(upstream.status, outHeaders);
  if (req.method === 'HEAD' || !upstream.body) return res.end();
  Readable.fromWeb(upstream.body).pipe(res);
}

const manifest = {
  id: ADDON_ID,
  version: '1.0.4',
  name: 'Ivy ❤️ YouTube Demo',
  description: 'Demo phát video YouTube trong Nuvio bằng media proxy cùng IP với extractor.',
  resources: ['catalog', 'meta', 'stream'],
  types: ['movie'],
  catalogs: [{ type: 'movie', id: CATALOG_ID, name: 'Ivy ❤️ YouTube Demo' }],
  idPrefixes: ['yt:']
};

const meta = {
  id: `yt:${DEFAULT_ID}`,
  type: 'movie',
  name: TITLE,
  poster: POSTER,
  background: `https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,
  description: 'Video demo YouTube của Khoai Lang Thang. Luồng phát được resolve và proxy qua server addon.',
  genres: ['YouTube', 'Travel'],
  releaseInfo: 'YouTube'
};

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, jsonHeaders());
      return res.end();
    }

    const u = new URL(req.url, 'http://localhost');
    let path;
    try { path = decodeURIComponent(u.pathname); } catch { path = u.pathname; }
    console.log(req.method, path);

    if (path === '/') return send(res, 200, { service: 'Ivy YouTube Nuvio demo addon', version: manifest.version, manifest: '/manifest.json', videoId: DEFAULT_ID });
    if (path === '/manifest.json') return send(res, 200, manifest);
    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });

    const metaMatch = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (metaMatch) return send(res, 200, { meta: metaMatch[1] === DEFAULT_ID ? meta : null });

    const streamMatch = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (streamMatch) return send(res, 200, { streams: await stremioStreams(streamMatch[1], req) });

    const playMatch = path.match(/^\/play\/([A-Za-z0-9_-]{11})\/(\d+)$/);
    if (playMatch) return await proxyMedia(req, res, playMatch[1], playMatch[2]);

    const inspectMatch = path.match(/^\/inspect\/([A-Za-z0-9_-]{11})$/);
    if (inspectMatch) return send(res, 200, await inspect(inspectMatch[1]));
    if (path === '/test') return send(res, 200, await inspect(DEFAULT_ID));

    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error('request-error', String(e), e?.stack || '');
    if (!res.headersSent) return send(res, 502, { ok: false, error: String(e) });
    res.destroy(e);
  }
});

server.listen(PORT, '0.0.0.0', () => console.log('Ivy YouTube Nuvio demo listening', PORT));
