import http from 'node:http';

const PORT = Number(process.env.PORT || 10000);
const DEFAULT_ID = 'AjSxpi8E9WE';
const ADDON_ID = 'community.ivy.youtube.external.demo';
const CATALOG_ID = 'ivy-youtube-external-demo';
const TITLE = 'Hành trình xuyên đảo núi lửa Iceland P5 - Du lịch Châu Âu';
const POSTER = `https://i.ytimg.com/vi/${DEFAULT_ID}/hqdefault.jpg`;

function headers() {
  return {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,OPTIONS',
    'access-control-allow-headers': '*'
  };
}
function send(res, code, body) {
  res.writeHead(code, headers());
  res.end(JSON.stringify(body));
}

const manifest = {
  id: ADDON_ID,
  version: '3.0.0',
  name: 'Ivy ❤️ YouTube External Demo',
  description: 'YouTube demo using externalUrl, matching the trailer-addon playback approach.',
  resources: ['catalog', 'meta', 'stream'],
  types: ['movie'],
  catalogs: [{ type: 'movie', id: CATALOG_ID, name: 'Ivy ❤️ YouTube External' }],
  idPrefixes: ['yt:']
};

const meta = {
  id: `yt:${DEFAULT_ID}`,
  type: 'movie',
  name: TITLE,
  poster: POSTER,
  background: `https://i.ytimg.com/vi/${DEFAULT_ID}/maxresdefault.jpg`,
  description: 'Demo mở video YouTube bằng externalUrl.',
  genres: ['YouTube', 'Travel'],
  releaseInfo: 'YouTube'
};

const server = http.createServer((req, res) => {
  try {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, headers());
      return res.end();
    }
    const u = new URL(req.url, 'http://localhost');
    let path;
    try { path = decodeURIComponent(u.pathname); } catch { path = u.pathname; }
    console.log(req.method, path);

    if (path === '/') return send(res, 200, { service: manifest.name, version: manifest.version, manifest: '/manifest.json' });
    if (path === '/manifest.json') return send(res, 200, manifest);
    if (path === `/catalog/movie/${CATALOG_ID}.json`) return send(res, 200, { metas: [meta] });

    const mm = path.match(/^\/meta\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (mm) return send(res, 200, { meta: mm[1] === DEFAULT_ID ? meta : null });

    const sm = path.match(/^\/stream\/movie\/yt:([A-Za-z0-9_-]{11})\.json$/);
    if (sm) {
      const id = sm[1];
      const streams = [{
        name: '▶️ Watch on YouTube',
        title: 'Open YouTube',
        externalUrl: `https://www.youtube.com/watch?v=${id}`
      }];
      console.log('[stream-external]', JSON.stringify(streams));
      return send(res, 200, { streams });
    }

    return send(res, 404, { error: 'not found', path });
  } catch (e) {
    console.error('[request-error]', String(e));
    return send(res, 500, { error: String(e) });
  }
});

server.listen(PORT, '0.0.0.0', () => console.log('Ivy YouTube externalUrl demo listening', PORT));
