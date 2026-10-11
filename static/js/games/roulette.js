import { post } from '../api.js';
import { S, bus, setUser, refreshMe, balanceNow } from '../state.js';
import { deduct, burst, resultPop, countUp } from './common.js';
import { money, parseAmount, ICON, esc } from '../util.js';
import { toast } from '../ui.js';
import { t, CHIP_SIGN, intlLocale } from '../i18n.js';

const COLOR = { red: 'rojo', black: 'negro', green: 'verde' };      // i18n: claves

const ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
const REDS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
const colorOf = (n) => (n === 0 ? 'green' : REDS.has(n) ? 'red' : 'black');
const STEP = 360 / 37, CX = 160, CY = 160;
const pt = (a, r) => { const rad = (a * Math.PI) / 180; return [CX + r * Math.sin(rad), CY - r * Math.cos(rad)]; };
const CHIPS = [0.1, 1, 5, 10, 25, 100, 500];
const chipLabel = (v) => (v >= 1000 ? `${v / 1000}K` : String(v));

function wheelSvg() {
  const R1 = 124, R2 = 86;
  let wedges = '', nums = '';
  ORDER.forEach((n, i) => {
    const a0 = (i - 0.5) * STEP, a1 = (i + 0.5) * STEP;
    const [x0, y0] = pt(a0, R2), [x1, y1] = pt(a0, R1), [x2, y2] = pt(a1, R1), [x3, y3] = pt(a1, R2);
    wedges += `<path d="M${x0} ${y0}L${x1} ${y1}A${R1} ${R1} 0 0 1 ${x2} ${y2}L${x3} ${y3}A${R2} ${R2} 0 0 0 ${x0} ${y0}Z" class="pk ${colorOf(n)}" data-n="${n}"/>`;
    nums += `<text x="${CX}" y="${CY - 104}" transform="rotate(${i * STEP} ${CX} ${CY})" class="pn">${n}</text>`;
  });
  return `<svg viewBox="0 0 320 320" class="wheel-svg">
    <circle cx="160" cy="160" r="156" fill="#2A2420" stroke="#0E0C0A" stroke-width="3"/><circle cx="160" cy="160" r="141" fill="#0E0C0A" stroke="#EFE6D2" stroke-width="3"/>
    <g id="wheel">${wedges}${nums}<circle cx="160" cy="160" r="84" fill="#1C1815" stroke="#EFE6D2" stroke-width="3"/>
      <g stroke="#C6F432" stroke-width="5" stroke-linecap="round"><path d="M160 104v112M104 160h112"/></g><circle cx="160" cy="160" r="17" fill="#C6F432" stroke="#0E0C0A" stroke-width="3.5"/><circle cx="160" cy="160" r="6" fill="#0E0C0A"/></g>
    <circle id="ball" r="6.5" cx="160" cy="24" fill="#EFE6D2" stroke="#0E0C0A" stroke-width="2"/><circle id="ball-hl" r="0" cx="159" cy="22" fill="#fff"/></svg>`;
}

function tableHtml() {
  let cells = '';
  cells += `<div class="rc green" data-bet="straight:0" style="grid-column:1;grid-row:1/4"><span>0</span></div>`;
  for (let n = 1; n <= 36; n++) {
    const col = Math.ceil(n / 3) + 1, row = 3 - ((n - 1) % 3);
    cells += `<div class="rc ${colorOf(n)}" data-bet="straight:${n}" style="grid-column:${col};grid-row:${row}"><span>${n}</span></div>`;
  }
  [3, 2, 1].forEach((c, i) => { cells += `<div class="rc out" data-bet="column:${c}" style="grid-column:14;grid-row:${i + 1}"><span>2:1</span></div>`; });
  [[t('1 a 12'), 1], [t('13 a 24'), 2], [t('25 a 36'), 3]].forEach(([l, d], i) => { cells += `<div class="rc out" data-bet="dozen:${d}" style="grid-column:${2 + i * 4}/span 4;grid-row:4"><span>${esc(l)}</span></div>`; });
  [[t('1 a 18'), 'low', ''], [t('Par'), 'even', ''], ['', 'red', 'red'], ['', 'black', 'black'], [t('Impar'), 'odd', ''], [t('19 a 36'), 'high', '']].forEach(([l, kind, c], i) => {
    cells += `<div class="rc out ${c}" data-bet="${kind}" style="grid-column:${2 + i * 2}/span 2;grid-row:5"><span>${c ? '<i class="diamond ' + c + '"></i>' : esc(l)}</span></div>`;
  });
  return cells;
}

