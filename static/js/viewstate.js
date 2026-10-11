/* Getting back to where you were, without ever trusting what you remembered about money.

   Two kinds of state live in Clique, and they are treated differently on purpose:
     * VISUAL state (scroll position, which tab was open, a filter, a search, a half-typed form) is remembered here, in this
       browser only, and put back when you return with Back/Forward, a "Back to..." shortcut or a reload.
     * ECONOMIC state (balances, prices, quotes, what a game round looks like, who holds what) is never remembered here. Every
       screen asks the server for it again when it opens, and every transaction is checked by the server again when it is made.
   A remembered amount in a bet box is just text you typed; the price it buys at is decided when you confirm, by the server.

   Each history entry gets a small marker the first time it is shown, so a later visit to the same entry (Back or Forward) can be
   told apart from a fresh link click, and its scroll position found again. */

import { t } from './i18n.js';

const MEM = new Map();
const KEY = 'clique-nav:';
const read = (k) => { try { return JSON.parse(sessionStorage.getItem(KEY + k) || 'null'); } catch { return null; } };
const write = (k, v) => { try { sessionStorage.setItem(KEY + k, JSON.stringify(v)); } catch { /* storage blocked: it still works for this visit */ } };

// ---- remembered visual state, per screen ---------------------------------------------------------------------------
export function recall(key) { return MEM.get(key) || read('v:' + key) || {}; }
export function remember(key, patch) {
  const next = { ...recall(key), ...patch };
  MEM.set(key, next);
  write('v:' + key, next);
  return next;
}

// ---- drafts: things you were typing -------------------------------------------------------------------------------
const DRAFT_DAYS = 3;
export function saveDraft(key, value) {
  try { localStorage.setItem('clique-draft:' + key, JSON.stringify({ t: Date.now(), v: value })); } catch { /* ignore */ }
}
export function loadDraft(key) {
  try {
    const d = JSON.parse(localStorage.getItem('clique-draft:' + key) || 'null');
    if (!d || Date.now() - d.t > DRAFT_DAYS * 86400000) return null;
    return d.v;
  } catch { return null; }
}
export function clearDraft(key) { try { localStorage.removeItem('clique-draft:' + key); } catch { /* ignore */ } }

/** Keeps the named fields of a form in a draft while you type, puts them back when you return, and tells you when to clear it. */
export function keepDraft(form, key, names) {
  const saved = loadDraft(key);
  let restored = false;
  if (saved) for (const n of names) { const el = form.elements[n] || form.querySelector(`[name="${n}"],#${n}`); if (el && saved[n] != null && saved[n] !== '') { el.value = saved[n]; restored = true; } }
  let t;
  const save = () => {
    clearTimeout(t);
    t = setTimeout(() => {
      const v = {}; let any = false;
      for (const n of names) { const el = form.elements[n] || form.querySelector(`[name="${n}"],#${n}`); if (el && el.value) { v[n] = el.value; any = true; } }
      if (any) saveDraft(key, v); else clearDraft(key);
    }, 250);
  };
  form.addEventListener('input', save);
  return { restored, clear: () => { clearTimeout(t); clearDraft(key); } };
}

// ---- history entries and scroll -----------------------------------------------------------------------------------
let seq = Number(read('seq')) || 0;
let entry = null;                 // the entry on screen now: { id }
const SCROLL = read('scroll') || {};
export const entryNow = () => entry;

/** Called when a screen is about to be shown. Returns { revisit } (true for Back/Forward/reload to an entry seen before). */
export function arrive() {
  const st = history.state;
  if (st && st.cq && st.cq.id) { entry = st.cq; return { revisit: true }; }
  entry = { id: 'e' + (++seq) + '-' + Math.random().toString(36).slice(2, 7) };
  write('seq', seq);
  try { history.replaceState({ ...(history.state || {}), cq: entry }, ''); } catch { /* sandboxed */ }
  return { revisit: false };
}
export function leaving() {
  if (!entry) return;
  SCROLL[entry.id] = Math.round(window.scrollY);
  const keys = Object.keys(SCROLL);
  if (keys.length > 80) for (const k of keys.slice(0, keys.length - 80)) delete SCROLL[k];
  write('scroll', SCROLL);
}
/** Puts the scroll position back (once the page is long enough to scroll to it), or starts at the top for a new visit. */
export function settle({ revisit }) {
  const y = revisit && entry ? SCROLL[entry.id] || 0 : 0;
  if (!y) { window.scrollTo(0, 0); return; }
  let tries = 0;
  const go = () => {
    const room = document.documentElement.scrollHeight - window.innerHeight;
    if (room >= y - 2 || tries++ > 25) window.scrollTo(0, Math.min(y, Math.max(0, room)));
    else setTimeout(go, 60);
  };
  go();
}
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';       // we do it ourselves, after the content has loaded

// ---- "are you sure?" when a form with real changes would be lost --------------------------------------------------
const guards = new Set();
/** Registers a form with unsaved changes. `dirty()` says whether there is anything to lose. Returns a view handle (unmount removes it). */
export function guardForm(dirty, message = t('Tienes cambios sin guardar. ¿Salir sin guardar?')) {
  const g = { dirty, message };
  guards.add(g);
  return { unmount() { guards.delete(g); } };
}
export const unsaved = () => [...guards].find((g) => { try { return g.dirty(); } catch { return false; } }) || null;
window.addEventListener('beforeunload', (e) => { if (unsaved()) { e.preventDefault(); e.returnValue = ''; } });
