/* How people look: profile picture, frame, badge, title. The server sends each person's look along with their name
   (a small `st` object), api.js hands every answer to registerLooks(), and avatar() in util.js asks lookOf(name).
   So every list in the app (leaderboards, members, chat, menus) shows cosmetics without each one knowing about them.
   An empty look ({}) means "all defaults"; a person who never changed anything has no entry at all. */
import { glyph } from './art.js';

const LOOKS = new Map();
export const lookOf = (name) => LOOKS.get(String(name)) || null;

/** Walks an API answer and remembers every {username, st} it finds. */
export function registerLooks(node, depth = 0) {
  if (!node || typeof node !== 'object' || depth > 6) return;
  if (Array.isArray(node)) { for (const n of node) registerLooks(n, depth + 1); return; }
  if (typeof node.username === 'string' && node.st && typeof node.st === 'object') {
    if (Object.keys(node.st).length) LOOKS.set(node.username, node.st); else LOOKS.delete(node.username);
  }
  for (const k in node) { const v = node[k]; if (v && typeof v === 'object') registerLooks(v, depth + 1); }
}
export const setLook = (name, st) => { if (st && Object.keys(st).length) LOOKS.set(name, st); else LOOKS.delete(name); };

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const HEX = /^#[0-9a-fA-F]{6}$/;

/** A person's picture with their frame and badge. `letter` is the plain tile everybody has by default. */
export function avatarLook(name, size, look, bg, fg) {
  const f = look.f && HEX.test(look.f.color || '') ? look.f : null;
  const cls = ['avatar'];
  let style = `--s:${size}px;background:${bg};color:${fg}`;
  let inner = esc((name || '?')[0].toUpperCase());
  if (look.u && /^[a-f0-9]{12}-[a-f0-9]{8}\.(png|jpg|webp)$/.test(look.u)) {
    cls.push('av-pic');
    inner += `<img src="/uploads/avatars/${look.u}" alt="" width="${size}" height="${size}" decoding="async" loading="lazy">`;
  } else if (look.a && /^[a-z]+$/.test(look.a.icon || '') && HEX.test(look.a.bg || '')) {
    cls.push('av-icon');
    style = `--s:${size}px;background:${look.a.bg};color:${fg}`;
    inner = `<img src="/casino-icons/small/${look.a.icon}.png" alt="" width="${size}" height="${size}" decoding="async">`;
  }
  if (f) { cls.push('fr', 'fr-' + (['solid', 'double', 'dashed'].includes(f.style) ? f.style : 'solid')); if (f.shadow) cls.push('fr-shadow'); style += `;--fr:${f.color};--frw:${Math.max(1, Math.min(6, +f.width || 3))}px`; }
  const badge = look.b && size >= 28 && /^[a-z]+$/.test(look.b) ? `<i class="av-badge" style="--bs:${Math.round(size * 0.46)}px"><svg viewBox="0 0 64 64" aria-hidden="true">${glyph(look.b)}</svg></i>` : '';
  return `<span class="${cls.join(' ')}" style="${style}">${inner}${badge}</span>`;
}

/** The little line of text under somebody's name, if they chose a title. */
export const titleHtml = (name) => { const l = lookOf(name); return l && l.t ? `<span class="who-title">${esc(l.t)}</span>` : ''; };

// ---- banner patterns: flat colours and a repeating shape, as inline SVG (no images to download) ----
// Quote characters are escaped too, so the result can sit safely inside an HTML style="..." attribute without any quotes of its own.
const uri = (svg) => `url(data:image/svg+xml,${encodeURIComponent(svg).replace(/'/g, '%27').replace(/\(/g, '%28').replace(/\)/g, '%29')})`;
export function bannerCss(art = {}) {
  const a = HEX.test(art.a || '') ? art.a : '#2A2420', b = HEX.test(art.b || '') ? art.b : a;
  const tile = (w, h, body) => uri(`<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}'><rect width='${w}' height='${h}' fill='${a}'/>${body}</svg>`);
  switch (art.pattern) {
    case 'stripes': return `background-color:${a};background-image:${tile(24, 24, `<path d='M-6 6 6 -6M-6 30 30 -6M18 30 30 18' stroke='${b}' stroke-width='7'/>`)}`;
    case 'dots': return `background-color:${a};background-image:${tile(14, 14, `<circle cx='7' cy='7' r='3' fill='${b}'/>`)}`;
    case 'checks': return `background-color:${a};background-image:${tile(40, 40, `<rect width='20' height='20' fill='${b}'/><rect x='20' y='20' width='20' height='20' fill='${b}'/>`)}`;
    case 'waves': return `background-color:${a};background-image:${tile(44, 18, `<path d='M0 9Q11 -1 22 9T44 9' fill='none' stroke='${b}' stroke-width='3'/>`)}`;
    default: return `background:${a}`;
  }
}
