import { esc, money, moneyFull } from '../util.js';

/**
 * "Where your money sits": a flat stacked bar of cash plus open bets, switchable between
 * market / category / circle. Segments differ by fill pattern as well as colour.
 */
const VIEWS = [['byMarket', 'Market'], ['byCategory', 'Category'], ['byCircle', 'Circle']];
const FILLS = ['var(--lime)', 'var(--verm)', '#EFE6D2', '#2F6B47', '#CFC3A8', '#B8200A', '#4C6300', '#8C8171'];
const PATTERNS = ['', 'p-dots', 'p-stripes', 'p-checker'];
const MAX_SEGMENTS = 7;
const share = (v, total) => (total > 0 ? (v / total) * 100 : 0);
const fmtPct = (p) => (p >= 10 ? p.toFixed(0) : p.toFixed(1)) + '%';

function segments(dist, view) {
  const rows = dist[view].filter((g) => g.value > 0);
  const shown = rows.slice(0, MAX_SEGMENTS), rest = rows.slice(MAX_SEGMENTS);
  const out = [{ label: 'Cash', value: dist.cash, cash: true }, ...(dist.poker > 0 ? [{ label: 'At the poker table', value: dist.poker, invested: dist.poker }] : []), ...shown];
  if (rest.length) out.push({ label: `${rest.length} smaller`, value: rest.reduce((a, g) => a + g.value, 0), invested: rest.reduce((a, g) => a + g.invested, 0) });
  return out.filter((s) => s.value > 0).map((s, i) => ({ ...s, fill: FILLS[i % FILLS.length], pattern: PATTERNS[i % PATTERNS.length] }));
}

export function mountSpread(host, dist, { go } = {}) {
  let view = 'byMarket';
  const draw = () => {
    const total = dist.total;
    const segs = segments(dist, view);
    const cashPct = share(dist.cash, total), openN = dist.byMarket.length;
    const biggest = dist.byMarket[0];
    const line = !dist.invested
      ? 'All cash. No open bets. Brave, or boring.'
      : `<b>${fmtPct(cashPct)}</b> cash. <b>${fmtPct(100 - cashPct)}</b> riding on <b>${openN}</b> open bet${openN === 1 ? '' : 's'}.${biggest && share(biggest.value, total) >= 25 ? ` Your biggest slip is <b>${fmtPct(share(biggest.value, total))}</b> of everything you own.` : ''}`;
    host.innerHTML = `<section class="spread card-box">
      <div class="spread-head"><div><span class="kicker">Portfolio</span><h2>Where your money sits</h2></div>
        <div class="seg" id="spread-seg" role="tablist" aria-label="Group by">${VIEWS.map(([k, l]) => `<button type="button" data-v="${k}" class="${view === k ? 'active' : ''}">${l}</button>`).join('')}</div></div>
      <p class="spread-line">${line}</p>
      <div class="spread-bar" role="img" aria-label="${esc(segs.map((s) => `${s.label} ${fmtPct(share(s.value, total))}`).join(', '))}">
        ${segs.map((s) => `<i class="${s.pattern}" style="flex:${Math.max(s.value, total * 0.012)};--fill:${s.fill}" title="${esc(s.label)}: ${moneyFull(s.value)}"></i>`).join('')}</div>
      <div class="spread-legend">${segs.map((s) => `<div class="spread-row ${s.key && view === 'byMarket' ? 'link' : ''}" ${s.key && view === 'byMarket' ? `data-m="${s.key}"` : ''}>
          <i class="sw ${s.pattern}" style="--fill:${s.fill}"></i><span class="nm ellipsis">${esc(s.label)}</span>
          <span class="inv num">${s.cash ? 'spendable' : s.invested != null ? `put in ${money(s.invested)}` : ''}</span>
          <b class="val num" title="${moneyFull(s.value)}">${money(s.value)}</b><span class="share num">${fmtPct(share(s.value, total))}</span></div>`).join('')}</div>
    </section>`;
  };
  draw();
  host.addEventListener('click', (e) => {
    const b = e.target.closest('#spread-seg [data-v]');
    if (b) { view = b.dataset.v; draw(); return; }
    const r = e.target.closest('[data-m]');
    if (r && go) go(`#/market/${r.dataset.m}`);
  });
}
