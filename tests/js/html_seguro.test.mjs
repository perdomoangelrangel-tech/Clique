// HTML seguro: nothing a person types (names, messages, market titles, punishments, bios) ever turns into markup on screen.
// Run: node --test tests/js/html_seguro.test.mjs
//
// Three checks:
//   1. the code: every ${...} inside a template that holds HTML is read (tests/js/htmlcheck.mjs); text people write must go through
//      esc(), th(), html`` or a helper that escapes. A new unescaped one fails here, file by file.
//   2. the helpers in static/js/ui.js (escape, setText, html, raw) do what they say.
//   3. the real app, in headless Chrome: a world where every field people write holds <img src=x onerror=xss=N> (tests/js/xss_world.py)
//      is opened screen by screen. The payload must never become an element (the server's Content-Security-Policy would also stop the
//      onerror from running, but that is the second lock, not the first), window.xss must never be set, and the text must be on screen
//      as text. Skipped with a message when there is no Chrome or Python.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkAll, checkSource, jsFiles, ROOT } from './htmlcheck.mjs';
import { CHROME, launch, login } from '../layout/cdp.mjs';

// Findings allowed per file. E5's files are at zero; E4's (art.js, looks.js) are sanitised by hand there and wait for E4 to mark
// them (request in the log). A number here can only go down.
const ALLOWED = { 'art.js': 3, 'looks.js': 1 };

test('no text people write reaches HTML unescaped (file by file)', () => {
  const by = {};
  for (const f of checkAll()) (by[f.file] ||= []).push(f);
  const worse = Object.entries(by).filter(([file, list]) => list.length > (ALLOWED[file] || 0))
    .map(([file, list]) => `${file}: ${list.length} (allowed ${ALLOWED[file] || 0}) — ${list.slice(0, 3).map((f) => `l.${f.line} ${f.hits.join(',')}`).join('; ')}`);
  assert.deepEqual(worse, [], 'escape it: esc() / th() / html`` (static/js/ui.js), or mark the line "html: seguro (why)" after checking it');
});

test('the check catches an unescaped field and accepts the escaped ways', () => {
  const n = (src) => checkSource(src).length;
  assert.equal(n('el.innerHTML = `<h3>${m.question}</h3>`;'), 1);
  assert.equal(n('el.innerHTML = `<h3>${esc(m.question)}</h3>`;'), 0);
  assert.equal(n('el.innerHTML = `<h3>${th("Hola, {n}", { n: u.username })}</h3>`;'), 0);
  assert.equal(n('el.innerHTML = html`<h3>${m.question}</h3>`;'), 0);
  assert.equal(n('el.innerHTML = `<b title="${c.name}">x</b>`;'), 1);
  assert.equal(n('el.innerHTML = `<b>${r.punishment.text}</b>`;'), 1);
  assert.equal(n('el.innerHTML = `<i>${m.shares}</i><a href="#/u/${encodeURIComponent(u.username)}">${avatar(u.username)}</a>`;'), 0);
  assert.equal(n('el.innerHTML = `<b class="${m.question ? \'on\' : \'\'}">x</b>`;'), 0);
  assert.equal(n("el.innerHTML = '<b>' + msg.text + '</b>';"), 1);
  assert.equal(n('el.innerHTML = `<b>${m.question}</b>`; // html: seguro (a reason)'), 0);
  assert.equal(n('el.innerHTML = `<b>${m.question}</b>`; // html: seguro'), 1);        // the reason is required
});

