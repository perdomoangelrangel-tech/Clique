/* Wheel: 50 segments, each with a multiplier. The server picks the segment (uniformly, with its secure random source); the wheel
   here just spins to it. Four risk levels share the segments out differently, and all of them return 96% on average. */
import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX } from './common.js';
import { money, sleep, esc } from '../util.js';
import { toast } from '../ui.js';
import { t } from '../i18n.js';

const RISKS = [['low', 'Bajo'], ['medium', 'Medio'], ['high', 'Alto'], ['risky', 'Arriesgado']];      // i18n: claves
const riskName = (k) => { const r = RISKS.find(([id]) => id === k); return r ? t(r[1]) : k; };
const SIZE = 420, CX = 210, R_OUT = 198, R_IN = 82;
const TONES = ['#F2C230', '#5ED16B', '#4DABF7', '#FF8A3D', '#FF6B9D', '#B388FF'];          // from the smallest winning multiplier up
const ZERO = '#3A3530';
const rad = (deg) => (deg * Math.PI) / 180;
const reduced = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const key = (m) => Math.round(m * 100);                          // colours are looked up by the multiplier in cents, never by a float
function palette(layout) {
  const wins = [...new Set(layout.filter((m) => m > 0).map(key))].sort((a, b) => a - b);
  const map = new Map([[0, ZERO]]);
  wins.forEach((k, i) => map.set(k, TONES[i % TONES.length]));
  return map;
}

