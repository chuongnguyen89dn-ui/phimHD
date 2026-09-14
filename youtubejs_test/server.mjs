import http from 'node:http';
import crypto from 'node:crypto';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.savetube.demo';
const CATALOG_ID = 'ivy-youtube-savetube-demo';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;
const SAVETUBE_KEY = Buffer.from('C5D58EF67A7584E4A29F6C35BBC4EB12', 'hex');
const SAVETUBE_DISCOVERY = [
  'https://media.savetube.me/api/random-cdn',
  'https://media.savetube.vip/api/random-cdn'
];
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Version/18.5 Mobile/15E148 Safari/604.1';

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
function signal(ms) { return AbortSignal.timeout(ms); }

async function readLimited(response, limit = 65536) {
  const reader = response.body?.getReader();
  if (!reader) return new Uint8Array();
  let total = 0;
  const chunks = [];
  try {
    while (total < limit) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      total += value.byteLength;
      if (total >= limit) break;
    }
  } finally {
    try { await reader.cancel(); } catch {}
  }
  const out = new Uint8Array(Math.min(total, limit));
  let offset = 0;
  for (const c of chunks) {
    const part = c.subarray(0, Math.min(c.byteLength, out.length - offset));
    out.set(part, offset);
    offset += part.byteLength;
    if (offset >= out.length) break;
  }
  return out;
}

async function probeMedia(url) {
  try {
    const r = await fetch(url, {
      method: 'GET',
      headers: { Range: 'bytes=0-65535', 'User-Agent': UA, Accept: '*/*' },
      redirect: 'follow',
      signal: signal(25000)
    });
    const ct = r.headers.get('content-type') || '';
    const data = await readLimited(r, 65536);
    return {
      ok: (r.status === 200 || r.status === 206) && data.byteLength > 0,
      status: r.status,
      contentType: ct,
      bytes: data.byteLength,
      finalUrl: r.url
    };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

function decryptSaveTube(enc) {
  const raw = Buffer.from(String(enc).replace(/\s/g, ''), 'base64');
  const iv = raw.subarray(0, 16);
  const payload = raw.subarray(16);
  const decipher = crypto.createDecipheriv('aes-128-cbc', SAVETUBE_KEY, iv);
  return JSON.parse(Buffer.concat([decipher.update(payload), decipher.final()]).toString('utf8'));
}

async function getSaveTubeCdn() {
  const attempts = [];
  for (const endpoint of SAVETUBE_DISCOVERY) {
    try {
      const r = await fetch(endpoint, {
        headers: { 'User-Agent': UA, Accept: 'application/json', Origin: 'https://ytsave.savetube.me', Referer: 'https://ytsave.savetube.me/' },
        signal: signal(15000)
      });
      const text = await r.text();
      let body = null;
      try { body = JSON.parse(text); } catch {}
      attempts.push({ endpoint, status: r.status, body: body ? { cdn: body.cdn } : text.slice(0, 120) });
      if (r.ok && body?.cdn) return { ok: true, cdn: body.cdn, attempts };
    } catch (e) {
      attempts.push({ endpoint, error: String(e) });
    }
  }
  return { ok: false, attempts };
}

async function resolveSaveTube(id, quality = '360') {
  const sourceUrl = `https://www.youtube.com/watch?v=${id}`;
  const cdnResult = await getSaveTubeCdn();
  if (!cdnResult.ok) return { ok: false, stage: 'cdn', ...cdnResult };
  const cdn = cdnResult.cdn;
  const base = `https://${cdn}`;
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    'User-Agent': UA,
    Origin: 'https://ytsave.savetube.me',
    Referer: 'https://ytsave.savetube.me/'
  };
  try {
    const infoRes = await fetch(`${base}/v2/info`, {
      method: 'POST', headers, body: JSON.stringify({ url: sourceUrl }), signal: signal(30000)
    });
    const infoText = await infoRes.text();
    let infoBody = null;
    try { infoBody = JSON.parse(infoText); } catch {}
    if (!infoRes.ok || !infoBody?.data) {
      return { ok: false, stage: 'info', cdn, status: infoRes.status, body: infoBody || infoText.slice(0, 200) };
    }
    const info = decryptSaveTube(infoBody.data);
    const requested = String(quality);
    const available = (info.video_formats || []).map(v => String(v.quality)).filter(Boolean);
    const chosen = available.includes(requested) ? requested : (available.includes('360') ? '360' : available[0]);
    if (!chosen) return { ok: false, stage: 'formats', cdn, title: info.title, available };

    const dlRes = await fetch(`${base}/download`, {
      method: 'POST', headers,
      body: JSON.stringify({ id, downloadType: 'video', quality: chosen, key: info.key }),
      signal: signal(30000)
    });
    const dlText = await dlRes.text();
    let dlBody = null;
    try { dlBody = JSON.parse(dlText); } catch {}
    const downloadUrl = dlBody?.data?.downloadUrl || dlBody?.data?.url || dlBody?.downloadUrl || null;
    if (!dlRes.ok || !downloadUrl) {
      return { ok: false, stage: 'download', cdn, status: dlRes.status, title: info.title, chosen, body: dlBody || dlText.slice(0, 200) };
    }
    const probe = await probeMedia(downloadUrl);
    return {
      ok: probe.ok,
      stage: probe.ok ? 'verified' : 'probe',
      provider: 'SaveTube', cdn, title: info.title, chosen, available,
      url: downloadUrl, probe
    };
  } catch (e) {
    return { ok: false, stage: 'exception', cdn, error: String(e) };
  }
}

const manifest = {
  id: ADDON_ID,
  version: '5.0.0',
  name: 'Ivy ❤️ YouTube SaveTube Demo',
  description: 'Tests SaveTube as a third-party media resolver and only exposes verified media to Nuvio.',
  resources: ['catalog', 'meta', 'stream'],
  types: ['movie'],
  catalogs: [{ type: 'movie', id: CATALOG_ID, name: 'Ivy ❤️ YouTube SaveTube' }],
  idPrefixes: ['yt:']
};

const meta = {
  id: `yt:${DEFAULT_ID}`,
  type: 'movie',
  name: TITLE,
  poster: POSTER,
  background: `https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,
  description: 'YouTube playback test through SaveTube third-party media URL.',
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

    if (path === '/') return send(res, 200, { service: manifest.name, version: manifest.version, manifest: '/manifest.json' });
    if (path === '/manifest.json') return send(res, 200, manifest);
    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });
    if (path === '/diag.json') return send(res, 200, await resolveSaveTube(DEFAULT_ID));

    const mm = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (mm) return send(res, 200, { meta: mm[1] === DEFAULT_ID ? meta : null });

    const sm = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (sm) {
      const resolved = await resolveSaveTube(sm[1]);
      console.log('[SAVETUBE-STREAM-RESOLVE]', JSON.stringify(resolved));
      if (!resolved.ok) return send(res, 200, { streams: [] });
      return send(res, 200, { streams: [{
        name: `Ivy YouTube • SaveTube ${resolved.chosen}p`,
        title: `Verified ${resolved.probe.status} • ${resolved.probe.contentType || 'media'} • ${resolved.probe.bytes} bytes`,
        url: resolved.url
      }] });
    }
    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error('[request-error]', String(e));
    return send(res, 500, { error: String(e) });
  }
});

server.listen(PORT, '0.0.0.0', async () => {
  console.log('Ivy YouTube SaveTube demo listening', PORT);
  const result = await resolveSaveTube(DEFAULT_ID);
  console.log('[SAVETUBE-SELFTEST]', JSON.stringify(result));
});
