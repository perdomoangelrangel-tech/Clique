import { esc, vol, cents, until, thumb, circleMark, oddsBar, ICON, pctOf } from '../util.js';
import { sticker } from '../art.js';
import { go } from '../state.js';
import { isBookmarked, toggleBookmark } from '../bookmarks.js';

export const isYesNo = (m) => m.binary && m.outcomes[0].name === 'Yes' && m.outcomes[1].name === 'No';

/** "№ 0042": a stable ticket number made from the market id. */
export const slipNo = (m) => '№ ' + String(parseInt(m.id.slice(0, 4), 16) % 10000).padStart(4, '0');

export function circleTag(c) {
  return `<span class="tag" title="${c.visibility === 'public' ? 'Public circle' : 'Private circle'}">${c.visibility === 'public' ? ICON.globe : ICON.lock} ${circleMark(c, 14)} ${esc(c.name)}</span>`;
}

/** Where a bet lives: its circle, or "Public" when anyone on the site can bet on it. */
export const whereHtml = (m, size = 13) => (m.circle
  ? `${circleMark(m.circle, size)} ${esc(m.circle.name)}`
  : `<span class="where-ico">${ICON.globe}</span> Public`);

export const bmButton = (id) => `<button class="bm ${isBookmarked(id) ? 'on' : ''}" data-bm="${id}" title="Bookmark" aria-label="Bookmark">${isBookmarked(id) ? ICON.bookmarkOn : ICON.bookmark}</button>`;

/** Builds the Yes/No (or per-outcome) choices for a slip. */
export function slipChoices(m, link) {
  const open = m.status === 'open';
  const O = m.outcomes;
  if (isYesNo(m)) {
    return `<div class="odds"><div class="od y"><span class="lbl">Yes</span><b class="num">${cents(O[0].yes)}</b></div><div class="od n"><span class="lbl">No</span><b class="num">${cents(O[1].yes)}</b></div></div>
      ${oddsBar(O[0].yes)}
      ${open ? `<div class="slip-btns"><button class="ybtn" data-go="${link(0, 'yes')}">Buy yes</button><button class="nbtn" data-go="${link(1, 'yes')}">Buy no</button></div>` : ''}`;
  }
  if (m.binary) {
    return `<div class="odds"><div class="od y"><span class="lbl ellipsis">${esc(O[0].name)}</span><b class="num">${cents(O[0].yes)}</b></div><div class="od n"><span class="lbl ellipsis">${esc(O[1].name)}</span><b class="num">${cents(O[1].yes)}</b></div></div>
      ${oddsBar(O[0].yes)}
      ${open ? `<div class="slip-btns"><button class="ybtn" data-go="${link(0, 'yes')}"><span class="ellipsis">${esc(O[0].name)}</span></button><button class="nbtn" data-go="${link(1, 'yes')}"><span class="ellipsis">${esc(O[1].name)}</span></button></div>` : ''}`;
  }
  const order = O.map((o, i) => ({ ...o, i })).sort((a, b) => b.yes - a.yes);
  return `<div class="orows">${order.slice(0, 4).map((o) => `<div class="orow"><span class="nm ellipsis">${esc(o.name)}</span><span class="opct num">${pctOf(o)}</span>
    ${open ? `<button class="ybtn sm" data-go="${link(o.i, 'yes')}">Yes</button><button class="nbtn sm" data-go="${link(o.i, 'no')}">No</button>` : ''}</div>`).join('')}
    ${order.length > 4 ? `<div class="more">+${order.length - 4} more on the slip</div>` : ''}</div>`;
}

export function marketCard(m, { fresh = false } = {}) {
  const isNew = Date.now() - m.createdAt < 86400000 && m.status === 'open';
  const link = (o, s) => `#/market/${m.id}?o=${o}&s=${s}`;
  const settled = m.status === 'resolved' || m.status === 'cancelled';
  const wide = !m.binary && m.outcomes.length >= 3;
  const stamp = m.status === 'resolved' ? `Settled · ${esc(m.outcomes[m.winner].name)}` : m.status === 'cancelled' ? 'Cancelled' : m.status === 'closed' ? 'Betting closed' : '';
  const ends = m.status === 'open' && m.closesAt ? `<span>Ends ${until(m.closesAt)}</span>` : '';
  return `<article class="mcard slip paper ${wide ? 'wide' : ''} ${settled || m.status === 'closed' ? 'settled' : ''} ${fresh ? 'pop' : ''}" data-id="${m.id}">
    <div class="slip-top"><span>${slipNo(m)} · ${esc(m.category)}</span>${isNew ? '<span class="tag new">New</span>' : ''}<span class="sp"></span>${bmButton(m.id)}</div>
    <div class="slip-body">
      <div class="slip-main">${thumb(m)}<h3 class="slip-q">${esc(m.question)}</h3></div>
      <div class="slip-pick">${slipChoices(m, link)}</div>
    </div>
    ${stamp ? `<span class="stamp slip-stamp">${stamp}</span>` : ''}
    <div class="slip-foot"><span>Vol. <b class="num">${vol(m.volume)}</b></span><span class="where ellipsis">${whereHtml(m)}</span><span class="sp"></span>${ends}</div>
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
    <div class="empty-copy">${kicker ? `<span class="kicker">${esc(kicker)}</span>` : ''}<h3>${title}</h3>${text ? `<p>${text}</p>` : ''}${actions ? `<div class="btns">${actions}</div>` : ''}</div></div>`;
}