function wheelSvg(layout, colors) {
  const n = layout.length, seg = 360 / n;
  const pt = (r, deg) => `${(CX + r * Math.sin(rad(deg))).toFixed(2)} ${(CX - r * Math.cos(rad(deg))).toFixed(2)}`;
  const paths = layout.map((m, i) => {
    const a0 = i * seg, a1 = (i + 1) * seg;
    return `<path d="M${pt(R_OUT, a0)}A${R_OUT} ${R_OUT} 0 0 1 ${pt(R_OUT, a1)}L${pt(R_IN, a1)}A${R_IN} ${R_IN} 0 0 0 ${pt(R_IN, a0)}Z" fill="${colors.get(key(m))}" stroke="#0E0C0A" stroke-width="2"><title>${fmtX(m)}</title></path>`;
  }).join('');
  return `<svg class="wh-svg" viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${esc(t('La rueda'))}">
    <circle cx="${CX}" cy="${CX}" r="${R_OUT + 6}" fill="#1C1815" stroke="#0E0C0A" stroke-width="4"/>
    <g class="wh-rot" id="rot">${paths}</g>
    <circle cx="${CX}" cy="${CX}" r="${R_IN - 2}" fill="#141110" stroke="#0E0C0A" stroke-width="4"/>
    <polygon points="${CX - 16},4 ${CX + 16},4 ${CX},38" fill="#EFE6D2" stroke="#0E0C0A" stroke-width="4" stroke-linejoin="round"/></svg>`;
}

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const W = meta.wheel;
  host.innerHTML = `<div class="gm wheel">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>${t('Riesgo')}</label><div class="seg stretch" id="risk">${RISKS.map(([k, l]) => `<button data-r="${k}" class="${k === 'low' ? 'active' : ''}">${esc(t(l))}</button>`).join('')}</div></div>
      <button class="btn-bet" id="spin">${t('Girar')}</button>
      <div class="wh-table" id="table" aria-label="${esc(t('Lo que paga cada segmento'))}"></div>
      <div class="gm-note">${t('La rueda tiene 50 segmentos y el servidor elige uno al azar. El riesgo bajo tiene muchos premios chicos; Arriesgado casi no tiene, pero unos cuantos son enormes. Todos los niveles devuelven 96% en promedio.')}</div>
    </div>
    <div class="gm-stage wh-stage" id="stage">
      <div class="wh-hist" id="hist" aria-label="${esc(t('Giros recientes'))}"></div>
      <div class="wh-board" id="board"></div>
      <div class="wh-result" id="result" aria-live="polite"><b class="num" id="rx">${t('Gírala')}</b><small id="rs">${t('Elige un nivel de riesgo y una apuesta.')}</small></div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-wheel' });
  const stage = $('#stage'), board = $('#board'), spinBtn = $('#spin');
  let risk = 'low', busy = false, dead = false, rot = 0, rotEl = null, colors = null;
  const recent = [];

  function draw() {
    const R = W.risks[risk];
    colors = palette(R.layout);
    board.innerHTML = wheelSvg(R.layout, colors);
    rotEl = board.querySelector('#rot');
    rotEl.style.transform = `rotate(${rot}deg)`;
    $('#table').innerHTML = R.table.slice().sort((a, b) => a.mult - b.mult).map((r) => `<div class="wh-row"><i style="background:${colors.get(key(r.mult))}"></i><b class="num">${fmtX(r.mult)}</b><span class="num">${(r.chance * 100).toFixed(0)}%</span></div>`).join('');
  }
  const drawHist = () => {
    $('#hist').innerHTML = recent.slice(-9).map((h) => `<span class="num" style="background:${h.color}" title="${esc(riskName(h.risk))}: ${fmtX(h.mult)}">${h.mult > 0 ? h.mult.toFixed(2) + 'x' : '0x'}</span>`).join('');
  };
  function setUi() {
    bp.lock(busy);
    spinBtn.disabled = busy || !bp.valid();
    host.querySelectorAll('#risk button').forEach((b) => { b.disabled = busy; });
  }
  bp.onChange(() => { spinBtn.disabled = busy || !bp.valid(); });
  $('#risk').addEventListener('click', (e) => {
    const b = e.target.closest('[data-r]'); if (!b || busy) return;
    risk = b.dataset.r; host.querySelectorAll('#risk button').forEach((x) => x.classList.toggle('active', x === b)); draw();
    $('#rx').textContent = t('Gírala'); $('#rs').textContent = t('Riesgo {nivel}.', { nivel: b.textContent });
  });

  function spinTo(index) {
    const seg = 360 / W.segments, jitter = (Math.random() - 0.5) * seg * 0.6;
    const dur = reduced() ? 400 : 4600;
    rot = Math.ceil(rot / 360) * 360 + 5 * 360 - (index + 0.5) * seg + jitter;
    rotEl.style.transition = `transform ${dur}ms cubic-bezier(.12,.72,.14,1)`;
    rotEl.style.transform = `rotate(${rot}deg)`;
    return sleep(dur + 80);
  }

  spinBtn.addEventListener('click', async () => {
    if (busy || !bp.valid()) return;
    const amount = bp.value(); busy = true; setUi();
    const prev = deduct(amount);
    $('#rx').textContent = '…'; $('#rs').textContent = t('No va más.');
    try {
      const res = await post('/api/games/wheel', { risk, amount });
      await spinTo(res.index);
      if (dead) return;
      const color = colors.get(key(res.mult));
      recent.push({ mult: res.mult, color, risk }); drawHist();
      $('#rx').textContent = res.mult > 0 ? fmtX(res.mult) : t('Sin suerte');
      $('#rs').textContent = res.mult > 0 ? t('Pagó {cantidad}', { cantidad: money(res.payout) }) : t('La rueda se lo queda.');
      const r = stage.getBoundingClientRect();
      if (res.win) burst(stage, r.width / 2, r.height / 2, { count: res.mult >= 5 ? 80 : 36, power: res.mult >= 5 ? 380 : 260 });
      else if (res.mult === 0) { shake(stage); stage.classList.add('flash-red'); setTimeout(() => stage.classList.remove('flash-red'), 450); }
      resultPop({ net: res.payout - amount, label: t('Riesgo {nivel}', { nivel: riskName(risk) }), detail: res.mult > 0 ? fmtX(res.mult) : t('sin suerte'), bet: amount });
      setUser(res.user); ctx.refreshBets?.();
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); $('#rx').textContent = t('Gírala'); $('#rs').textContent = ''; }
    busy = false; setUi();
  });

  draw(); drawHist(); setUi();
  return { unmount() { dead = true; bp.destroy(); } };
}
