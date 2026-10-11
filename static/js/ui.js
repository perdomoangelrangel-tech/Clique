import { esc } from './util.js';
import { icon } from './icons.js';
import { t } from './i18n.js';

// ---- putting text people wrote on the page (names, messages, market titles, punishments) without it ever becoming markup.
// The check that keeps it that way: tests/js/html_seguro.test.mjs.

/** Text, ready to sit inside HTML: & < > " ' become entities. (The same as esc() in util.js.) */
export const escape = esc;

/** Puts text on the page as text. Prefer it to innerHTML whenever there is no markup to add. */
export function setText(el, text) {
  if (el) el.textContent = text === null || text === undefined ? '' : String(text);
  return el;
}

/** Markup this code built itself, to pass through html`` untouched. Never wrap something a person typed in it. */
export const raw = (markup) => ({ __html: String(markup ?? '') });

/** html`<b>${name}</b> said ${raw(icon('chat'))}`: every value is escaped unless it is raw(); arrays are joined. Returns a string. */
export function html(strings, ...values) {
  const one = (v) => (v && typeof v === 'object' && '__html' in v ? v.__html : esc(v));
  return strings.reduce((out, s, i) => out + s + (i < values.length ? (Array.isArray(values[i]) ? values[i].map(one).join('') : one(values[i])) : ''), '');
}

export function toast(msg, kind = '', opts = {}) {
  const root = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${kind} ${opts.onClick ? 'click' : ''}`;
  el.textContent = msg;
  if (opts.onClick) el.addEventListener('click', () => { opts.onClick(); el.remove(); });
  root.appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .3s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, opts.ms || 3200);
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Opens a modal. `html` is the inner markup. Returns { el, close }. */
export function modal(html, { wide = false, onClose, guard, locked = false } = {}) {
  const root = document.getElementById('modal-root');
  const back = document.createElement('div');
  back.className = 'modal-back';
  back.innerHTML = `<div class="modal paper ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">${html}</div>`;
  root.appendChild(back);
  // A window taller than the screen scrolls, and its buttons stay pinned to the bottom edge so they are always within reach (layout.css, .tall).
  const fit = () => back.classList.toggle('tall', back.scrollHeight > back.clientHeight + 1);
  const ro = window.ResizeObserver ? new ResizeObserver(fit) : null;
  if (ro) ro.observe(back.firstElementChild);
  window.addEventListener('resize', fit); fit();
  const opener = document.activeElement;
  const close = () => {
    const hadFocus = back.contains(document.activeElement);
    back.remove(); document.removeEventListener('keydown', onKey); document.removeEventListener('keydown', onTab); window.removeEventListener('resize', fit); if (ro) ro.disconnect();
    if (hadFocus && opener && opener.isConnected && opener.focus) opener.focus();      // keyboard users land back on the button that opened it
    onClose && onClose();
  };
  // Tab stays inside the top-most window: it wraps round at either end, and comes in from the page behind if the window opened with nothing focused.
  const onTab = (e) => {
    if (e.key !== 'Tab' || back !== root.lastElementChild) return;
    const items = [...back.querySelectorAll(FOCUSABLE)].filter((n) => n.getClientRects().length);
    if (!items.length) { e.preventDefault(); return; }
    const at = items.indexOf(document.activeElement), edge = e.shiftKey ? 0 : items.length - 1;
    if (at === -1 || at === edge) { e.preventDefault(); items[e.shiftKey ? items.length - 1 : 0].focus(); }
  };
  document.addEventListener('keydown', onTab);
  // Closing a window never touches the page underneath. If the window holds changes that would be lost (`guard()` says so),
  // closing it by clicking outside, pressing Escape or Cancel asks first; closing it from code (after saving) does not.
  let asking = false;
  const tryClose = async () => {
    if (asking) return;
    if (guard && guard()) {
      asking = true;
      const leave = await confirmBox({ title: t('¿Descartar tus cambios?'), text: t('Lo que cambiaste en esta ventana no se ha guardado.'), confirm: t('Descartar'), danger: true });
      asking = false;
      if (!leave) return;
    }
    close();
  };
  const onKey = (e) => { if (e.key === 'Escape' && back === root.lastElementChild) tryClose(); };     // only the top-most window answers Escape
  if (!locked) {                                       // a locked window (the one that asks everybody for an email) can only be closed from code
    document.addEventListener('keydown', onKey);
    back.addEventListener('mousedown', (e) => { if (e.target === back) tryClose(); });
    back.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', tryClose));
  }
  const first = back.querySelector('input, textarea, select');
  if (first) setTimeout(() => first.focus(), 30);
  return { el: back.firstElementChild, close };
}

export function confirmBox({ title, text, confirm = t('Confirmar'), danger = false }) {
  return new Promise((resolve) => {
    const m = modal(`<h2>${esc(title)}</h2><p class="lede">${esc(text)}</p>
      <div class="modal-actions"><button class="btn btn-secondary" data-close>${esc(t('Mejor no'))}</button>
      <button class="btn ${danger ? 'btn-no' : 'btn-primary'}" id="cf-ok">${esc(confirm)}</button></div>`, { onClose: () => resolve(false) });
    m.el.querySelector('#cf-ok').addEventListener('click', () => { resolve(true); m.close(); });
  });
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const area = document.createElement('textarea'); area.value = text; document.body.appendChild(area); area.select();
    try { document.execCommand('copy'); } catch { /* ignore */ }
    area.remove();
  }
  toast(t('¡Copiado!'), 'ok');
}

/** Animates a number inside an element. */
export function tween(el, from, to, fmt, ms = 600) {
  const t0 = performance.now();
  const step = (at) => {
    const k = Math.min(1, (at - t0) / ms);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Gives every password box inside `scope` an eye button, so people can check what they typed. */
export function revealPasswords(scope) {
  scope.querySelectorAll('input[type="password"]').forEach((input) => {
    if (input.parentElement.classList.contains('pw')) return;
    const wrap = document.createElement('div');
    wrap.className = 'pw';
    input.replaceWith(wrap);
    wrap.appendChild(input);
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('spellcheck', 'false');
    const eye = document.createElement('button');
    eye.type = 'button';
    eye.className = 'icon-btn pw-eye';
    const set = (shown) => {
      input.type = shown ? 'text' : 'password';
      eye.innerHTML = icon(shown ? 'eye-slash' : 'eye', 20);
      eye.setAttribute('aria-pressed', String(shown));
      eye.setAttribute('aria-label', shown ? t('Ocultar contraseña') : t('Mostrar contraseña'));
      eye.title = shown ? t('Ocultar contraseña') : t('Mostrar contraseña');
    };
    eye.addEventListener('click', () => { set(input.type === 'password'); input.focus(); });
    set(false);
    wrap.appendChild(eye);
  });
}
