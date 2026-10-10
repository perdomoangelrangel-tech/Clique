// usage: node voice.mjs --out DIR [--base URL] [--user tester] [--pass testpass123] [--vp 1366x768,390x844]
// Joins a circle's voice room with a fake microphone, then walks through the site at different sizes with the call up. Checks that the call bar
// stays, that the page makes room for it (nothing is hidden under it), that notices and pinned bars sit above it, and that leaving removes it.
import { mkdirSync } from 'node:fs';
import { launch, login } from './cdp.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const BASE = args.base || 'http://127.0.0.1:3005';
mkdirSync(args.out || '.', { recursive: true });
const VPS = (args.vp || '1366x768,390x844').split(',').map((s) => s.split('x').map(Number));
const page = await launch({ scratch: args.out, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] });
const problems = [];
const note = (vp, msg) => { problems.push(`[${vp}] ${msg}`); console.log(`[${vp}] ${msg}`); };
try {
  await login(page, BASE, args.user || 'tester', args.pass || 'testpass123');
  await page.viewport(1366, 768);
  await page.goto(BASE + '/', { settle: 700 });
  const circle = await page.eval(`fetch('/api/circles').then((r) => r.json()).then((j) => j.mine[0].id)`);
  await page.hash('#/circle/' + circle, 1500);
  const joined = await page.eval(`(async () => { const b = document.querySelector('#vc-join'); if (!b) return 'no join button'; b.click(); for (let i = 0; i < 40; i++) { await new Promise((r) => setTimeout(r, 250)); const d = document.getElementById('voice-dock'); if (d && !d.hidden && d.querySelector('[data-a="leave"]')) return 'in the call'; } return 'dock never appeared'; })()`);
  if (joined !== 'in the call') note('start', 'could not join the call: ' + joined);
  else {
    for (const [w, h] of VPS) {
      const vp = `${w}x${h}`;
      await page.viewport(w, h);
      for (const route of ['/', '/games/mines', '/poker', '/chat', '/friends', '/store']) {
        await page.hash('#' + route, 900);
        const r = await page.eval(`(async () => {
          const d = document.getElementById('voice-dock'), root = getComputedStyle(document.documentElement);
          const dock = d.getBoundingClientRect(), vh = innerHeight;
          window.scrollTo(0, document.documentElement.scrollHeight); await new Promise((r) => setTimeout(r, 200));
          const page = document.querySelector('#view .page, #view > *:last-child');
          const last = page ? page.getBoundingClientRect().bottom : 0;
          toast: { const t = document.createElement('div'); t.className = 'toast'; t.textContent = 'a notice'; document.getElementById('toasts').appendChild(t); await new Promise((r) => setTimeout(r, 50)); var toastBottom = t.getBoundingClientRect().bottom; t.remove(); }
          return { hidden: d.hidden, dockH: Math.round(dock.height), dockTop: Math.round(dock.top), cssDock: parseFloat(root.getPropertyValue('--dock-h')), bodyPad: parseFloat(getComputedStyle(document.body).paddingBottom), lastBottom: Math.round(last), toastBottom: Math.round(toastBottom), vh, overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth, call: !!d.querySelector('[data-a="leave"]') };
        })()`);
        const at = `${vp} ${route}`;
        if (r.hidden || !r.call) note(at, 'the call bar went away when the screen changed');
        if (Math.abs(r.cssDock - r.dockH) > 2) note(at, `--dock-h is ${r.cssDock}px but the bar is ${r.dockH}px tall`);
        if (Math.abs(r.bodyPad - r.dockH) > 2) note(at, `the page leaves ${r.bodyPad}px at the bottom but the bar is ${r.dockH}px tall`);
        if (r.lastBottom > r.dockTop + 2) note(at, `the end of the page (${r.lastBottom}px) is under the call bar (top at ${r.dockTop}px)`);
        if (r.toastBottom > r.dockTop + 1) note(at, `a notice (${r.toastBottom}px) would sit on top of the call bar (top at ${r.dockTop}px)`);
        if (r.overflowX > 1) note(at, `the page scrolls sideways by ${r.overflowX}px with the call bar up`);
      }
    }
    const left = await page.eval(`(async () => { document.querySelector('#voice-dock [data-a="leave"]').click(); for (let i = 0; i < 20; i++) { await new Promise((r) => setTimeout(r, 200)); if (document.getElementById('voice-dock').hidden) return true; } return false; })()`);
    if (!left) note('end', 'leaving the call did not remove the bar');
    const after = await page.eval(`parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dock-h'))`);
    if (after !== 0) note('end', `--dock-h is ${after}px after leaving`);
  }
  console.log(problems.length ? `\n${problems.length} problems` : '\nthe call bar behaved on every screen');
  process.exitCode = problems.length ? 1 : 0;
} finally { await page.close(); }
