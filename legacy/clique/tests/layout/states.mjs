// usage: node states.mjs --out DIR [--vp 1366x768,...] [--zoom 1] [--only name,name] [--shots] [--base URL] [--user tester] [--pass testpass123]
// Exit code 1 when any state has a problem.
// Interactive states: menus, pop-overs, dialogs, and every casino game in the middle of a round. Checks that things stay on screen and
// reachable, and that RESIZING (and zooming) in the middle of a round neither restarts it nor places another bet.
import { mkdirSync, writeFileSync } from 'node:fs';
import { launch, login } from './cdp.mjs';
import { MEASURE, problems } from './measure.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const BASE = args.base || 'http://127.0.0.1:3005';
const OUT = args.out; mkdirSync(OUT, { recursive: true });
const VPS = (args.vp || '1024x600,1366x768,1536x864,1920x1080,320x640,390x844,768x1024').split(',').map((s) => s.split('x').map(Number));
const ZOOM = Number(args.zoom || 1);
const only = args.only ? String(args.only).split(',') : null;
const page = await launch({ port: Number(args.port || 9335), scratch: process.env.SCRATCH || OUT });
console.log('engine:', page.version, '| zoom', ZOOM);

const posts = [];                       // every request that could place a bet, so a resize that repeats one is caught
page.send('Network.enable').catch(() => {});
page.on((m) => { if (m.method === 'Network.requestWillBeSent' && m.params.request.method === 'POST') posts.push(m.params.request.url.replace(BASE, '')); });

const J = JSON.stringify;
const click = (sel) => page.eval(`(() => { const e = document.querySelector(${J(sel)}); if (!e) return 'missing'; e.scrollIntoView({block: 'center'}); e.click(); return 'ok'; })()`);
const exists = (sel) => page.eval(`!!document.querySelector(${J(sel)})`);
const wait = (ms) => page.sleep(ms);
const set = (sel, v) => page.eval(`(() => { const e = document.querySelector(${J(sel)}); e.value = ${J(v)}; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); })()`);
const vpSet = async (w, h) => (ZOOM === 1 ? page.viewport(w, h) : page.zoomed(w, h, ZOOM));

// is this control really reachable? scrolled into view, inside the window, and nothing (a sticky bar, a banner) sitting on top of it
const reach = (sels) => page.eval(`(() => {
  document.querySelectorAll('.gm-pop').forEach((p) => p.remove());
  const bad = [];
  for (const sel of ${J(sels)}) for (const e of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || e.disabled) continue;
    e.scrollIntoView({ block: 'center', inline: 'center' });
    const r = e.getBoundingClientRect(), vw = innerWidth, vh = innerHeight;
    if (r.width < 1) continue;
    const cx = Math.min(Math.max(r.left + r.width / 2, 1), vw - 1), cy = Math.min(Math.max(r.top + r.height / 2, 1), vh - 1);
    const top = document.elementFromPoint(cx, cy);
    const label = sel + ' "' + (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 20) + '"';
    if (r.left < -1 || r.right > vw + 1 || r.top < -1 || r.bottom > vh + 1) bad.push(label + ' is outside the window after scrolling to it');
    else if (top && !(e === top || e.contains(top) || top.contains(e))) bad.push(label + ' is covered by ' + top.tagName.toLowerCase() + '.' + String(top.className).slice(0, 30));
    if (r.height < 28 && !e.matches('input[type=range], input[type=radio], input[type=checkbox], .bp-input button, .rc, .dc-slider') && !e.closest('.bp-input, .gm-input, .gm-ro')) bad.push(label + ' is only ' + Math.round(r.height) + 'px tall (hard to hit)');
  }
  return bad;
})()`);

const gameState = () => page.eval(`fetch('/api/games/state').then((r) => r.json()).then((j) => JSON.stringify(j))`);
const BET = /\/api\/games\/[a-z]+\/(bet|deal|start|play|new|spin|roll|flip|toss|round|go)\b|\/api\/games\/(dice|limbo|coinflip|wheel|war|roulette)\b|\/api\/poker/;

async function check(name, vp, extra = []) {
  const rep = await page.eval(MEASURE);
  const p = problems(rep).filter((x) => !/^pinned header/.test(x) || rep.stuckH > rep.vh * 0.45);
  const bad = await reach(extra);
  return [...p, ...bad.map((b) => 'reach: ' + b)];
}

