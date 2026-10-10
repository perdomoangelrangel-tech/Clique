import { icon } from './icons.js';
import { sticker, CATEGORY_ART } from './art.js';
import { lookOf, avatarLook } from './looks.js';

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* history rows: the server writes "1 lanes"; say it properly */
export const detailText = (d) => esc(String(d ?? '').replace(/\b1 lanes\b/, '1 lane'));

const SUFFIX = [[1e15, null], [1e12, 'T'], [1e9, 'B'], [1e6, 'M']];

/** $1,234.56 — big numbers shrink to $1.23M / $4.5B / $1.2e18 so they always fit. */
export function money(x, opts = {}) {
  x = Number(x) || 0;
  const sign = x < 0 ? '-' : (opts.plus && x > 0 ? '+' : '');
  const a = Math.abs(x);
  for (const [lim, suf] of SUFFIX) {
    if (a >= lim) return sign + '$' + (suf ? (a / lim).toLocaleString('en-US', { maximumFractionDigits: 2 }) + suf : a.toExponential(2).replace('e+', 'e'));
  }
  return sign + '$' + a.toLocaleString('en-US', { minimumFractionDigits: opts.noCents && Number.isInteger(a) ? 0 : 2, maximumFractionDigits: 2 });
}
export const moneyFull = (x) => '$' + (Number(x) || 0).toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 });

