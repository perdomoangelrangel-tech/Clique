/* Drawing products and previews: the Store and the profile editor both use these, so an item looks the same wherever it appears. */
import { sticker } from './art.js';
import { avatarLook, bannerCss } from './looks.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const BASE = ['#C6F432', '#FF4B2B', '#EFE6D2', '#2F6B47', '#CFC3A8'];
const baseColors = (name) => { let h = 2166136261; for (const ch of String(name)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return [BASE[(h >>> 0) % BASE.length], '#10140A']; };

/** The person's plain picture: their upload if they have one, otherwise the initial tile. */
export function plainAvatar(name, size, look = {}) {
  const [bg, fg] = baseColors(name);
  return avatarLook(name, size, look, bg, fg);
}

/** A picture of a product: what it would look like. `fonts` maps a font name to its CSS family list. */
export function productArt(item, { name = 'you', size = 72, fonts = {} } = {}) {
  const a = item.art || {};
  switch (item.kind) {
    case 'avatar':
      return a.icon ? plainAvatar(name, size, { a: { icon: a.icon, bg: a.bg } }) : plainAvatar(name, size, {});
    case 'frame':
      return a.style === 'none' ? plainAvatar(name, size, {}) : plainAvatar(name, size, { f: a });
    case 'badge':
      return a.glyph ? `<span class="pa-badge">${sticker(a.glyph, { size, bg: 'cream' })}</span>` : `<span class="pa-none">none</span>`;
    case 'title':
      return `<span class="pa-title">${a.text ? esc(a.text) : 'no title'}</span>`;
    case 'banner':
      return `<span class="pa-banner" style="${bannerCss(a)}"></span>`;
    case 'accent':
      return `<span class="pa-accent" style="--c:${esc(a.color)}"><i></i><em>${esc(a.color)}</em></span>`;
    case 'font':
      return `<span class="pa-font" style="font-family:${fonts[a.family] || 'inherit'}">Aa</span>`;
    default:
      return '';
  }
}