const out = [];
let failures = 0;
async function scenario(name, fn) {
  if (only && !only.includes(name)) return;
  for (const [w, h] of VPS) {
    const label = ZOOM === 1 ? `${w}x${h}` : `${w}x${h}@${Math.round(ZOOM * 100)}%`;
    try {
      await vpSet(w, h);
      const probs = await fn(w, h, label);
      out.push({ scenario: name, vp: label, problems: probs });
      if (probs.length) { failures++; console.log(`\n[${label}] ${name}\n  - ` + probs.join('\n  - ')); }
      if (args.shots) await page.shot(`${OUT}/${name}-${label}.png`);
    } catch (e) { failures++; console.log(`\n[${label}] ${name}: ERROR ${e.message}`); out.push({ scenario: name, vp: label, problems: ['error: ' + e.message] }); }
    try { await page.eval(`document.querySelectorAll('#modal-root .modal-back').forEach((b) => b.remove()); document.getElementById('user-menu')?.classList.add('hidden'); true`); } catch { await page.goto(BASE + '/', { settle: 900 }); }
  }
}
const go = async (path, settle = 1100) => { await page.hash('#/__elsewhere__', 150); await page.hash('#' + path, settle); };       // always a fresh mount, never a leftover from the last viewport

try {
  await login(page, BASE, args.user || 'tester', args.pass || 'testpass123');
  await vpSet(1366, 768);
  await page.goto(BASE + '/', { settle: 900 });

  // ------------------------------------------------------------------ menus and dialogs
  await scenario('menu-account', async () => {
    await go('/');
    await page.eval(`window.scrollTo(0, 0)`);
    await click('#btn-avatar'); await wait(250);
    const r = await page.eval(`(() => { const m = document.getElementById('user-menu'); const b = m.getBoundingClientRect(); const items = [...m.querySelectorAll('a, button')]; const cut = items.filter((e) => { const r = e.getBoundingClientRect(); return r.right > innerWidth + 1 || r.left < -1; }).length; return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, vw: innerWidth, vh: innerHeight, scrolls: m.scrollHeight > m.clientHeight + 1, ov: getComputedStyle(m).overflowY, n: items.length, cut }; })()`);
    const p = [];
    if (r.left < -1 || r.right > r.vw + 1) p.push(`menu sideways off screen (${Math.round(r.left)}..${Math.round(r.right)} of ${r.vw})`);
    if (r.bottom > r.vh + 1 && !(r.scrolls || r.ov === 'auto')) p.push(`menu runs off the bottom (${Math.round(r.bottom)} of ${r.vh}) and cannot scroll`);
    if (r.bottom > r.vh + 1) p.push(`menu bottom ${Math.round(r.bottom)} beyond ${r.vh}`);
    if (r.cut) p.push(`${r.cut} menu items cut sideways`);
    return p;
  });
  await scenario('modal-deposit', async () => {
    await go('/'); await click('#btn-deposit'); await wait(350);
    const m = await page.eval(`(() => { const m = document.querySelector('#modal-root .modal'); if (!m) return null; const r = m.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, vw: innerWidth, vh: innerHeight, tall: !!document.querySelector('.modal-back.tall') }; })()`);
    if (!m) return ['dialog did not open'];
    const p = [];
    if (m.left < 0 || m.right > m.vw + 1) p.push('dialog sideways off screen');
    const bad = await reach(['.modal .btn', '.modal input', '.modal select', '.modal [data-close]']);
    return [...p, ...bad.map((b) => 'reach: ' + b)];
  });
  await scenario('popover-markets', async () => {
    await go('/'); await page.eval(`document.querySelectorAll('.pop-menu').forEach((m) => m.classList.add('hidden'))`); await wait(300);
    const ids = await page.eval(`[...document.querySelectorAll('.all-icons .icon-btn')].map((b) => b.id)`);
    const sort = ids.find((i) => /sort|filter/i.test(i)) || ids[1];
    if (!sort) return ['no pop-over trigger found'];
    await click('#' + sort); await wait(250);
    const r = await page.eval(`(() => { const m = document.querySelector('.pop-menu:not(.hidden)'); if (!m) return null; const b = m.getBoundingClientRect(); return { left: b.left, right: b.right, bottom: b.bottom, vw: innerWidth, vh: innerHeight, scrolls: m.scrollHeight > m.clientHeight + 1 }; })()`);
    if (!r) return ['pop-over did not open'];
    const p = [];
    if (r.left < -1 || r.right > r.vw + 1) p.push(`pop-over off screen sideways (${Math.round(r.left)}..${Math.round(r.right)} of ${r.vw})`);
    if (r.bottom > r.vh + 1 && !r.scrolls) p.push(`pop-over bottom ${Math.round(r.bottom)} beyond ${r.vh}`);
    return p;
  });

  // ------------------------------------------------------------------ casino: a round in progress, then the window changes shape
  const SERIES = [[1024, 600], [390, 844], [1366, 768], [320, 640], [1920, 1080]];
  async function inRound(name, route, start, reachSels) {
    await scenario(name, async (w, h) => {
      await go(route, 1300);
      const before = await gameState();
      const ok = await start();
      await wait(1100);
      const p = [];
      if (ok !== true) { return [`could not start the round: ${ok}`]; }
      const roundState = await gameState();
      posts.length = 0;
      p.push(...(await check(name, [w, h], reachSels)));
      // reshape the window in the middle of the round
      for (const [sw, sh] of SERIES) { await vpSet(sw, sh); await wait(450); }
      await vpSet(w, h); await wait(450);
      const after = await gameState();
      const repeated = posts.filter((u) => BET.test(u));
      if (repeated.length) p.push('resizing sent requests to the game: ' + repeated.join(', '));
      if (roundState !== after) p.push('the round changed while only the window was resized');
      p.push(...(await check(name + ' (after resize)', [w, h], reachSels)).map((x) => 'after resize: ' + x));
      return p;
    });
  }
  const startBtn = (sel, then) => async () => { if ((await click(sel)) !== 'ok') return 'start button missing: ' + sel; await wait(900); if (then) { const r = await then(); if (r !== true) return r; } return true; };
  const clickFirst = (sel) => async () => { await wait(300); return (await click(sel)) === 'ok' ? true : 'missing ' + sel; };

  await inRound('round-mines', '/games/mines', startBtn('#go', clickFirst('#grid .mn-tile')), ['#go', '#cash', '#grid .mn-tile:not(:disabled)', '#bp-amt']);
  await inRound('round-tower', '/games/tower', startBtn('#go'), ['#cash', '.tw-row.now .tw-tile:not(:disabled)', '#bp-amt']);
  await inRound('round-chicken', '/games/chicken', startBtn('#play', clickFirst('#step')), ['#step', '#cash', '#bp-amt']);
  await inRound('round-blackjack', '/games/blackjack', startBtn('#deal'), ['#actions button', '#bp-amt']);
  await inRound('round-hilo', '/games/hilo', startBtn('#play'), ['#higher', '#lower', '#cash', '#skip']);
  await inRound('round-moles', '/games/moles', startBtn('#go'), ['#cash', '#field .ml-hole', '#bp-amt']);
  await inRound('round-rps', '/games/rps', startBtn('#play'), ['#choices button', '#cash']);
  await inRound('after-roll-dice', '/games/dice', startBtn('#go'), ['#go', '#slider', '#bp-amt']);
  await inRound('after-roll-limbo', '/games/limbo', startBtn('#go'), ['#go', '#target', '#bp-amt']);
  await inRound('after-flip-coinflip', '/games/coinflip', startBtn('#go'), ['#go', '#bp-amt']);
  await inRound('after-spin-wheel', '/games/wheel', startBtn('#spin'), ['#spin', '#bp-amt']);
  await inRound('after-deal-war', '/games/war', startBtn('#go'), ['#go', '#bp-amt']);
  await inRound('after-spin-roulette', '/games/roulette', async () => { if ((await click('#table .rc:not(.out)')) !== 'ok') return 'no cell'; await wait(300); if ((await click('#go')) !== 'ok') return 'no spin button'; await wait(2500); return true; }, ['#go', '#clear', '.rchip', '.rl-side']);
} finally {
  writeFileSync(`${OUT}/states-${ZOOM}.json`, JSON.stringify(out, null, 1));
  console.log(`\n${out.length} states checked, ${failures} with problems`);
  process.exitCode = failures ? 1 : 0;
  await page.close();
}
