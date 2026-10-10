import { esc, money, cents, avatar } from '../util.js';

/**
 * "Who's in": every person holding a slip on this bet, what they put in and what they backed.
 * Biggest stake first. Totals per side sit on top so you can see where the money is leaning.
 */
export function whoseIn(M) {
  const rows = M.holders;
  if (!rows.length) return '<p class="quiet">Nobody has put money on this yet. Be the first mistake.</p>';
  const people = new Set(rows.map((h) => h.user.username)).size;
  const sides = new Map();
  for (const h of rows) {
    const s = sides.get(h.label) || { label: h.label, side: h.side, total: 0, n: 0 };
    s.total += h.invested; s.n += 1; sides.set(h.label, s);
  }
  const top = [...sides.values()].sort((a, b) => b.total - a.total);
  const settled = rows.some((h) => h.settled);
  return `<div class="whosin-sum"><span><b class="num">${money(M.investedTotal)}</b> in play from <b>${people}</b> ${people === 1 ? 'person' : 'people'}</span>
      ${top.map((s) => `<span class="tag ${s.side === 'yes' ? 'good' : 'bad'}">${esc(s.label)} <b class="num">${money(s.total)}</b> · ${s.n}</span>`).join('')}</div>
    <div class="card-box tbl-wrap"><table class="tbl whosin"><thead><tr><th>Who</th><th>Backed</th><th class="r">Put in</th><th class="r">Avg price</th><th class="r">${settled ? 'Paid' : 'Worth now'}</th></tr></thead><tbody>
    ${rows.map((h) => `<tr><td><a class="row" href="#/u/${esc(h.user.username)}" style="gap:10px;font-weight:600">${avatar(h.user.username, 26)}<span>${esc(h.user.username)}</span></a></td>
      <td><span class="tag ${h.side === 'yes' ? 'good' : 'bad'}">${esc(h.label)}</span></td>
      <td class="r num"><b>${money(h.invested)}</b></td><td class="r num">${cents(h.avgPrice)}</td>
      <td class="r num ${h.pnl > 0 ? 'up' : h.pnl < 0 ? 'down' : ''}">${h.value == null ? '—' : money(h.value)}</td></tr>`).join('')}
    </tbody></table></div>`;
}
