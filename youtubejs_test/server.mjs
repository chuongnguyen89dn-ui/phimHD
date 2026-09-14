import http from 'node:http';
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

function cors() {
  return {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,OPTIONS',
    'access-control-allow-headers': '*'
  };
}

function send(res, code, obj) {
  res.writeHead(code, cors());
  res.end(JSON.stringify(obj));
}

async function probe(url) {
  try {
    const r = await fetch(url, { headers: { Range: 'bytes=0-1' }, redirect: 'follow' });
    const b = await r.arrayBuffer();
    return { ok: (r.status === 200 || r.status === 206) && b.byteLength > 0, status: r.status, bytes: b.byteLength, contentType: r.headers.get('content-type') };
  } catch (e) {
    return { ok: false, error: String(e).slice(0, 240) };
  }
}

async function inspect(id) {
  const y = await client();
  const info = await y.getBasicInfo(id);
  const all = [...(info.streaming_data?.formats || []), ...(info.streaming_data?.adaptive_formats || [])];
  const rows = [];
  for (const f of all) {
    try {
      const url = await f.decipher(y.session.player);
      if (!url) continue;
      const p = await probe(url);
      rows.push({
        itag: f.itag,
        quality: f.quality_label || f.quality,
        container: f.container,
        mimeType: f.mime_type?.toString?.() || String(f.mime_type || ''),
        bitrate: f.bitrate,
        contentLength: f.content_length,
        hasVideo: f.has_video,
        hasAudio: f.has_audio,
        verified: p.ok,
        probe: p,
        url
      });
    } catch (e) {
      rows.push({ itag: f.itag, quality: f.quality_label || f.quality, error: String(e).slice(0, 240), verified: false });
    }
  }
  rows.sort((a, b) => (Number(String(b.quality || '').replace(/\D/g, '')) || 0) - (Number(String(a.quality || '').replace(/\D/g, '')) || 0));
  return { ok: rows.some(x => x.verified), videoId: id, total: rows.length, verifiedCount: rows.filter(x => x.verified).length, formats: rows };
}

async function stremioStreams(id) {
  const result = await inspect(id);
  const progressive = result.formats.filter(f => f.verified && f.hasVideo && f.hasAudio && f.url);
  const candidates = progressive.length ? progressive : result.formats.filter(f => f.verified && f.url);
  return candidates.slice(0, 6).map(f => ({
    name: `Ivy YouTube • ${f.quality || 'auto'}${f.hasAudio ? '' : ' • video-only'}`,
    title: `${TITLE}\nYouTube ID: ${id} • itag ${f.itag}`,
    url: f.url
  }));
}

const manifest = {
  id: ADDON_ID,
  version: '1.0.3',
  name: 'Ivy ❤️ YouTube Demo',
  description: 'Demo phát trực tiếp một video YouTube trong Nuvio qua URL media được resolve tại thời điểm Play.',
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
  description: 'Video demo YouTube của Khoai Lang Thang. Stream được resolve bằng youtubei.js khi bấm Play.',
  genres: ['YouTube', 'Travel'],
  releaseInfo: 'YouTube'
};

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, cors());
      return res.end();
    }

    const u = new URL(req.url, 'http://localhost');
    let path;
    try { path = decodeURIComponent(u.pathname); }
    catch { path = u.pathname; }

    console.log(req.method, path);

    if (path === '/') {
      return send(res, 200, {
        service: 'Ivy YouTube Nuvio demo addon',
        manifest: '/manifest.json',
        videoId: DEFAULT_ID,
        catalog: `/catalog/movie/${CATALOG_ID}.json`,
        meta: `/meta/movie/yt:${DEFAULT_ID}.json`,
        stream: `/stream/movie/yt:${DEFAULT_ID}.json`
      });
    }

    if (path === '/manifest.json') return send(res, 200, manifest);

    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });

    const metaMatch = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (metaMatch) {
      if (metaMatch[1] !== DEFAULT_ID) return send(res, 200, { meta: null });
      return send(res, 200, { meta });
    }

    const streamMatch = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (streamMatch) {
      const streams = await stremioStreams(streamMatch[1]);
      return send(res, 200, { streams });
    }

    const inspectMatch = path.match(/^\/inspect\/([A-Za-z0-9_-]{11})$/);
    if (inspectMatch) return send(res, 200, await inspect(inspectMatch[1]));
    if (path === '/test') return send(res, 200, await inspect(DEFAULT_ID));

    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error(e);
    return send(res, 502, { ok: false, error: String(e), stack: String(e?.stack || '').split('\n').slice(0, 5) });
  }
});

server.listen(PORT, '0.0.0.0', () => console.log('Ivy YouTube Nuvio demo listening', PORT));