test('the count of innerHTML is known (for the log)', () => {
  let count = 0;
  for (const p of jsFiles()) count += (readFileSync(p, 'utf8').match(/innerHTML\s*\+?=|insertAdjacentHTML\(/g) || []).length;
  assert.ok(count > 0);
  console.log(`innerHTML / insertAdjacentHTML in static/js: ${count}`);
});

test('ui.js helpers: escape, setText, html and raw', async () => {
  globalThis.document ||= { documentElement: { setAttribute() {} } };
  globalThis.localStorage ||= { getItem: () => null, setItem() {} };
  const ui = await import('../../static/js/ui.js');
  const evil = `<img src=x onerror="alert('x')">&`;
  assert.equal(ui.escape(evil), '&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt;&amp;');
  assert.equal(ui.html`<b>${evil}</b>`, `<b>${ui.escape(evil)}</b>`);
  assert.equal(ui.html`<p>${ui.raw('<i>built here</i>')}</p>`, '<p><i>built here</i></p>');
  assert.equal(ui.html`<ul>${['<a>', ui.raw('<li>ok</li>')]}</ul>`, '<ul>&lt;a&gt;<li>ok</li></ul>');
  assert.equal(ui.html`${null}${undefined}${0}`, '0');
  const el = { textContent: 'old' };
  ui.setText(el, evil);
  assert.equal(el.textContent, evil);
  ui.setText(el, null);
  assert.equal(el.textContent, '');
});

// ---------------------------------------------------------------- the real app, with poisoned data

const PY = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const hasPython = spawnSync(PY, ['--version']).status === 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test('in Chrome, HTML that people typed never runs', { skip: !CHROME ? 'no Chrome or Chromium found (set CHROME_BIN)' : !hasPython ? `no ${PY}` : false, timeout: 240000 }, async () => {
  const data = mkdtempSync(join(tmpdir(), 'clique-xss-'));
  const env = { ...process.env, DATA_DIR: data, EMAIL_REQUIRED: '0', PYTHONIOENCODING: 'utf-8' };
  const seeded = spawnSync(PY, ['-c', 'import sys, json; sys.path.insert(0, "tests/js"); from backend.store import store; store.load(); import xss_world; print(json.dumps(xss_world.seed())); store.save()'], { cwd: ROOT, env, encoding: 'utf8' });
  assert.equal(seeded.status, 0, seeded.stderr);
  const ids = JSON.parse(seeded.stdout.trim().split('\n').pop());
  const port = 3400 + Math.floor(Math.random() * 400);
  const server = spawn(PY, ['server.py'], { cwd: ROOT, env: { ...env, PORT: String(port) }, stdio: 'ignore' });
  const base = `http://127.0.0.1:${port}`;
  let page;
  try {
    for (let i = 0; i < 60; i++) { try { if ((await fetch(base + '/api/me')).status) break; } catch { /* starting */ } await sleep(250); }
    page = await launch({ scratch: data });
    await login(page, base, 'tester');
    await page.viewport(1366, 900);
    await page.goto(base + '/');
    // Each screen, and the payloads that must show there as plain text (proof the data was drawn, not left out).
    const SCREENS = [
      ['#/', [3]], [`#/market/${ids.market}`, [3, 4]], [`#/market/${ids.market}`, [6], '[data-t="comments"]'], [`#/market/${ids.multi}`, [5]], ['#/circles', [1]],
      [`#/circle/${ids.circle}`, [1, 3]], ['#/chat', [7, 8]], ['#/weekly', [9]], ['#/u/amy', [10]], ['#/friends', []], ['#/portfolio', [3]],
    ];
    const ran = [], missing = [];
    for (const [hash, shown, click] of SCREENS) {
      await page.hash(hash, 1500);
      if (click) { await page.eval(`document.querySelector(${JSON.stringify(click)})?.click()`); await sleep(600); }
      const r = await page.eval(`({ xss: window.xss, text: document.body.innerText,
        made: [...document.querySelectorAll('[onerror]')].map((e) => e.getAttribute('onerror')) })`);
      if (r.xss !== undefined) ran.push(`${hash}: payload ${r.xss} ran`);
      for (const m of r.made) ran.push(`${hash}: payload became an element (${m})`);
      for (const n of shown) if (!r.text.includes(`onerror=xss=${n}`)) missing.push(`${hash}: payload ${n} not shown as text`);
    }
    assert.deepEqual(ran, [], 'HTML typed by a person became markup on these screens (the number says which field: tests/js/xss_world.py)');
    assert.deepEqual(missing, [], 'the poisoned data should be on screen as plain text');
  } finally {
    try { await page?.close?.(); } catch { /* gone */ }
    server.kill();
    await sleep(300);
    try { rmSync(data, { recursive: true, force: true }); } catch { /* Windows keeps files a moment longer */ }
  }
});