export default async function mount(host, ctx = {}) {
  host.innerHTML = `<div class="gm roulette">
    <div class="gm-panel">
      <div class="gm-field"><label>${t('Total en la mesa')}</label><div class="gm-ro lg"><span>${CHIP_SIGN}</span><input id="total" readonly value="0.00"></div></div>
      <div class="gm-field"><label>${t('Último pago')}</label><div class="gm-ro"><span>${CHIP_SIGN}</span><input id="payout" readonly value="0.00"><em id="payx">0.00x</em></div></div>
      <button class="btn-bet" id="go">${t('Girar')}</button>
      <div class="rl-tools"><button class="mini" id="clear">${t('Limpiar la mesa')}</button><button class="mini" id="x2">${t('Doblar todo')}</button></div>
      <div class="bp-err" id="rl-err"></div>
      <div class="gm-note">${t('Elige una ficha, toca la mesa y apila lo que te atrevas. Un número solo paga 35 a 1. Clic derecho en un lugar para quitar tus fichas.')}</div>
    </div>
    <div class="gm-stage rl-stage" id="stage">
      <div class="rl-top"><div class="wheel-wrap" id="wheel-wrap">${wheelSvg()}<div class="rl-result hidden" id="result"></div></div>
        <div class="rl-hist" id="hist"></div></div>
      <p class="board-hint" aria-hidden="true">${t('La mesa es más ancha que tu pantalla: deslízala de lado.')}</p>
      <div class="rl-board">
        <button class="rl-side" id="undo" title="${esc(t('Deshacer'))}">${ICON.undo}</button>
        <div class="rl-table-wrap board-scroll" tabindex="0" role="group" aria-label="${esc(t('Mesa de ruleta (se desliza de lado)'))}"><div class="rl-table" id="table">${tableHtml()}</div></div>
        <button class="rl-side" id="rebet" title="${esc(t('Repetir tus últimas apuestas'))}">${ICON.redo}</button>
      </div>
      <div class="rl-chips" id="chips">${CHIPS.map((v) => `<button class="rchip v${String(v).replace('.', '_')}" data-v="${v}" title="${money(v)}"><span>${chipLabel(v)}</span></button>`).join('')}
        <button class="rchip custom" id="chip-custom" title="${esc(t('Valor de ficha a tu gusto'))}">${ICON.pencil}</button>
        <input class="chip-in hidden" id="chip-in" inputmode="decimal" placeholder="0.00" autocomplete="off" aria-label="${esc(t('Valor de ficha a tu gusto'))}"></div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const stage = $('#stage'), table = $('#table'), wheel = $('#wheel'), ball = $('#ball'), ballHl = $('#ball-hl'), go = $('#go'), err = $('#rl-err');
  let bets = new Map(), stack = [], lastBets = null, busy = false, dead = false, chipVal = 1;
  const hist = [];

  // ------------------------------------------------------------ chips
  const markChip = () => {
    host.querySelectorAll('.rchip[data-v]').forEach((c) => c.classList.toggle('sel', Number(c.dataset.v) === chipVal));
    $('#chip-custom').classList.toggle('sel', !CHIPS.includes(chipVal));
  };
  $('#chips').addEventListener('click', (e) => {
    const c = e.target.closest('.rchip[data-v]');
    if (c) { chipVal = Number(c.dataset.v); $('#chip-in').classList.add('hidden'); markChip(); return; }
    if (e.target.closest('#chip-custom')) { const i = $('#chip-in'); i.classList.toggle('hidden'); if (!i.classList.contains('hidden')) i.focus(); }
  });
  $('#chip-in').addEventListener('input', (e) => {
    let v = e.target.value.replace(/[^\d.]/g, ''); const p = v.split('.'); if (p.length > 2) v = p[0] + '.' + p.slice(1).join('');
    if (v.includes('.')) { const [a, b] = v.split('.'); v = a + '.' + b.slice(0, 2); }
    e.target.value = v;
    const n = parseAmount(v);
    if (n >= S.minBet - 1e-9) { chipVal = Math.round(n * 100) / 100; err.textContent = ''; } else err.textContent = v ? t('La ficha más chica es {cantidad}.', { cantidad: money(S.minBet) }) : '';
    markChip();
  });
  markChip();

  // ------------------------------------------------------------ bets
  const total = () => Math.round([...bets.values()].reduce((a, b) => a + b, 0) * 100) / 100;
  const chipClass = (v) => ['c1', 'c2', 'c3', 'c4', 'c5'][Math.max(0, Math.min(4, Math.floor(Math.log10(Math.max(0.1, v)) + 1)))];
  const fmtChip = (v) => (v >= 10000 ? money(v, { noCents: true }).replace('$', '') : Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/0$/, ''));
  function drawChips() {
    table.querySelectorAll('.chip').forEach((c) => c.remove());
    for (const [k, v] of bets) {
      const cell = table.querySelector(`[data-bet="${k}"]`); if (!cell) continue;
      const c = document.createElement('div'); c.className = `chip ${chipClass(v)}`; c.textContent = fmtChip(v); c.title = money(v); cell.appendChild(c);
    }
    const tot = total(); $('#total').value = tot.toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const over = tot > balanceNow() + 1e-9;
    go.disabled = busy || !bets.size || over;
    $('#total').closest('.gm-ro').classList.toggle('bad', over);
    const short = t('No te alcanzan las fichas. Agrega fichas o apuesta menos.');
    if (over) err.textContent = short; else if (err.textContent === short) err.textContent = '';
  }
  const onUser = () => drawChips();
  bus.addEventListener('user', onUser);

  table.addEventListener('click', (e) => {
    if (busy) return;
    const cell = e.target.closest('[data-bet]'); if (!cell) return;
    if (!(chipVal >= S.minBet - 1e-9)) { toast(t('La ficha más chica es {cantidad}.', { cantidad: money(S.minBet) }), 'err'); return; }
    const k = cell.dataset.bet;
    bets.set(k, Math.round(((bets.get(k) || 0) + chipVal) * 100) / 100); stack.push({ k, v: chipVal }); drawChips();
  });
  table.addEventListener('contextmenu', (e) => {
    const cell = e.target.closest('[data-bet]'); if (!cell || busy) return; e.preventDefault();
    bets.delete(cell.dataset.bet); stack = stack.filter((s) => s.k !== cell.dataset.bet); drawChips();
  });
  $('#undo').addEventListener('click', () => { if (busy) return; const s = stack.pop(); if (!s) return; const nv = Math.round(((bets.get(s.k) || 0) - s.v) * 100) / 100; if (nv > 0.0001) bets.set(s.k, nv); else bets.delete(s.k); drawChips(); });
  $('#clear').addEventListener('click', () => { if (busy) return; bets.clear(); stack = []; drawChips(); });
  $('#rebet').addEventListener('click', () => { if (busy || !lastBets) return; bets = new Map(lastBets); stack = [...bets].map(([k, v]) => ({ k, v })); drawChips(); });
  $('#x2').addEventListener('click', () => { if (busy) return; for (const [k, v] of bets) bets.set(k, Math.round(v * 200) / 100); stack = [...bets].map(([k, v]) => ({ k, v })); drawChips(); });

  // ------------------------------------------------------------ wheel animation
  const R_TRACK = 134, R_POCKET = 106;
  let wheelAngle = 0, ballRel = 0, ballR = R_POCKET, mode = 'idle', last = performance.now();
  function place() {
    wheel.setAttribute('transform', `rotate(${wheelAngle} ${CX} ${CY})`);
    const [x, y] = pt(wheelAngle + ballRel, ballR);
    ball.setAttribute('cx', x); ball.setAttribute('cy', y); ballHl.setAttribute('cx', x - 1.6); ballHl.setAttribute('cy', y - 2);
  }
  function idle(now) {
    if (dead) return;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (mode === 'idle') { wheelAngle = (wheelAngle - 7 * dt) % 360; place(); }
    requestAnimationFrame(idle);
  }
  requestAnimationFrame(idle);

  function spinTo(n) {
    return new Promise((resolve) => {
      mode = 'spin';
      const phiF = ORDER.indexOf(n) * STEP, w0 = wheelAngle, wTurn = -(360 * 3 + Math.random() * 90), turns = 7, dur = 6200, t0 = performance.now();
      const step = (now) => {
        if (dead) return resolve();
        const k = Math.min(1, (now - t0) / dur);
        wheelAngle = w0 + wTurn * (1 - Math.pow(1 - k, 2));
        const eb = 1 - Math.pow(1 - k, 2.6);
        ballRel = phiF - (1 - eb) * turns * 360;
        if (k < 0.6) ballR = R_TRACK;
        else if (k < 0.86) { const q = (k - 0.6) / 0.26; ballR = R_TRACK - (R_TRACK - R_POCKET) * q * q * (3 - 2 * q) + Math.sin(q * 18) * 3 * (1 - q); }
        else { const q = (k - 0.86) / 0.14; ballR = R_POCKET - Math.abs(Math.sin(q * 11)) * 7 * (1 - q) ** 2; }
        place();
        if (k < 1) return requestAnimationFrame(step);
        ballRel = phiF; ballR = R_POCKET; place(); wheelAngle %= 360; mode = 'idle'; last = performance.now();
        resolve();
      };
      requestAnimationFrame(step);
    });
  }

  function drawHist() { $('#hist').innerHTML = hist.slice(0, 12).map((n) => `<span class="hn ${colorOf(n)}">${n}</span>`).join(''); }

  async function spin() {
    if (busy || !bets.size) return;
    if (total() > balanceNow() + 1e-9) return toast(t('No te alcanzan las fichas.'), 'err');
    busy = true; go.disabled = true; table.classList.add('locked');
    const payload = [...bets].map(([k, amount]) => { const [type, v] = k.split(':'); return { type, value: v === undefined ? undefined : parseInt(v, 10), amount }; });
    lastBets = new Map(bets);
    const prev = deduct(t);
    $('#result').classList.add('hidden'); table.querySelectorAll('.win').forEach((c) => c.classList.remove('win'));
    try {
      const res = await post('/api/games/roulette', { bets: payload });
      await spinTo(res.number);
      const r = $('#result'); r.className = `rl-result ${res.color}`; r.textContent = res.number; r.classList.remove('hidden');
      hist.unshift(res.number); drawHist();
      table.querySelector(`[data-bet="straight:${res.number}"]`)?.classList.add('win');
      res.wins.forEach((w) => table.querySelector(`[data-bet="${w.type}${w.value !== null && w.value !== undefined && ['straight', 'dozen', 'column'].includes(w.type) ? ':' + w.value : ''}"]`)?.classList.add('win'));
      $('#payout').value = res.payout.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      $('#payx').textContent = (res.total ? res.payout / res.total : 0).toFixed(2) + 'x';
      const net = Math.round((res.payout - res.total) * 100) / 100;
      resultPop({ net, label: `${res.number} ${COLOR[res.color] ? t(COLOR[res.color]) : res.color}`, detail: res.payout > 0 ? t('Pagó {cantidad}', { cantidad: money(res.payout) }) : '', bet: res.total });
      if (net > 0) { const rect = stage.getBoundingClientRect(); burst(stage, rect.width * 0.5, rect.height * 0.3, { count: 50, power: 320 }); }
      setUser(res.user); ctx.refreshBets?.();
      bets.clear(); stack = [];
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); mode = 'idle'; }
    busy = false; table.classList.remove('locked'); drawChips();
  }
  go.addEventListener('click', spin);
  drawChips();
  return { unmount() { dead = true; bus.removeEventListener('user', onUser); } };
}
