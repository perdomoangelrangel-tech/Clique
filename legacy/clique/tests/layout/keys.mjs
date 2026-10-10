// usage: node keys.mjs --out DIR [--base URL] [--user tester] [--pass testpass123] [--vp 1366x768,390x844]
// Keyboard only: Tab through a screen and check that whatever has focus is on screen and not hidden behind the pinned header or the call bar,
// then open a dialog from the keyboard, Tab around inside it, and close it with Escape.
import { mkdirSync } from 'node:fs';
import { launch, login } from './cdp.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const BASE = args.base || 'http://127.0.0.1:3005';
mkdirSync(args.out || '.', { recursive: true });
const VPS = (args.vp || '1366x768,390x844').split(',').map((s) => s.split('x').map(Number));
const page = await launch({ scratch: args.out });
const problems = [];
const note = (at, msg) => { problems.push(`[${at}] ${msg}`); console.log(`[${at}] ${msg}`); };
const key = async (k, code, vk, shift = false) => {
  const mods = shift ? 8 : 0;
  // Enter needs the character too (as a real keyboard sends it), or a focused button is never "clicked"
  await page.send('Input.dispatchKeyEvent', k === 'Enter' ? { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, modifiers: mods, text: '\r' } : { type: 'rawKeyDown', key: k, code, windowsVirtualKeyCode: vk, modifiers: mods });
  await page.send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk, modifiers: mods });
  await page.sleep(60);
};
const tab = (shift) => key('Tab', 'Tab', 9, shift);
const focused = `(() => { const e = document.activeElement; if (!e || e === document.body) return null; const r = e.getBoundingClientRect(); const vw = innerWidth, vh = innerHeight;
  const cx = Math.min(Math.max(r.left + r.width / 2, 1), vw - 1), cy = Math.min(Math.max(r.top + r.height / 2, 1), vh - 1); const top = document.elementFromPoint(cx, cy);
  const dock = document.getElementById('voice-dock'); const name = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + String(e.className).trim().split(/\\s+/)[0] + ' "' + (e.getAttribute('aria-label') || e.textContent || e.value || '').trim().slice(0, 18) + '"';
  const drawn = (n) => { const c = getComputedStyle(n); return c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0 || c.boxShadow !== 'none'; };
  let ring = drawn(e); for (let n = e.parentElement, d = 0; !ring && n && d < 3; n = n.parentElement, d++) ring = n.matches(':focus-within') && drawn(n);
  return { name, inside: r.width > 0 && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw, covered: !!top && !(e === top || e.contains(top) || top.contains(e)) ? (top.tagName.toLowerCase() + '.' + String(top.className).slice(0, 28)) : '', ring, hiddenByScroller: !!e.closest('.strip') && r.right > vw }; })()`;
try {
  await login(page, BASE, args.user || 'tester', args.pass || 'testpass123');
  await page.viewport(1366, 768);
  await page.goto(BASE + '/', { settle: 700 });
  for (const [w, h] of VPS) {
    await page.viewport(w, h);
    for (const route of ['/', '/games/mines', '/friends', '/store']) {
      await page.hash('#' + route, 900);
      await page.eval(`document.getElementById('toasts').replaceChildren(); window.scrollTo(0, 0); document.activeElement && document.activeElement.blur(); true`);
      let steps = 0, seen = new Set();
      for (let i = 0; i < 70; i++) {
        await tab(); steps++;
        const f = await page.eval(focused);
        if (!f) continue;
        seen.add(f.name);
        const at = `${w}x${h} ${route} tab ${i + 1}`;
        if (!f.inside) note(at, `${f.name} has focus but is not on screen`);
        else if (f.covered && /top-bar|top-rest|vdock|toast|modal/.test(f.covered)) note(at, `${f.name} has focus but is covered by ${f.covered}`);
        if (!f.ring) note(at, `${f.name} has focus but shows no focus ring`);
      }
      if (seen.size < 12) note(`${w}x${h} ${route}`, `only ${seen.size} different things could be reached with Tab`);
    }
    // a dialog from the keyboard
    await page.hash('#/', 900);
    await page.eval(`document.getElementById('btn-deposit').focus(); true`);
    await key('Enter', 'Enter', 13);
    await page.sleep(400);
    const open = await page.eval(`!!document.querySelector('#modal-root .modal')`);
    if (!open) note(`${w}x${h} dialog`, 'Enter on "Add funds" did not open the dialog');
    else {
      const inside = new Set();
      for (let i = 0; i < 12; i++) { await tab(); inside.add(await page.eval(`document.activeElement && !!document.activeElement.closest('#modal-root .modal')`)); }
      if (inside.has(false)) note(`${w}x${h} dialog`, 'Tab left the dialog while it was open (focus went to the page behind it)');
      await key('Escape', 'Escape', 27);
      await page.sleep(300);
      if (await page.eval(`!!document.querySelector('#modal-root .modal')`)) note(`${w}x${h} dialog`, 'Escape did not close the dialog');
    }
  }
  console.log(problems.length ? `\n${problems.length} problems` : '\nkeyboard focus stayed visible and uncovered everywhere');
  process.exitCode = problems.length ? 1 : 0;
} finally { await page.close(); }
