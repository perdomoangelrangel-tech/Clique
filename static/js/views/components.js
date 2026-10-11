import { esc, vol, cents, until, thumb, circleMark, oddsBar, ICON, pctOf, catName, sideName } from '../util.js';
import { sticker } from '../art.js';
import { go } from '../state.js';
import { isBookmarked, toggleBookmark } from '../bookmarks.js';
import { t, tp } from '../i18n.js';

export const isYesNo = (m) => m.binary && m.outcomes[0].name === 'Yes' && m.outcomes[1].name === 'No';      // i18n: no (the names the server gives the two sides)

/** "№ 0042": a stable ticket number made from the market id. */
export const slipNo = (m) => '№ ' + String(parseInt(m.id.slice(0, 4), 16) % 10000).padStart(4, '0');

export function circleTag(c) {
  return `<span class="tag" title="${esc(c.visibility === 'public' ? t('Círculo público') : t('Círculo privado'))}">${c.visibility === 'public' ? ICON.globe : ICON.lock} ${circleMark(c, 14)} ${esc(c.name)}</span>`;
}

/** Where a bet lives: its circle, or "Public" when anyone on the site can bet on it. */
export const whereHtml = (m, size = 13) => (m.circle
  ? `${circleMark(m.circle, size)} ${esc(m.circle.name)}`
  : `<span class="where-ico">${ICON.globe}</span> ${t('Público')}`);

export const bmButton = (id) => `<button class="bm ${isBookmarked(id) ? 'on' : ''}" data-bm="${id}" title="${esc(t('Guardar boleto'))}" aria-label="${esc(t('Guardar boleto'))}">${isBookmarked(id) ? ICON.bookmarkOn : ICON.bookmark}</button>`;

/** Builds the Yes/No (or per-outcome) choices for a slip. */
export function slipChoices(m, link) {
  const open = m.status === 'open';
  const O = m.outcomes;
  if (isYesNo(m)) {
    return `<div class="odds"><div class="od y"><span class="lbl">${t('Sí')}</span><b class="num">${cents(O[0].yes)}</b></div><div class="od n"><span class="lbl">${t('No')}</span><b class="num">${cents(O[1].yes)}</b></div></div>
      ${oddsBar(O[0].yes)}
      ${open ? `<div class="slip-btns"><button class="ybtn" data-go="${link(0, 'yes')}">${t('Comprar sí')}</button><button class="nbtn" data-go="${link(1, 'yes')}">${t('Comprar no')}</button></div>` : ''}`;
  }
  if (m.binary) {
    return `<div class="odds"><div class="od y"><span class="lbl ellipsis">${esc(O[0].name)}</span><b class="num">${cents(O[0].yes)}</b></div><div class="od n"><span class="lbl ellipsis">${esc(O[1].name)}</span><b class="num">${cents(O[1].yes)}</b></div></div>
      ${oddsBar(O[0].yes)}
      ${open ? `<div class="slip-btns"><button class="ybtn" data-go="${link(0, 'yes')}"><span class="ellipsis">${esc(O[0].name)}</span></button><button class="nbtn" data-go="${link(1, 'yes')}"><span class="ellipsis">${esc(O[1].name)}</span></button></div>` : ''}`;
  }
  const order = O.map((o, i) => ({ ...o, i })).sort((a, b) => b.yes - a.yes);
  return `<div class="orows">${order.slice(0, 4).map((o) => `<div class="orow"><span class="nm ellipsis">${esc(o.name)}</span><span class="opct num">${pctOf(o)}</span>
    ${open ? `<button class="ybtn sm" data-go="${link(o.i, 'yes')}">${t('Sí')}</button><button class="nbtn sm" data-go="${link(o.i, 'no')}">${t('No')}</button>` : ''}</div>`).join('')}
    ${order.length > 4 ? `<div class="more">${tp(order.length - 4, '+{n} más en el boleto', '+{n} más en el boleto')}</div>` : ''}</div>`;
}

export function marketCard(m, { fresh = false } = {}) {
  const isNew = Date.now() - m.createdAt < 86400000 && m.status === 'open';
  const link = (o, s) => `#/market/${m.id}?o=${o}&s=${s}`;
  const settled = m.status === 'resolved' || m.status === 'cancelled';
  const wide = !m.binary && m.outcomes.length >= 3;
  const stamp = m.status === 'resolved' ? `${t('Resuelto')} · ${esc(sideName(m.outcomes[m.winner].name, m.binary))}` : m.status === 'cancelled' ? t('Cancelado') : m.status === 'closed' ? t('Apuestas cerradas') : '';
  const ends = m.status === 'open' && m.closesAt ? `<span>${t('Cierra en {tiempo}', { tiempo: until(m.closesAt) })}</span>` : '';
  return `<article class="mcard slip paper ${wide ? 'wide' : ''} ${settled || m.status === 'closed' ? 'settled' : ''} ${fresh ? 'pop' : ''}" data-id="${m.id}">
    <div class="slip-top"><span>${slipNo(m)} · ${esc(catName(m.category))}</span>${isNew ? `<span class="tag new">${t('Nuevo')}</span>` : ''}<span class="sp"></span>${bmButton(m.id)}</div>
    <div class="slip-body">
      <div class="slip-main">${thumb(m)}<h3 class="slip-q">${esc(m.question)}</h3></div>
      <div class="slip-pick">${slipChoices(m, link)}</div>
    </div>
    ${stamp ? `<span class="stamp slip-stamp">${stamp}</span>` : ''}
    <div class="slip-foot"><span>${t('Vol.')} <b class="num">${vol(m.volume)}</b></span><span class="where ellipsis">${whereHtml(m)}</span><span class="sp"></span>${ends}</div>
  </article>`;
}

/** Clicks on slips: buy buttons jump to the market with the side preselected, bookmark toggles in place. */
export function wireCards(root) {
  if (root.__wired) return;
  root.__wired = true;
  root.addEventListener('click', (e) => {
    const bm = e.target.closest('[data-bm]');
    if (bm) {
      e.stopPropagation();
      const on = toggleBookmark(bm.dataset.bm);
      bm.classList.toggle('on', on); bm.innerHTML = on ? ICON.bookmarkOn : ICON.bookmark;
      root.dispatchEvent(new CustomEvent('bookmark', { bubbles: true }));
      return;
    }
    const b = e.target.closest('[data-go]');
    if (b) { e.stopPropagation(); go(b.dataset.go); return; }
    const c = e.target.closest('.mcard');
    if (c) go(`#/market/${c.dataset.id}`);
  });
}

/**
 * Empty states: a sticker leaning on a note. Text is left-aligned and has a voice.
 * art = a glyph name from art.js, tone = tile colour.
 */
export function emptyState({ art = 'slip', tone = 'cream', kicker = '', title, text = '', actions = '', tight = false }) {
  return `<div class="empty ${tight ? 'tight' : ''}"><div class="empty-art">${sticker(art, { size: tight ? 84 : 120, bg: tone })}</div>
    <div class="empty-copy">${kicker ? `<span class="kicker">${esc(kicker)}</span>` : ''}<h3>${title}</h3>${text ? `<p>${text}</p>` : ''}${''/* html: seguro (title y text son HTML de quien llama; quien llama escapa lo de personas) */}${actions ? `<div class="btns">${actions}</div>` : ''}</div></div>`;
}
