// A tiny Chrome DevTools Protocol client (Node 22+ has WebSocket built in). Drives headless Chrome or Chromium that is already installed:
// no downloads, no dependencies. Used by the layout checks in this folder (see tests/test_layout.py and the README).
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const CANDIDATES = [process.env.CHROME_BIN, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'].filter(Boolean);
export const CHROME = CANDIDATES.find((p) => existsSync(p));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function launch({ scratch, args = [] } = {}) {
  if (!CHROME) throw new Error('No Chrome or Chromium found (set CHROME_BIN to its path)');
  const dir = mkdtempSync(join(scratch || tmpdir(), 'chrome-'));
  const proc = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${dir}`, '--no-first-run', '--no-default-browser-check',
    '--disable-gpu', '--hide-scrollbars=false', '--force-color-profile=srgb', '--window-size=1400,900', ...args, 'about:blank'], { stdio: 'ignore' });
  let list, port;                                                 // Chrome picks a free debugging port and writes it in its profile folder
  for (let i = 0; i < 80 && !list; i++) {
    try { port = Number(readFileSync(join(dir, 'DevToolsActivePort'), 'utf8').split('\n')[0]); list = port ? await (await fetch(`http://127.0.0.1:${port}/json`)).json() : null; if (list && !list.length) list = null; } catch { /* still starting */ }
    await sleep(250);
  }
  if (!list) { proc.kill(); throw new Error('Chrome did not start'); }
  const target = list.find((t) => t.type === 'page');
  const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pending = new Map(); const listeners = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result); }
    else for (const l of listeners) l(msg);
  };
  const send = (method, params = {}, timeout = 20000) => new Promise((res, rej) => {
    const i = ++id; const t = setTimeout(() => { pending.delete(i); rej(new Error(`timeout: ${method}`)); }, timeout);
    pending.set(i, { res: (v) => { clearTimeout(t); res(v); }, rej: (e) => { clearTimeout(t); rej(e); } }); ws.send(JSON.stringify({ id: i, method, params }));
  });
  ws.onclose = () => { for (const { rej } of pending.values()) rej(new Error('browser connection closed')); pending.clear(); };
  listeners.push((m) => { if (m.method === 'Page.javascriptDialogOpening') send('Page.handleJavaScriptDialog', { accept: true }).catch(() => {}); });   // never let a dialog freeze a run
  await send('Page.enable'); await send('Runtime.enable');
  const api = {
    version: version.Browser, send,
    on: (fn) => listeners.push(fn),
    async viewport(w, h, dpr = 1, mobile = false) {
      await send('Emulation.setDeviceMetricsOverride', { width: Math.round(w), height: Math.round(h), deviceScaleFactor: dpr, mobile });
    },
    // Browser zoom is not device-pixel-ratio emulation: at 150% zoom the page sees a viewport 1/1.5 as wide AND a 1.5 ratio.
    async zoomed(screenW, screenH, zoom) { await api.viewport(screenW / zoom, screenH / zoom, zoom); },
    async goto(url, { settle = 900 } = {}) {
      await send('Page.navigate', { url });
      for (let i = 0; i < 80; i++) { const r = await api.eval('document.readyState'); if (r === 'complete') break; await sleep(100); }
      await sleep(settle);
    },
    async hash(h, settle = 900) { await api.eval(`location.hash = ${JSON.stringify(h)}`); await sleep(settle); },
    async eval(expr) {
      const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    },
    async shot(path, { full = false, jpeg = 0 } = {}) {
      const r = await send('Page.captureScreenshot', { format: jpeg ? 'jpeg' : 'png', ...(jpeg ? { quality: jpeg } : {}), captureBeyondViewport: full, fromSurface: true });
      writeFileSync(path, Buffer.from(r.data, 'base64'));
    },
    async close() { try { await send('Browser.close'); } catch { /* gone */ } try { ws.close(); } catch { /* gone */ } proc.kill(); try { rmSync(dir, { recursive: true, force: true }); } catch { /* it is only a temporary folder */ } },
    sleep,
  };
  return api;
}

export async function login(page, base, user, pass = 'testpass123') {
  await page.goto(base + '/', { settle: 300 });
  const r = await page.eval(`fetch('/api/auth/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: ${JSON.stringify(user)}, password: ${JSON.stringify(pass)}})}).then(r => r.status)`);
  if (r !== 200) throw new Error('login failed: ' + r);
}
