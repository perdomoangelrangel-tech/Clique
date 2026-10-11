// The service worker (static/sw.js): keeps the app's shell so Clique opens without a connection, and never keeps anything from /api/
// (balances, prices and results always come from the server, D8). Run: node --test tests/js/sw.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const ORIGIN = 'https://clique.test';
const SRC = readFileSync(new URL('../../static/sw.js', import.meta.url), 'utf8');
const PAGE = `<!doctype html><html><head><link rel="stylesheet" href="/css/tokens.css"><link rel="preload" href="/fonts/a.woff2" as="font">
<link rel="manifest" href="/manifest.webmanifest"><link rel="modulepreload" href="/js/app.js"><link rel="modulepreload" href="/js/i18n.js">
<link rel="icon" href="data:image/svg+xml,x"></head><body><script type="module" src="/js/app.js"></script></body></html>`;

const keyOf = (r) => { const u = new URL(typeof r === 'string' ? r : r.url, ORIGIN); return u.pathname + u.search; };

function world() {
  const stores = new Map();
  const net = { online: true, files: new Map([['/', PAGE], ['/css/tokens.css', 'css'], ['/fonts/a.woff2', 'font'], ['/js/app.js', 'app'], ['/js/i18n.js', 'i18n'],
    ['/manifest.webmanifest', '{}'], ['/i18n/en.json', '{}'], ['/js/views/markets.js', 'markets'], ['/api/me', '{"user":null}']]), asked: [] };
  class FakeCache {
    constructor() { this.m = new Map(); }
    async put(req, res) { this.m.set(keyOf(req), await res.clone().text()); }
    async add(req) { const res = await fetchFake(req); if (!res.ok) throw new Error('bad'); await this.put(req, res); }
    async match(req, opts = {}) { let k = keyOf(req); if (opts.ignoreSearch) k = k.split('?')[0]; return this.m.has(k) ? new Response(this.m.get(k)) : undefined; }
    async keys() { return [...this.m.keys()]; }
  }
  const caches = {
    async open(n) { if (!stores.has(n)) stores.set(n, new FakeCache()); return stores.get(n); },
    async keys() { return [...stores.keys()]; },
    async delete(n) { return stores.delete(n); },
  };
  async function fetchFake(req) {
    const k = keyOf(req);
    net.asked.push(k);
    if (!net.online) throw new TypeError('Failed to fetch');
    const body = net.files.get(k.split('?')[0]);
    return body === undefined ? new Response('nope', { status: 404 }) : new Response(body, { status: 200 });
  }
  const handlers = {};
  const self = { location: new URL(ORIGIN + '/sw.js'), addEventListener: (t, fn) => { handlers[t] = fn; }, skipWaiting: async () => {}, clients: { claim: async () => {} } };
  vm.runInNewContext(SRC, { self, caches, fetch: fetchFake, URL, Response, Request, Headers, Promise, Set, Map, console });
  const fire = async (type, extra = {}) => {
    let waited = null, responded = null;
    const ev = { ...extra, waitUntil: (p) => { waited = p; }, respondWith: (p) => { responded = p; } };
    handlers[type](ev);
    if (waited) await waited;
    return responded;
  };
  const get = (path, mode = 'cors', method = 'GET', origin = ORIGIN) => fire('fetch', { request: { url: origin + path, method, mode } });
  return { stores, net, caches, fire, get };
}

test('installing keeps the page and everything it links to: styles, fonts, scripts, the manifest and the English words', async () => {
  const w = world();
  await w.fire('install');
  const [name] = await w.caches.keys();
  const kept = await (await w.caches.open(name)).keys();
  for (const p of ['/', '/css/tokens.css', '/fonts/a.woff2', '/js/app.js', '/js/i18n.js', '/manifest.webmanifest', '/i18n/en.json']) assert.ok(kept.includes(p), p);
  assert.ok(!kept.some((k) => k.startsWith('data:') || k.startsWith('/api/')));
});

test('online, files come from the network and the copy is refreshed', async () => {
  const w = world();
  await w.fire('install');
  w.net.files.set('/js/app.js', 'app v2');
  const res = await w.get('/js/app.js');
  assert.equal(await res.text(), 'app v2');
  w.net.online = false;
  assert.equal(await (await w.get('/js/app.js')).text(), 'app v2');
});

test('offline, any page of the app opens the kept shell', async () => {
  const w = world();
  await w.fire('install');
  w.net.online = false;
  for (const p of ['/', '/diseno', '/?x=1']) assert.equal(await (await w.get(p, 'navigate')).text(), PAGE, p);
});

test('offline, a file that was never kept fails as it would without the worker', async () => {
  const w = world();
  await w.fire('install');
  w.net.online = false;
  await assert.rejects(() => w.get('/js/views/poker.js'));
});

test('nothing from /api/ is ever answered by the worker (D8): not online, not offline', async () => {
  const w = world();
  await w.fire('install');
  assert.equal(await w.get('/api/me'), null);
  w.net.online = false;
  assert.equal(await w.get('/api/me'), null);
  assert.equal(await w.get('/api/stream'), null);
  assert.equal(await w.get('/uploads/avatars/x.png'), null);
  const kept = await (await w.caches.open((await w.caches.keys())[0])).keys();
  assert.ok(!kept.some((k) => k.startsWith('/api/')));
});

test('only GET from this site goes through the worker', async () => {
  const w = world();
  await w.fire('install');
  assert.equal(await w.get('/api/bets', 'cors', 'POST'), null);
  assert.equal(await w.get('/js/app.js', 'cors', 'POST'), null);
  assert.equal(await w.get('/lib.js', 'cors', 'GET', 'https://cdn.example.com'), null);
});

test('a new version clears the copies of the old one', async () => {
  const w = world();
  await (await w.caches.open('clique-shell-old')).put('/', new Response('old'));
  await w.fire('install');
  await w.fire('activate');
  const names = await w.caches.keys();
  assert.equal(names.length, 1);
  assert.notEqual(names[0], 'clique-shell-old');
});

test('the page links the manifest and the app registers the worker and says when there is no connection', () => {
  const html = readFileSync(new URL('../../static/index.html', import.meta.url), 'utf8');
  assert.match(html, /<link rel="manifest" href="\/manifest\.webmanifest">/);
  const app = readFileSync(new URL('../../static/js/app.js', import.meta.url), 'utf8');
  assert.match(app, /serviceWorker\.register\('\/sw\.js'\)/);
  assert.match(app, /addEventListener\('offline'/);
  assert.match(app, /t\('Sin conexión'\)/);
  const m = JSON.parse(readFileSync(new URL('../../static/manifest.webmanifest', import.meta.url), 'utf8'));
  assert.equal(m.lang, 'es-MX');
  assert.equal(m.start_url, '/');
  assert.equal(m.display, 'standalone');
  assert.ok(m.icons.length >= 1);
});
