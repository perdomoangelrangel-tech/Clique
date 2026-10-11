/* The language system. Every sentence on screen goes through t('the sentence in Mexican Spanish'): the Spanish text is the key, so a
   sentence nobody has translated yet still reads fine (in Spanish). English lives in /i18n/en.json, one "Spanish": "English" pair per
   sentence. Numbers, chips and dates are written with Intl, the es-MX way. Switching language never reloads the page: whoever cares
   listens with onLang() and paints itself again. How keys are written, plurals and the chip format: equipo/contratos/textos.md. */

export const LANGS = { 'es-MX': 'Español (México)', en: 'English' };      // i18n: no (each language is named in its own words)
const BASE = 'es-MX';
const STORE_KEY = 'clique-lang';
const INTL = { 'es-MX': 'es-MX', en: 'en-US' };

let lang = BASE;
let dict = {};
const cache = new Map();                 // loader -> { code: words }, so a test's loader never sees another's
const listeners = new Set();

const defaultLoader = async (code) => {
  const r = await fetch(`/i18n/${code}.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`/i18n/${code}.json: ${r.status}`);
  return r.json();
};

const fill = (s, vars, wrap = String) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] === undefined || vars[k] === null ? m : wrap(vars[k]))) : s);
const escHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const look = (key) => (lang !== BASE && typeof dict[key] === 'string' && dict[key] ? dict[key] : key);

/** The sentence in the language on screen, with {placeholders} filled in. Plain text: escape it before it goes into HTML (or use th). */
export function t(key, vars) { return fill(look(key), vars); }

/** Same as t(), for HTML: the values that go into the placeholders are escaped (the sentence itself is ours and may hold <b>). */
export function th(key, vars) { return fill(look(key), vars, escHtml); }

/** One of two sentences depending on how many: tp(n, '{n} ficha', '{n} fichas'). {n} is written the es-MX way. */
export function tp(n, one, other, vars = {}) {
  const form = new Intl.PluralRules(INTL[lang]).select(Number(n)) === 'one' ? one : other;
  return t(form, { n: number(n, 0), ...vars });
}

export const getLang = () => lang;
export const intlLocale = () => INTL[lang];

/** Who wants to know when the language changes. Returns a function that stops listening. */
export function onLang(fn) { listeners.add(fn); return () => listeners.delete(fn); }

/** Switch language without reloading. A dictionary that cannot be loaded leaves the app in Spanish. */
export async function setLang(code, { loader = defaultLoader } = {}) {
  let next = Object.prototype.hasOwnProperty.call(LANGS, code) ? code : BASE;
  let words = {};
  if (next !== BASE) {
    const mine = cache.get(loader) || cache.set(loader, {}).get(loader);
    try { words = mine[next] || (mine[next] = await loader(next)); } catch { next = BASE; words = {}; }
  }
  const changed = next !== lang;
  lang = next; dict = words;
  try { document.documentElement.setAttribute('lang', lang); } catch { /* no page (tests) */ }
  try { localStorage.setItem(STORE_KEY, lang); } catch { /* storage blocked: the choice lasts until the tab closes */ }
  if (changed) listeners.forEach((fn) => { try { fn(lang); } catch (e) { console.error(e); } });
  return lang;
}

/** At start-up: the language this browser chose last time, or Spanish. */
export async function initLang(opts = {}) {
  let code = BASE;
  try { code = localStorage.getItem(STORE_KEY) || BASE; } catch { /* storage blocked */ }
  return setLang(code, opts);
}

// ---------------------------------------------------------------- numbers, chips and dates

export function number(x, digits = 2) {
  x = Number(x) || 0;
  if (Math.abs(x) >= 1e15) return x.toExponential(2).replace('e+', 'e');
  return x.toLocaleString(INTL[lang], { maximumFractionDigits: digits });
}

/* Chips are not money (D3), but the app has always written them with a sign in front. Until the owner decides (question in the log),
   the sign lives here and only here, so changing it is one line. */
export const CHIP_SIGN = '$';
const BIG = { 'es-MX': [[1e12, ' B'], [1e9, ' mil M'], [1e6, ' M']], en: [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']] };      // i18n: no (each language's own units)

/** 1234.5 → "$1,234.50"; big amounts shrink ("$2.5 M") so they always fit. opts: plus (a + on gains), noCents (whole amounts without .00). */
export function chips(x, opts = {}) {
  x = Number(x) || 0;
  const sign = x < 0 ? '-' : (opts.plus && x > 0 ? '+' : '');
  const a = Math.abs(x);
  if (a >= 1e15) return sign + CHIP_SIGN + a.toExponential(2).replace('e+', 'e');
  for (const [lim, suf] of BIG[lang]) {
    if (a >= lim) return sign + CHIP_SIGN + (a / lim).toLocaleString(INTL[lang], { maximumFractionDigits: 2 }) + suf;
  }
  const whole = opts.noCents && Number.isInteger(a);
  return sign + CHIP_SIGN + a.toLocaleString(INTL[lang], { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
}

/** The full amount, never shortened (for a tooltip). */
export const chipsFull = (x) => CHIP_SIGN + (Number(x) || 0).toLocaleString(INTL[lang], { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmt = (t, base, opts) => new Date(t).toLocaleString(INTL[lang], { ...base, ...opts });
/** "10 oct 2026" */
export const date = (t, opts) => fmt(t, { day: 'numeric', month: 'short', year: 'numeric' }, opts);
/** "10 oct" */
export const dateShort = (t, opts) => fmt(t, { day: 'numeric', month: 'short' }, opts);
/** "12:05 p.m." */
export const time = (t, opts) => fmt(t, { hour: 'numeric', minute: '2-digit' }, opts);
/** "10 oct 2026, 12:05 p.m." */
export const dateTime = (t, opts) => fmt(t, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }, opts);

/** "hace 5 min" */
export function ago(ts) {
  const s = Math.max(0, (Date.now() - ts) / 1000);
  if (s < 45) return t('justo ahora');
  if (s < 3600) return t('hace {n} min', { n: Math.round(s / 60) });
  if (s < 86400) return t('hace {n} h', { n: Math.round(s / 3600) });
  if (s < 86400 * 30) return t('hace {n} d', { n: Math.round(s / 86400) });
  return date(ts);
}

/** "2 d 3 h" until a moment; "terminó" once it has passed. */
export function until(ts) {
  const s = (ts - Date.now()) / 1000;
  if (s <= 0) return t('terminó');
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (d > 0) return t('{d} d {h} h', { d, h });
  if (h > 0) return t('{h} h {m} min', { h, m });
  return t('{m} min', { m: Math.max(1, m) });
}

// ---------------------------------------------------------------- server errors

/* What to say for each error code the server sends (the list is E3's: equipo/contratos/errores.md). A code missing here shows the
   server's own text, so a new code is never hidden. */
const ERRORS = {                         // i18n: claves ↓
  NOT_FOUND: 'No encontramos lo que buscabas.',
  UNAUTHORIZED: 'Tu sesión terminó. Vuelve a entrar.',
  FORBIDDEN: 'No tienes permiso para hacer eso.',
  RATE_LIMITED: 'Vas muy rápido. Espera un momento y vuelve a intentarlo.',
  INSUFFICIENT_FUNDS: 'No te alcanzan las fichas.',
  INVALID_AMOUNT: 'Esa cantidad no es válida.',
  MARKET_CLOSED: 'Este mercado ya cerró.',
  NETWORK: 'Sin conexión. Revisa tu internet y vuelve a intentarlo.',
};                                       // i18n: fin

export function tError(err) {
  if (!err) return t('Algo salió mal. Inténtalo otra vez.');
  if (err.code && ERRORS[err.code]) return t(ERRORS[err.code]);
  return err.message || t('Algo salió mal. Inténtalo otra vez.');
}
