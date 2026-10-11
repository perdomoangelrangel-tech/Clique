/* A price chart for the Exchange: a line for the live view, candlesticks for the longer ones. Drawn as inline SVG, flat colours,
   with a hover readout. Nothing here knows where the numbers come from. */
import { t, intlLocale, CHIP_SIGN } from '../i18n.js';
import { esc } from '../util.js';

const fmtP = (p) => CHIP_SIGN + p.toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: p < 10 ? 3 : 2 });
const fmtT = (ts, span) => {
  const d = new Date(ts);
  if (span <= 3 * 3600e3) return d.toLocaleTimeString(intlLocale(), { hour: 'numeric', minute: '2-digit', second: span <= 15 * 60e3 ? '2-digit' : undefined });
  if (span <= 36 * 3600e3) return d.toLocaleTimeString(intlLocale(), { hour: 'numeric', minute: '2-digit' });
  return d.toLocaleDateString(intlLocale(), { month: 'short', day: 'numeric' }) + (span <= 8 * 86400e3 ? ' ' + d.toLocaleTimeString(intlLocale(), { hour: 'numeric' }) : '');
};

export function drawStockChart(host, { type = 'line', ticks = [], candles = [], height = 300 } = {}) {
  const W = Math.max(280, host.clientWidth || 640), H = height, PR = 62, PB = 26, PT = 12;
  const rows = type === 'candles' ? candles.map((c) => ({ t: c.t, o: c.o, h: c.h, l: c.l, c: c.c, gap: !!c.g })) : ticks.map(([t, p]) => ({ t, o: p, h: p, l: p, c: p }));
  if (rows.length < 2) { host.innerHTML = `<div class="sc-empty">${t('Juntando precios…')}</div>`; return null; }
  const lo0 = Math.min(...rows.map((r) => r.l)), hi0 = Math.max(...rows.map((r) => r.h));
  const pad = (hi0 - lo0 || hi0 * 0.002) * 0.12, lo = lo0 - pad, hi = hi0 + pad;
  const t0 = rows[0].t, t1 = rows[rows.length - 1].t + (type === 'candles' ? 0 : 0), span = Math.max(1, t1 - t0);
  const x = (at) => 6 + ((at - t0) / span) * (W - PR - 12);
  const y = (p) => PT + (1 - (p - lo) / (hi - lo)) * (H - PT - PB);
  const up = rows[rows.length - 1].c >= rows[0].o;
  const grid = [0, .25, .5, .75, 1].map((k) => { const p = lo + (hi - lo) * k; return `<line x1="0" x2="${W - PR}" y1="${y(p)}" y2="${y(p)}" stroke="var(--line-soft)" stroke-width="1.5" stroke-dasharray="${k === 0 ? '0' : '2 5'}"/><text x="${W - PR + 8}" y="${y(p) + 4}" fill="var(--text-3)" font-size="11" font-family="var(--f-mono)">${fmtP(p)}</text>`; }).join('');
  const nT = W < 400 ? 2 : W < 560 ? 3 : 5;      // a phone's chart has room for two time labels, not three
  const xl = Array.from({ length: nT }, (_, i) => { const k = i / (nT - 1), t = t0 + span * k; return `<text x="${Math.min(W - PR - 4, Math.max(6, x(t)))}" y="${H - 7}" fill="var(--text-3)" font-size="11" font-family="var(--f-mono)" text-anchor="${k === 0 ? 'start' : k === 1 ? 'end' : 'middle'}">${esc(fmtT(t, span))}</text>`; }).join('');
  let body;
  if (type === 'candles') {
    const bw = Math.max(1.5, Math.min(14, ((W - PR - 12) / rows.length) * 0.66));
    body = rows.map((r) => { const col = r.c >= r.o ? 'var(--pos)' : 'var(--neg)', cx = x(r.t); const top = y(Math.max(r.o, r.c)), bot = y(Math.min(r.o, r.c));
      return `<g ${r.gap ? 'opacity=".55"' : ''}><line x1="${cx}" x2="${cx}" y1="${y(r.h)}" y2="${y(r.l)}" stroke="${col}" stroke-width="1.5"/><rect x="${cx - bw / 2}" y="${top}" width="${bw}" height="${Math.max(1.5, bot - top)}" fill="${col}"/></g>`; }).join('');
  } else {
    const d = rows.map((r, i) => `${i ? 'L' : 'M'}${x(r.t).toFixed(1)} ${y(r.c).toFixed(1)}`).join('');
    const col = up ? 'var(--pos)' : 'var(--neg)', last = rows[rows.length - 1];
    body = `<path d="${d}L${x(last.t).toFixed(1)} ${H - PB}L${x(rows[0].t).toFixed(1)} ${H - PB}Z" fill="${col}" opacity=".10"/><path d="${d}" fill="none" stroke="${col}" stroke-width="2.4" stroke-linejoin="round"/>
      <circle cx="${x(last.t)}" cy="${y(last.c)}" r="4" fill="${col}" stroke="#0E0C0A" stroke-width="1.5"/>`;
  }
  const lastP = rows[rows.length - 1].c;
  host.innerHTML = `<div class="sc-wrap"><div class="sc-read" aria-live="off"></div><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(t('Gráfica de precio'))}">${grid}${xl}${body}${''/* html: seguro (grid, xl y body son SVG que arma este archivo con números) */}
    <line x1="0" x2="${W - PR}" y1="${y(lastP)}" y2="${y(lastP)}" stroke="${up ? 'var(--pos)' : 'var(--neg)'}" stroke-width="1" stroke-dasharray="1 3"/>
    <rect x="${W - PR + 2}" y="${y(lastP) - 9}" width="${PR - 4}" height="18" fill="${up ? 'var(--pos)' : 'var(--neg)'}"/><text x="${W - PR + 7}" y="${y(lastP) + 4}" fill="#0E0C0A" font-size="11" font-weight="700" font-family="var(--f-mono)">${fmtP(lastP)}</text>
    <line class="sc-cross" y1="${PT}" y2="${H - PB}" stroke="var(--text-2)" stroke-width="1" style="display:none"/><rect class="sc-hit" x="0" y="0" width="${W - PR}" height="${H}" fill="transparent"/></svg></div>`;
  const svg = host.querySelector('svg'), cross = host.querySelector('.sc-cross'), read = host.querySelector('.sc-read');
  const move = (ev) => {
    const r = svg.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * W;
    let best = rows[0], bd = Infinity;
    for (const row of rows) { const dd = Math.abs(x(row.t) - px); if (dd < bd) { bd = dd; best = row; } }
    cross.setAttribute('x1', x(best.t)); cross.setAttribute('x2', x(best.t)); cross.style.display = '';
    read.innerHTML = type === 'candles'
      ? `<b>${esc(fmtT(best.t, span))}</b> <span>O ${fmtP(best.o)}</span> <span>H ${fmtP(best.h)}</span> <span>L ${fmtP(best.l)}</span> <span>C ${fmtP(best.c)}</span>${best.gap ? ` <em>${t('(repetido mientras el servidor estuvo apagado)')}</em>` : ''}`
      : `<b>${esc(fmtT(best.t, span))}</b> <span>${fmtP(best.c)}</span>`;
  };
  host.querySelector('.sc-hit').addEventListener('mousemove', move);
  host.querySelector('.sc-hit').addEventListener('touchmove', (e) => move(e.touches[0]), { passive: true });
  host.querySelector('.sc-hit').addEventListener('mouseleave', () => { cross.style.display = 'none'; read.innerHTML = ''; });
  return { up };
}
