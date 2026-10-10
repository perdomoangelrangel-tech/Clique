// usage: node audit.mjs --out DIR [--user tester] [--pass testpass123] [--base http://127.0.0.1:3005] [--vp 1024x600,1366x768] [--zoom 1.25] [--routes all|a,b] [--shots] [--focus .selector]
// Exit code 1 when any screen has a problem.
// Logs in, visits every route at every viewport, runs the in-page audit, prints a compact table of problems, saves a JSON report.
import { mkdirSync, writeFileSync } from 'node:fs';
import { launch, login } from './cdp.mjs';
import { MEASURE, problems } from './measure.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const BASE = args.base || 'http://127.0.0.1:3005';
const OUT = args.out; mkdirSync(OUT, { recursive: true });
const SCRATCH = process.env.SCRATCH || OUT;
const VPS = (args.vp || '1024x600,1280x720,1366x768,1440x900,1536x864,1920x1080,320x640,360x740,375x812,390x844,768x1024').split(',').map((s) => s.split('x').map(Number));
const ZOOM = Number(args.zoom || 1);
const USER = args.user || 'tester';

const GAMES = ['chicken', 'blackjack', 'roulette', 'limbo', 'coinflip', 'war', 'dice', 'mines', 'moles', 'tower', 'hilo', 'wheel', 'rps'];
const page = await launch({ port: Number(args.port || 9333), scratch: SCRATCH });
console.log('engine:', page.version, '| zoom', ZOOM);
try {
  await login(page, BASE, USER, args.pass || 'testpass123');
  await page.viewport(1366, 768);
  await page.goto(BASE + '/');
  const ids = await page.eval(`(async () => {
    const j = (u) => fetch(u).then((r) => r.json());
    const ms = (await j('/api/markets?status=open&sort=trending')).markets || [];
    const cs = (await j('/api/circles')).mine || [];
    const pk = ((await j('/api/poker/tables')).tables || []).map((t) => t.id);
    const ch = ((await j('/api/chats')).chats || []).map((c) => c.id);
    return { markets: ms.map((m) => m.id), circles: cs.map((c) => c.id), poker: pk, chats: ch };
  })()`);
  const routes = [['markets', '/'], ['market', '/market/' + ids.markets[0]], ['market-12', '/market/' + (ids.markets[2] || ids.markets[0])], ['create', '/create'],
    ['circles', '/circles'], ['circle', '/circle/' + ids.circles[0]], ['circle-long', '/circle/' + (ids.circles[1] || ids.circles[0])], ['weekly', '/weekly'],
    ['games', '/games'], ...GAMES.map((g) => ['game-' + g, '/games/' + g]),
    ['friends', '/friends'], ['chat', '/chat/global'], ...ids.chats.filter((c) => c !== 'global' && !c.startsWith('circle_')).slice(0, 2).map((c, i) => ['chat-' + (c.startsWith('dm_') ? 'dm' : 'group'), '/chat/' + c]), ['poker', '/poker'], ...(ids.poker[0] ? [['poker-table', '/poker/' + ids.poker[0]]] : []), ['profile', '/u/' + USER], ['profile-edit', '/u/' + USER + '/edit'], ['portfolio', '/portfolio'],
    ['exchange', '/exchange'], ['exchange-co', '/exchange/NEXO'], ['store', '/store'], ['statement', '/statement'],
    ['challenges', '/challenges'], ['progress', '/progress'], ['loans', '/loans'], ['transfers', '/transfers'], ['ranking', '/ranking']];
  const want = args.routes && args.routes !== 'all' ? String(args.routes).split(',') : null;
  const report = [];
  for (const [w, h] of VPS) {
    const label = ZOOM === 1 ? `${w}x${h}` : `${w}x${h}@${Math.round(ZOOM * 100)}%`;
    if (ZOOM === 1) await page.viewport(w, h); else await page.zoomed(w, h, ZOOM);
    for (const [name, path] of routes) {
      if (want && !want.includes(name)) continue;
      try {
        await page.hash('#' + path, 1100);
        const rep = await page.eval(MEASURE);
        const p = problems(rep);
        report.push({ vp: label, route: name, rep, problems: p });
        if (args.focus) await page.eval(`(() => { const e = document.querySelector(${JSON.stringify(args.focus)}); if (!e) return; const h = document.querySelector('.top-sticky'); const hb = h ? h.getBoundingClientRect().bottom : 0; window.scrollTo(0, window.scrollY + e.getBoundingClientRect().top - hb - 6); })()`);
        if (args.shots) { await page.sleep(150); await page.shot(`${OUT}/${name}-${label}.png`); }
        if (p.length) console.log(`\n[${label}] ${name}\n  - ` + p.join('\n  - '));
      } catch (e) { console.log(`\n[${label}] ${name}: AUDIT ERROR ${e.message}`); report.push({ vp: label, route: name, rep: {}, problems: ['audit error: ' + e.message] }); }
    }
  }
  writeFileSync(`${OUT}/report-${ZOOM}.json`, JSON.stringify(report, null, 1));
  const bad = report.filter((r) => r.problems.length);
  console.log(`\n${report.length} screens checked, ${bad.length} with problems`);
  process.exitCode = bad.length ? 1 : 0;
} finally { await page.close(); }
