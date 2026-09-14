import http from 'node:http';
import { Readable } from 'node:stream';
import youtubedl from 'youtube-dl-exec';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.demo';
const CATALOG_ID = 'ivy-youtube-demo';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;

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
function originFromReq(req) {
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0].trim();
  const host = String(req.headers['x-forwarded-host'] || req.headers.host || 'ivy-youtubejs-direct-test.onrender.com').split(',')[0].trim();
  return `${proto}://${host}`;
}

async function getFreshInfo(id) {
  const url = `https://www.youtube.com/watch?v=${id}`;
  console.log('[yt-dlp] fresh', id);
  const info = await youtubedl(url, {
    dumpSingleJson: true,
    noWarnings: true,
    noCacheDir: true,
    noPlaylist: true,
    jsRuntimes: 'node',
    extractorArgs: 'generic:impersonate',
    ignoreNoFormatsError: true
  }, { timeout: 90000 });
  return info;
}

function pickMuxed360(info) {
  const formats = Array.isArray(info?.formats) ? info.formats : [];
  return formats.find(f => String(f.format_id) === '18' && f.url && f.vcodec && f.vcodec !== 'none' && f.acodec && f.acodec !== 'none')
    || formats.find(f => f.url && f.ext === 'mp4' && f.vcodec && f.vcodec !== 'none' && f.acodec && f.acodec !== 'none' && Number(f.height || 0) <= 480)
    || formats.find(f => f.url && f.vcodec && f.vcodec !== 'none' && f.acodec && f.acodec !== 'none');
}

async function inspect(id) {
  const info = await getFreshInfo(id);
  const formats = (info.formats || []).map(f => ({
    format_id: f.format_id,
    ext: f.ext,
    height: f.height,
    vcodec: f.vcodec,
    acodec: f.acodec,
    hasUrl: Boolean(f.url)
  }));
  const pick = pickMuxed360(info);
  return { ok: Boolean(pick), id, title: info.title, picked: pick ? { format_id: pick.format_id, ext: pick.ext, height: pick.height, vcodec: pick.vcodec, acodec: pick.acodec } : null, formats };
}

async function proxy360(req, res, id) {
  const info = await getFreshInfo(id);
  const muxed = pickMuxed360(info);
  if (!muxed?.url) return send(res, 404, { error: 'No muxed YouTube format found' });

  const ytHeaders = {
    'Referer': 'https://www.youtube.com/',
    'Origin': 'https://www.youtube.com',
    'User-Agent': info.http_headers?.['User-Agent'] || 'Mozilla/5.0'
  };
  if (req.headers.range) ytHeaders.Range = String(req.headers.range);

  console.log('[play] proxy', id, muxed.format_id, muxed.height, req.headers.range || 'full');
  const upstream = await fetch(muxed.url, { headers: ytHeaders, redirect: 'follow' });
  console.log('[play] upstream', upstream.status, upstream.headers.get('content-type'), upstream.headers.get('content-length'), upstream.headers.get('content-range'));

  if (!upstream.ok && upstream.status !== 206) {
    const body = await upstream.text().catch(() => '');
    return send(res, 502, { error: `YouTube CDN ${upstream.status}`, body: body.slice(0, 200) });
  }

  res.statusCode = upstream.status;
  res.setHeader('Content-Type', upstream.headers.get('content-type') || 'video/mp4');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  for (const h of ['content-length', 'content-range', 'accept-ranges']) {
    const v = upstream.headers.get(h);
    if (v) res.setHeader(h, v);
  }
  if (req.method === 'HEAD' || !upstream.body) return res.end();
  Readable.fromWeb(upstream.body).pipe(res);
}

const manifest = {
  id: ADDON_ID,
  version: '1.1.0',
  name: 'Ivy ❤️ YouTube Demo',
  description: 'YouTube demo using the same yt-dlp muxed-MP4 playback path as working Stremio YouTube addons.',
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
  description: 'Demo YouTube playback through fresh yt-dlp extraction and muxed MP4 proxy.',
  genres: ['YouTube', 'Travel'],
  releaseInfo: 'YouTube'
};

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'OPTIONS') { res.writeHead(204, jsonHeaders()); return res.end(); }
    const u = new URL(req.url, 'http://localhost');
    let path;
    try { path = decodeURIComponent(u.pathname); } catch { path = u.pathname; }
    console.log(req.method, path);

    if (path === '/') return send(res, 200, { service: 'Ivy YouTube Nuvio demo', version: manifest.version, manifest: '/manifest.json', test: `/inspect/${DEFAULT_ID}` });
    if (path === '/manifest.json') return send(res, 200, manifest);
    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });

    const metaMatch = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (metaMatch) return send(res, 200, { meta: metaMatch[1] === DEFAULT_ID ? meta : null });

    const streamMatch = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (streamMatch) {
      const id = streamMatch[1];
      const origin = originFromReq(req);
      return send(res, 200, { streams: [
        { name: 'Ivy YouTube • MP4 360p', title: 'yt-dlp muxed MP4 • video + audio', url: `${origin}/play/${id}.mp4` },
        { name: 'YouTube native', title: 'Native YouTube fallback', ytId: id }
      ] });
    }

    const playMatch = path.match(/^\/play\/([A-Za-z0-9_-]{11})\.mp4$/);
    if (playMatch) return await proxy360(req, res, playMatch[1]);

    const inspectMatch = path.match(/^\/inspect\/([A-Za-z0-9_-]{11})$/);
    if (inspectMatch) return send(res, 200, await inspect(inspectMatch[1]));

    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error('[request-error]', String(e), e?.stack || '');
    if (!res.headersSent) return send(res, 502, { error: String(e) });
    res.destroy(e);
  }
});
server.listen(PORT, '0.0.0.0', () => console.log('Ivy YouTube yt-dlp demo listening', PORT));
