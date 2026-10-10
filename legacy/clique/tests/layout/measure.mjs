// The in-page layout audit. Returns a JSON-able report: page overflow, elements poking outside the viewport that nothing clips,
// controls that are cut off by a clipping ancestor or sit outside the viewport, text cut off without an ellipsis, and how much of the
// screen the sticky header takes. Intentional things are skipped (marquee ticker, off-screen sprite, visually hidden helpers).
export const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight, root0 = document.documentElement;
  const de = document.documentElement;
  const q = (e) => {
    let s = e.tagName.toLowerCase();
    if (!e.id && !(typeof e.className === 'string' && e.className.trim()) && e.parentElement) s = (e.parentElement.id ? '#' + e.parentElement.id : '.' + String(e.parentElement.className).trim().split(/\\s+/)[0]) + ' > ' + s;
    if (e.id) s += '#' + e.id;
    const c = typeof e.className === 'string' ? e.className.trim().split(/\\s+/).slice(0, 3).join('.') : '';
    if (c) s += '.' + c;
    const t = (e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 24);
    return s + (t ? ' "' + t + '"' : '');
  };
  const skip = (e) => !!e.closest('.ticker, [aria-hidden="true"], svg[width="1"], #toasts, .sr-only, .vh, [hidden]');
  const visible = (e) => { const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false; const cs = getComputedStyle(e); return cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0'; };
  const clips = (cs, axis) => { const o = axis === 'x' ? cs.overflowX : cs.overflowY; return o === 'hidden' || o === 'clip' || o === 'auto' || o === 'scroll'; };
  const out = { vw, vh, pageScrollW: de.scrollWidth, pageScrollH: de.scrollHeight, bodyScrollW: document.body.scrollWidth, overflowX: de.scrollWidth - vw };
  const hb = document.querySelector('.top-bar'), hr = document.querySelector('.top-rest');
  out.headerH = Math.round((hb ? hb.getBoundingClientRect().height : 0) + (hr ? hr.getBoundingClientRect().height : 0));
  out.headerShare = +(out.headerH / vh).toFixed(2);
  // pinned things: a sticky panel is only a problem when it cannot be seen whole while pinned (its bottom would be out of reach)
  const sticky = [...document.querySelectorAll('#app *')].filter((e) => getComputedStyle(e).position === 'sticky' && visible(e) && !skip(e));
  out.stuck = sticky.map((e) => { const cs = getComputedStyle(e); return q(e) + ' top:' + cs.top + ' h:' + Math.round(e.getBoundingClientRect().height); }).slice(0, 8);
  out.stuckH = Math.round(sticky.filter((e) => ['top-bar', 'top-rest'].some((c) => e.classList.contains(c))).reduce((n, e) => n + e.getBoundingClientRect().height, 0));
  out.tallPinned = sticky.filter((e) => { const t = parseFloat(getComputedStyle(e).top); return Number.isFinite(t) && t + e.getBoundingClientRect().height > vh + 1; }).map((e) => q(e) + ' needs ' + Math.round(parseFloat(getComputedStyle(e).top) + e.getBoundingClientRect().height) + 'px of ' + vh);

  const all = [...document.querySelectorAll('#app *, #modal-root *, #voice-dock *')].filter((e) => !skip(e) && visible(e));
  const poke = [], cut = [], trunc = [], off = [];
  for (const e of all) {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    // 1. pokes out of the viewport and no ancestor clips it inside the viewport
    if (r.right > vw + 1.5 || r.left < -1.5) {
      let held = false, a = e.parentElement;
      while (a && a !== document.body && a !== de) {
        const ac = getComputedStyle(a); const ar = a.getBoundingClientRect();
        if (clips(ac, 'x') && ar.right <= vw + 1.5 && ar.left >= -1.5) { held = true; break; }
        if (ac.position === 'fixed' && ac.display !== 'none') break;
        a = a.parentElement;
      }
      if (!held && cs.position !== 'fixed') poke.push({ el: q(e), left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width) });
    }
    // 2. interactive control cut off by an ancestor that hides overflow, or sitting outside the viewport entirely
    if (e.matches('button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [tabindex="0"]')) {
      let a = e.parentElement, reason = '';
      while (a && a !== document.body && a !== de) {
        const ac = getComputedStyle(a);
        if (ac.overflowX === 'hidden' || ac.overflowX === 'clip' || ac.overflowY === 'hidden' || ac.overflowY === 'clip') {
          const ar = a.getBoundingClientRect();
          if (ac.overflowX !== 'visible' && (r.right > ar.right + 2 || r.left < ar.left - 2)) { reason = 'cut sideways by ' + q(a); break; }
          if (ac.overflowY !== 'visible' && (r.bottom > ar.bottom + 2 || r.top < ar.top - 2) && ar.height > 0) { reason = 'cut vertically by ' + q(a); break; }
        }
        a = a.parentElement;
      }
      if (reason) cut.push({ el: q(e), reason });
      if (!reason && cs.position !== 'fixed' && (r.right > vw + 1.5 || r.left < -1.5)) {
        let inScroller = false; a = e.parentElement;
        while (a && a !== document.body && a !== de) { const ac = getComputedStyle(a); if ((ac.overflowX === 'auto' || ac.overflowX === 'scroll') && a.getBoundingClientRect().right <= vw + 1.5) { inScroller = true; break; } a = a.parentElement; }
        if (!inScroller) off.push({ el: q(e), left: Math.round(r.left), right: Math.round(r.right) });
      }
    }
    // 3. text cut off by overflow:hidden without an ellipsis
    if ((cs.overflowX === 'hidden' || cs.overflowY === 'hidden') && e.children.length === 0 && (e.textContent || '').trim()) {
      const hx = e.scrollWidth - e.clientWidth > 2 && cs.overflowX === 'hidden' && cs.textOverflow !== 'ellipsis';
      const hy = e.scrollHeight - e.clientHeight > 2 && cs.overflowY === 'hidden';
      const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
      if ((hx || hy) && !clamp && !e.classList.contains('rl')) trunc.push({ el: q(e), sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight });
    }
  }
  // block containers that hide overflow and are cutting off real content
  const boxes = [];
  for (const e of document.querySelectorAll('#app *, #modal-root *')) {
    if (skip(e) || !visible(e) || e.closest('.ck-stage, .gm-pop, .rl') || (!e.id && !(typeof e.className === 'string' && e.className.trim()))) continue;           // (the rolling-number window and the result ticket clip on purpose)           // (the chicken road is a window onto a longer road that slides: clipped on purpose)
    const cs = getComputedStyle(e);
    if ((cs.overflowY === 'hidden' || cs.overflowX === 'hidden') && e.children.length && cs.textOverflow !== 'ellipsis') {
      const dx = e.scrollWidth - e.clientWidth, dy = e.scrollHeight - e.clientHeight;
      if ((dx > 3 && cs.overflowX === 'hidden') || (dy > 3 && cs.overflowY === 'hidden')) boxes.push({ el: q(e), dx, dy, w: e.clientWidth, h: e.clientHeight });
    }
  }
  const uniq = (arr, k) => { const seen = new Set(); return arr.filter((x) => { const key = k(x); if (seen.has(key)) return false; seen.add(key); return true; }); };
  out.poke = uniq(poke, (x) => x.el).slice(0, 12);
  out.cutControls = uniq(cut, (x) => x.el + x.reason).slice(0, 12);
  out.offControls = uniq(off, (x) => x.el).slice(0, 12);
  out.truncated = uniq(trunc, (x) => x.el).slice(0, 12);
  out.hiddenOverflow = uniq(boxes, (x) => x.el).slice(0, 12);
  // a casino card (title, table or board, bet controls) should be whole on one screen when the room allows it: that is the point of sizing boards from the visible height
  const card = document.querySelector('#app .cg');
  if (card) {                                                    // (the title row and the footer strip are not part of playing: only what is between them has to be seen whole)
    const room = vh - out.stuckH - (parseFloat(getComputedStyle(root0).getPropertyValue('--dock-h')) || 0), chrome = [...card.querySelectorAll(':scope > .cg-head, :scope > .cg-foot')].reduce((n, e) => n + e.getBoundingClientRect().height, 0);
    out.card = { h: Math.round(card.getBoundingClientRect().height - chrome), room: Math.round(room) };
  }
  // modal bounds
  const m = document.querySelector('#modal-root .modal');
  if (m) { const r = m.getBoundingClientRect(); out.modal = { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), fits: r.top >= 0 && r.bottom <= vh + 1 && r.left >= 0 && r.right <= vw + 1, scrolls: m.scrollHeight > m.clientHeight + 1 || getComputedStyle(m).overflowY === 'auto' }; }
  return out;
})()`;

export function problems(rep) {
  const p = [];
  if (rep.overflowX > 1) p.push(`PAGE scrolls sideways by ${rep.overflowX}px`);
  for (const x of rep.poke) p.push(`pokes out: ${x.el} (${x.left}..${x.right})`);
  for (const x of rep.cutControls) p.push(`control cut: ${x.el} (${x.reason})`);
  for (const x of rep.offControls) p.push(`control off-screen: ${x.el} (${x.left}..${x.right})`);
  for (const x of rep.truncated) p.push(`text cropped: ${x.el} (${x.sw}x${x.sh} in ${x.cw}x${x.ch})`);
  for (const x of rep.hiddenOverflow) p.push(`hidden overflow: ${x.el} (dx ${x.dx}, dy ${x.dy})`);
  if (rep.stuckH > rep.vh * 0.4) p.push(`pinned header takes ${rep.stuckH}px of ${rep.vh}px`);
  for (const x of rep.tallPinned || []) p.push(`pinned panel too tall: ${x}`);
  if (rep.card && rep.vw > 1000 && rep.card.room >= 640 && rep.card.h > rep.card.room + 4) p.push(`the table and the controls of a casino game are ${rep.card.h}px tall but only ${rep.card.room}px is visible under the header: they cannot be seen together`);
  if (rep.modal && !rep.modal.fits) p.push(`modal does not fit the viewport (${JSON.stringify(rep.modal)})`);
  return p;
}
