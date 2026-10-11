// usage: node bet.mjs --out DIR [--base http://127.0.0.1:3005] [--user tester] [--vp 1366x768,390x844]
// Exit code 1 when any problem is found.
// The bet button of every casino game (and the button that opens a poker table) must be on screen the moment the game opens, without
// scrolling: fully inside the window, above the phone bar and the call bar, and not covered by anything. In the casino the market search
// and the price ticker must be gone (R3), and the phone bar along the bottom has five places at most (F2).
import { mkdirSync, writeFileSync } from 'node:fs';
import { launch, login } from './cdp.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const BASE = args.base || 'http://127.0.0.1:3005';
const OUT = args.out; mkdirSync(OUT, { recursive: true });
const VPS = (args.vp || '1366x768,390x844').split(',').map((s) => s.split('x').map(Number));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const GAMES = ['chicken', 'blackjack', 'roulette', 'limbo', 'coinflip', 'war', 'dice', 'mines', 'moles', 'tower', 'hilo', 'wheel', 'rps'];
const SCREENS = [...GAMES.map((g) => [g, `#/games/${g}`, '.btn-bet']), ['poker', '#/poker', '#pk-new']];

const CHECK = (sel) => `(() => {
  scrollTo(0, 0);
  const cs = getComputedStyle(document.documentElement);
  const nav = parseFloat(cs.getPropertyValue('--nav-h')) || 0, dock = parseFloat(cs.getPropertyValue('--dock-h')) || 0;
  const room = innerHeight - Math.max(nav, dock);
  const out = [];
  const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find((e) => e.getClientRects().length);
  if (!b) out.push('no bet button on screen');
  else {
    const r = b.getBoundingClientRect();
    if (r.top < 0 || r.bottom > room + 0.5) out.push('bet button at ' + Math.round(r.top) + '-' + Math.round(r.bottom) + 'px, the room ends at ' + Math.round(room) + 'px (' + Math.ceil(r.bottom - room) + 'px short)');
    else {
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (!hit || !(hit === b || b.contains(hit))) out.push('bet button covered by ' + (hit ? hit.tagName.toLowerCase() + '.' + [...hit.classList].join('.') : 'nothing'));
    }
  }
  const shown = (el) => el && el.getClientRects().length > 0;
  if (shown(document.getElementById('ticker'))) out.push('the price ticker is showing in the casino');
  for (const s of document.querySelectorAll('.top-right .search, .search-mobile')) if (shown(s)) out.push('the market search is showing in the casino');
  const tabs = document.querySelectorAll('#tabbar .tab');
  if (tabs.length > 5) out.push('the phone bar has ' + tabs.length + ' places (five at most)');
  return out;
})()`;

const page = await launch({ port: Number(args.port || 9336), scratch: process.env.SCRATCH || OUT });
const problems = [];
try {
  await login(page, BASE, args.user || 'tester', args.pass || 'testpass123');
  for (const [w, h] of VPS) {
    const phone = w <= 720;
    await page.viewport(w, h, phone ? 3 : 1, phone);
    await page.goto(BASE + '/#/games', { settle: 300 });
    await page.eval('location.reload()');
    await sleep(2500);
    for (const [name, hash, sel] of SCREENS) {
      await page.hash(hash, 1400);
      for (const p of await page.eval(CHECK(sel))) problems.push(`${w}x${h} ${name}: ${p}`);
    }
  }
} finally { await page.close(); }

writeFileSync(`${OUT}/bet.json`, JSON.stringify(problems, null, 1));
for (const p of problems) console.log(p);
console.log(problems.length ? `${problems.length} problems` : 'every bet button is on screen');
process.exit(problems.length ? 1 : 0);
