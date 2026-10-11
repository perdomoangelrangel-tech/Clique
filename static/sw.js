/* Clique's service worker. It keeps the app's shell (the page and the scripts, styles and fonts it links to) so the app opens without a
   connection and can say so. It never keeps or answers anything from /api/ or /uploads/: balances, prices and results always come from
   the server (D8), or not at all. Files are always asked of the network first, so a new deploy shows up as it did before the worker;
   the kept copy is only used when the network is not there. Tests: tests/js/sw.test.mjs */

const VERSION = 'clique-shell-v1';
const EXTRA = ['/manifest.webmanifest', '/i18n/en.json'];
const NEVER = /^\/(api|uploads)\//;

self.addEventListener('install', (event) => {
  event.waitUntil(keepShell().then(() => self.skipWaiting()));
});

/* The page lists what it needs (stylesheets, fonts, and every script of the first screen as modulepreload, added by the server), so the
   list of files to keep is read from the page itself and never goes stale. */
async function keepShell() {
  const cache = await caches.open(VERSION);
  const page = await fetch('/', { cache: 'no-cache' });
  if (!page.ok) throw new Error('the page did not load: ' + page.status);
  const html = await page.clone().text();
  await cache.put('/', page);
  const files = new Set(EXTRA);
  for (const m of html.matchAll(/<(?:link|script)\b[^>]*\b(?:href|src)="(\/[^"]*)"/g)) files.add(m[1]);
  await Promise.all([...files].map((f) => cache.add(f).catch(() => { /* one missing file must not stop the rest */ })));
}

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((names) => Promise.all(names.filter((n) => n !== VERSION).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || NEVER.test(url.pathname)) return;
  // every page of the app is the same page (the address after # picks the screen), so offline any of them opens the kept one
  event.respondWith(networkFirst(req, req.mode === 'navigate' ? '/' : null));
});

async function networkFirst(req, keepAs) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(keepAs || req, res.clone()).catch(() => {});
    return res;
  } catch (offline) {
    const kept = await cache.match(keepAs || req, { ignoreSearch: !!keepAs });
    if (kept) return kept;
    throw offline;
  }
}
