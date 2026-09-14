import http from 'node:http';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.thirdparty.demo';
const CATALOG_ID = 'ivy-youtube-thirdparty-demo';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;
const PROVIDERS = [
  'https://inv.nadeko.net',
  'https://invidious.nerdvpn.de',
  'https://yt.chocolatemoo53.com',
  'https://invidious.tiekoetter.com'
];

function jsonHeaders() {
  return {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,OPTIONS',
    'access-control-allow-headers': '*'
  };
}
function send(res, code, body) {
  res.writeHead(code, jsonHeaders());
  res.end(JSON.stringify(body));
}
function timeoutSignal(ms) { return AbortSignal.timeout(ms); }
function absoluteUrl(base, value) {
  if (!value) return null;
  try { return new URL(value, base).toString(); } catch { return null; }
}

async function probeMedia(url) {
  try {
    const r = await fetch(url, {
      method: 'GET',
      headers: { Range: 'bytes=0-1023', 'User-Agent': 'Mozilla/5.0' },
      redirect: 'follow',
      signal: timeoutSignal(15000)
    });
    const ct = r.headers.get('content-type') || '';
    const buf = await r.arrayBuffer();
    return { ok: (r.status === 200 || r.status === 206) && buf.byteLength > 0, status: r.status, contentType: ct, bytes: buf.byteLength, finalUrl: r.url };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

function candidateList(base, info) {
  const out = [];
  for (const f of info?.formatStreams || []) {
    const url = absoluteUrl(base, f.url);
    if (!url) continue;
    const container = String(f.container || '').toLowerCase();
    const mime = String(f.type || '').toLowerCase();
    if (container === 'mp4' || mime.includes('video/mp4')) {
      out.push({ kind: 'mp4', quality: f.qualityLabel || f.quality || '', url });
    }
  }
  if (info?.hlsUrl) {
    const url = absoluteUrl(base, info.hlsUrl);
    if (url) out.push({ kind: 'hls', quality: 'HLS', url });
  }
  return out;
}

async function resolveFromProvider(base, id) {
  const api = `${base}/api/v1/videos/${id}`;
  try {
    const r = await fetch(api, { headers: { Accept: 'application/json', 'User-Agent': 'Mozilla/5.0' }, signal: timeoutSignal(20000) });
    if (!r.ok) return { provider: base, ok: false, apiStatus: r.status };
    const info = await r.json();
    const candidates = candidateList(base, info);
    for (const c of candidates) {
      const probe = await probeMedia(c.url);
      console.log('[THIRDPARTY-PROBE]', JSON.stringify({ provider: base, candidate: { kind: c.kind, quality: c.quality }, probe }));
      if (probe.ok) return { provider: base, ok: true, title: info.title, candidate: c, probe };
    }
    return { provider: base, ok: false, title: info.title, candidateCount: candidates.length };
  } catch (e) {
    return { provider: base, ok: false, error: String(e) };
  }
}

async function resolveMedia(id) {
  const attempts = [];
  for (const base of PROVIDERS) {
    const result = await resolveFromProvider(base, id);
    attempts.push(result);
    console.log('[THIRDPARTY]', JSON.stringify(result));
    if (result.ok) return { ok: true, result, attempts };
  }
  return { ok: false, attempts };
}

const manifest = {
  id: ADDON_ID,
  version: '4.0.0',
  name: 'Ivy ❤️ YouTube Third-Party Demo',
  description: 'Tests verified MP4/HLS media returned by third-party Invidious providers.',
  resources: ['catalog', 'meta', 'stream'],
  types: ['movie'],
  catalogs: [{ type: 'movie', id: CATALOG_ID, name: 'Ivy ❤️ YouTube Third-Party' }],
  idPrefixes: ['yt:']
};

const meta = {
  id: `yt:${DEFAULT_ID}`,
  type: 'movie',
  name: TITLE,
  poster: POSTER,
  background: `https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,
  description: 'YouTube playback test through verified third-party media URLs.',
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

    if (path === '/') return send(res, 200, { service: manifest.name, version: manifest.version, manifest: '/manifest.json' });
    if (path === '/manifest.json') return send(res, 200, manifest);
    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });
    if (path === '/diag.json') return send(res, 200, await resolveMedia(DEFAULT_ID));

    const mm = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (mm) return send(res, 200, { meta: mm[1] === DEFAULT_ID ? meta : null });

    const sm = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (sm) {
      const id = sm[1];
      const resolved = await resolveMedia(id);
      if (!resolved.ok) return send(res, 200, { streams: [] });
      const { candidate, provider } = resolved.result;
      const streams = [{
        name: `Ivy YouTube • ${candidate.kind.toUpperCase()} ${candidate.quality}`,
        title: `Third-party verified via ${new URL(provider).hostname}`,
        url: candidate.url
      }];
      console.log('[STREAM-VERIFIED]', JSON.stringify(streams));
      return send(res, 200, { streams });
    }

    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error('[request-error]', String(e));
    return send(res, 500, { error: String(e) });
  }
});

server.listen(PORT, '0.0.0.0', async () => {
  console.log('Ivy YouTube third-party demo listening', PORT);
  const result = await resolveMedia(DEFAULT_ID);
  console.log('[THIRDPARTY-SELFTEST]', JSON.stringify(result));
});