export function vol(x) {
  x = Number(x) || 0;
  if (x < 1000) return '$' + Math.round(x).toLocaleString('en-US');
  if (x < 1e6) return '$' + (x / 1e3).toFixed(x < 1e4 ? 1 : 0).replace(/\.0$/, '') + 'K';
  if (x < 1e9) return '$' + (x / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
  if (x < 1e12) return '$' + (x / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
  return money(x, { noCents: true });
}

export function num(x, d = 2) {
  x = Number(x) || 0;
  if (Math.abs(x) >= 1e9) return x.toExponential(2).replace('e+', 'e');
  return x.toLocaleString('en-US', { maximumFractionDigits: d });
}

export function cents(p) {
  const c = p * 100;
  if (c >= 99.95) return '100¢';
  if (c < 0.05) return '0¢';
  const s = c < 10 || Math.abs(c - Math.round(c)) > 0.05 ? c.toFixed(1) : String(Math.round(c));
  return s.replace(/\.0$/, '') + '¢';
}
/** The whole-number chance the server worked out for an outcome row. A market's rows always add up to exactly 100. */
export const pctOf = (o) => (typeof o.pct !== 'number' ? pct(o.yes) : o.pct === 0 && o.yes > 0 ? '<1%' : o.pct === 100 && o.yes < 1 ? '>99%' : o.pct + '%');
export function pct(p) {
  const c = p * 100;
  if (c > 0 && c < 1) return '<1%';
  if (c > 99 && c < 100) return '>99%';
  return Math.round(c) + '%';
}

export function ago(t) {
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return Math.round(s / 60) + 'm ago';
  if (s < 86400) return Math.round(s / 3600) + 'h ago';
  if (s < 86400 * 30) return Math.round(s / 86400) + 'd ago';
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
export function until(t) {
  const s = (t - Date.now()) / 1000;
  if (s <= 0) return 'ended';
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${Math.max(1, m)}m`;
}
export const dateShort = (t) => new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
export const dateLong = (t) => new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });

function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
export const hues = (seed) => { const h = hash(String(seed)); return [h % 360, (h >> 8) % 360]; };

// ---- people: flat colour tiles, no gradients ----
const AVATARS = [['#C6F432', '#10140A'], ['#FF4B2B', '#170805'], ['#EFE6D2', '#1A1612'], ['#2F6B47', '#F2EADB'], ['#CFC3A8', '#1A1612']];
export function avatar(name, size = 32) {
  const [bg, fg] = AVATARS[hash(String(name)) % AVATARS.length];
  const look = lookOf(name);
  if (look) return avatarLook(name, size, look, bg, fg);                        // picture, frame and badge they chose
  return `<span class="avatar" style="--s:${size}px;background:${bg};color:${fg}">${esc((name || '?')[0].toUpperCase())}</span>`;
}

// ---- markets and circles: sticker art unless the person picked their own emoji ----
// (the server fills these in when nobody picked one, so they count as "no choice")
const AUTO_EMOJI = { General: '\u{1F3B2}', Sports: '\u{1F3C6}', Gaming: '\u{1F3AE}', Life: '\u{1F331}', Money: '\u{1F4B0}', Dares: '\u{1F608}', Music: '\u{1F3B5}', Other: '✨' };
const AUTO_CIRCLE = '\u{1F465}';
const FRAME = ['#C6F432', '#FF4B2B', '#EFE6D2', '#2F6B47', '#CFC3A8'];

export function thumb(m, big = false) {
  const size = big ? 64 : 44;
  if (!m.emoji || AUTO_EMOJI[m.category] === m.emoji) {
    const [n, bg] = CATEGORY_ART[m.category] || CATEGORY_ART.Other;
    return `<div class="thumb ${big ? 'thumb-lg' : ''}">${sticker(n, { size, bg })}</div>`;
  }
  return `<div class="thumb thumb-emo ${big ? 'thumb-lg' : ''}" style="background:${FRAME[hash(m.id || m.question) % FRAME.length]}">${esc(m.emoji)}</div>`;
}

/** A circle's little mark: the emoji its owner picked, or a letter tile when they didn't. */
export function circleMark(c, size = 16) {
  if (c.emoji && c.emoji !== AUTO_CIRCLE) return `<span class="cmark cmark-emo" style="--s:${size}px">${esc(c.emoji)}</span>`;
  const [bg, fg] = AVATARS[hash(c.name || c.id || '') % AVATARS.length];
  return `<span class="cmark" style="--s:${size}px;background:${bg};color:${fg}">${esc((c.name || '?')[0].toUpperCase())}</span>`;
}

export const ICON = {
  search: icon('magnifying-glass', 16), trend: icon('trend-up', 16), dice: icon('dice-five', 16), users: icon('users-three', 16), cal: icon('calendar-blank', 16),
  plus: icon('plus', 14), lock: icon('lock-simple', 12), globe: icon('globe-simple', 12), check: icon('check', 16), copy: icon('copy', 16),
  moon: icon('moon', 16), sun: icon('sun', 16), user: icon('user', 16), out: icon('sign-out', 16), wallet: icon('wallet', 16), link: icon('link-simple', 16),
  trophy: icon('trophy', 16), bookmark: icon('bookmark-simple', 18), bookmarkOn: icon('bookmark-simple-fill', 18), flame: icon('fire-fill', 14),
  chevR: icon('caret-right', 14), chevL: icon('caret-left', 14), chevD: icon('caret-down', 14), sliders: icon('sliders-horizontal', 18), info: icon('info', 18),
  shield: icon('shield-check-fill', 16), expand: icon('arrows-out-simple', 18), menu: icon('list', 20), undo: icon('arrow-u-up-left', 18), redo: icon('arrow-u-up-right', 18),
  pencil: icon('pencil-simple', 14), home: icon('house-simple', 18), star: icon('star', 18), starOn: icon('star-fill', 18), clock: icon('clock', 18), wallet2: icon('wallet', 18),
  x: icon('x', 14), hand: icon('hand-palm', 18), split: icon('arrows-split', 18), bolt: icon('lightning', 18), minus: icon('minus', 14), warn: icon('warning', 16),
  crown: icon('crown-simple', 16), chat: icon('chat-circle', 16), gear: icon('gear', 18), arrowR: icon('arrow-right', 16), arrowUR: icon('arrow-up-right', 14),
  trash: icon('trash', 16), coins: icon('coins', 16), clockc: icon('clock-countdown', 16),
};

/** Flat two-colour odds bar: lime for YES, vermillion for NO. */
export const oddsBar = (p) => `<div class="oddsbar" style="--p:${(Math.max(0, Math.min(1, p)) * 100).toFixed(1)}%" aria-hidden="true"><i></i></div>`;

export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Reads a money-ish string. Returns NaN for junk. Accepts "1,200.5", "$40". No upper limit. */
export function parseAmount(s) {
  const t = String(s ?? '').replace(/[$,\s]/g, '');
  if (!t || !/^\d*\.?\d*$/.test(t) || t === '.') return NaN;
  return parseFloat(t);
}
export const floorCents = (x) => Math.floor(x * 100 + 1e-9) / 100;

/** Odometer-style update: only the digits that changed roll in. Falls back to a plain swap. */
export function roll(el, next) {
  next = String(next);
  const prev = el.dataset.v;
  if (prev === next) { if (!el.firstChild) el.textContent = next; return; }
  el.dataset.v = next;
  if (prev === undefined || matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = next; return; }
  const a = prev.padStart(next.length, ' ');
  el.innerHTML = [...next].map((ch, i) => (a[i] !== ch
    ? `<span class="rl"><i style="--d:${i * 28}ms">${esc(ch)}</i></span>` : `<span>${esc(ch)}</span>`)).join('');
}
