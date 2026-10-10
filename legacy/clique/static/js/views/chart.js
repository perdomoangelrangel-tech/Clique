import { esc, pct } from '../util.js';

export const RANGES = { '1H': 3600e3, '6H': 6 * 3600e3, '1D': 86400e3, '1W': 7 * 86400e3, '1M': 30 * 86400e3, ALL: Infinity };
export const COLORS = ['#C6F432', '#FF4B2B', '#EFE6D2', '#CFC3A8', '#2F6B47', '#A09482', '#F2EADB', '#8A2210'];

const fmtTick = (t, span) => {
  const d = new Date(t);
  if (span <= 15 * 60e3) return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });
  if (span <= 86400e3 * 1.5) return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

/** Step-line price chart with hover tooltip. series = [{idx, name, color}] */
export function drawChart(host, history, series, range, endTime, opts = {}) {
  const W = Math.max(280, host.clientWidth || 600), H = opts.height || 260, PR = 42, PB = 26, PT = 10;
  const now = endTime || Date.now();
  const span = RANGES[range];
  let t0 = span === Infinity ? history[0].t : now - span;
  if (now - t0 < 120000) t0 = now - 120000;
  const x = (t) => ((t - t0) / (now - t0)) * (W - PR);
  const y = (p) => PT + (1 - p) * (H - PT - PB);

  const lines = series.map((s) => {
    let before = history[0];
    const inside = [];
    for (const h of history) { if (h.t < t0) before = h; else inside.push(h); }
    const pts = [[t0, before.p[s.idx]], ...inside.map((h) => [h.t, h.p[s.idx]])];
    const last = pts[pts.length - 1];
    if (last[0] < now) pts.push([now, last[1]]);
    let d = `M${x(pts[0][0]).toFixed(1)} ${y(pts[0][1]).toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) d += `H${x(pts[i][0]).toFixed(1)}V${y(pts[i][1]).toFixed(1)}`;
    return { ...s, pts, d };
  });

  const grid = [0, .25, .5, .75, 1].map((p) => `<line x1="0" x2="${W - PR}" y1="${y(p)}" y2="${y(p)}" stroke="var(--line-soft)" stroke-width="1.5" stroke-dasharray="${p === 0 ? '0' : '2 5'}"/>
    <text x="${W - PR + 8}" y="${y(p) + 4}" fill="var(--text-3)" font-size="11" font-weight="500" font-family="var(--f-mono)">${Math.round(p * 100)}</text>`).join('');
  const ticks = (W - PR < 270 ? [0, 1] : W < 520 ? [0, .5, 1] : [0, .25, .5, .75, 1]).map((k) => {
    const t = t0 + (now - t0) * k;
    return `<text x="${Math.min(W - PR - 4, Math.max(14, x(t)))}" y="${H - 6}" fill="var(--text-3)" font-size="11" font-family="var(--f-mono)" text-anchor="${k === 0 ? 'start' : k === 1 ? 'end' : 'middle'}">${fmtTick(t, now - t0)}</text>`;
  }).join('');
  const paths = lines.map((l) => `<path d="${l.d}" fill="none" stroke="${l.color}" stroke-width="3" stroke-linejoin="miter" stroke-linecap="square"/>`).join('');
  const dots = lines.map((l) => `<rect class="cd" data-i="${l.idx}" width="11" height="11" fill="${l.color}" stroke="#0E0C0A" stroke-width="2" style="display:none"/>`).join('');
  const lastDots = lines.map((l) => { const p = l.pts[l.pts.length - 1]; return `<rect x="${x(p[0]) - 6}" y="${y(p[1]) - 6}" width="12" height="12" fill="${l.color}" stroke="#0E0C0A" stroke-width="2"><animate attributeName="opacity" values="1;.35;1" dur="1.6s" repeatCount="indefinite"/></rect>`; }).join('');

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${grid}${ticks}${paths}${lastDots}
    <line class="cv" y1="${PT}" y2="${H - PB}" stroke="var(--text-3)" stroke-width="1.5" stroke-dasharray="3 3" style="display:none"/>${dots}
    <rect class="hit" x="0" y="0" width="${W - PR}" height="${H}" fill="transparent"/></svg><div class="chart-tip hidden"></div>`;

  const svg = host.querySelector('svg'), tip = host.querySelector('.chart-tip'), vline = svg.querySelector('.cv');
  const valueAt = (l, t) => { let v = l.pts[0][1]; for (const p of l.pts) { if (p[0] <= t) v = p[1]; else break; } return v; };
  const hide = () => { tip.classList.add('hidden'); vline.style.display = 'none'; svg.querySelectorAll('.cd').forEach((c) => (c.style.display = 'none')); };
  svg.querySelector('.hit').addEventListener('pointermove', (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const t = t0 + (Math.max(0, Math.min(W - PR, px)) / (W - PR)) * (now - t0);
    vline.setAttribute('x1', px); vline.setAttribute('x2', px); vline.style.display = '';
    let rows = '';
    lines.forEach((l) => {
      const v = valueAt(l, t);
      const c = svg.querySelector(`.cd[data-i="${l.idx}"]`);
      c.setAttribute('x', px - 5.5); c.setAttribute('y', y(v) - 5.5); c.style.display = '';
      rows += `<div style="display:flex;gap:8px;align-items:center"><i style="width:9px;height:9px;background:${l.color};border:1.5px solid #0E0C0A;display:inline-block"></i>${esc(l.name)} <b>${pct(v)}</b></div>`;
    });
    tip.innerHTML = `<div class="muted" style="margin-bottom:3px">${new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</div>${rows}`;
    tip.classList.remove('hidden');
    tip.style.left = Math.max(60, Math.min(W - PR - 60, px)) + 'px';
    tip.style.top = (y(valueAt(lines[0], t)) - 4) + 'px';
  });
  svg.querySelector('.hit').addEventListener('pointerleave', hide);
}
