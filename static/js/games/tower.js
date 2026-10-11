import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX, progressHtml, paintProgress } from './common.js';
import { money, sleep, esc } from '../util.js';
import { glyph } from '../art.js';
import { toast } from '../ui.js';
import { t, tp } from '../i18n.js';

const svg = (name) => `<svg viewBox="0 0 64 64" aria-hidden="true">${glyph(name)}</svg>`;
const COIN = svg('coin'), TRAP = svg('flame');
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
const LABEL = { easy: 'Fácil', medium: 'Medio', hard: 'Difícil', expert: 'Experto', master: 'Maestro' };      // i18n: claves

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const ROWS = meta.tower.rows, RISKS = meta.tower.risks;
  host.innerHTML = `<div class="gm tower">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label for="risk">${t('Riesgo')}</label>
        <select class="gm-select" id="risk">${Object.keys(RISKS).map((k) => `<option value="${k}">${esc(LABEL[k] ? t(LABEL[k]) : k)}</option>`).join('')}</select>
        <small class="muted" id="risk-info"></small></div>
      ${progressHtml()}
      <button class="btn-bet" id="go">${t('Apostar')}</button>
      <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      <div class="gm-note">${t('Sube {n} filas. Elige una casilla por fila: si es segura, subes; si es trampa, te caes. Plántate después de cualquier fila. Las torres más seguras pagan menos por piso.', { n: ROWS })}</div>
    </div>
    <div class="gm-stage tw-stage" id="stage"><div class="tw-tower" id="tower"></div><div class="tw-msg" id="msg">${t('Elige un riesgo. Empieza a subir.')}</div></div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-tower' });
  const stage = $('#stage'), tower = $('#tower'), msg = $('#msg'), go = $('#go'), cash = $('#cash'), riskSel = $('#risk');
  let risk = 'easy', game = null, busy = false, dead = false;
  const say = (text) => { msg.textContent = text; };
  const tile = (r, c) => tower.querySelector(`.tw-tile[data-r="${r}"][data-c="${c}"]`);
  const step = () => (game ? game.step : 0);

  function build(picks = []) {
    const R = RISKS[risk];
    tower.style.setProperty('--cols', R.cols);
    let html = '';
    for (let r = ROWS - 1; r >= 0; r--) {
      html += `<div class="tw-row" data-r="${r}"><span class="tw-mult num">${fmtX(R.mults[r + 1])}</span><div class="tw-tiles">${Array.from({ length: R.cols }, (_, c) => `<button class="tw-tile" data-r="${r}" data-c="${c}" aria-label="${esc(t('Fila {fila}, casilla {n}', { fila: r + 1, n: c + 1 }))}"></button>`).join('')}</div></div>`;
    }
    tower.innerHTML = html;
    picks.forEach((c, r) => mark(r, c, 'safe', true));
    setNow();
  }
  function mark(r, c, kind, instant = false, ghost = false) {
    const tileEl = tile(r, c); if (!tileEl) return;
    tileEl.className = `tw-tile ${kind} ${ghost ? 'ghost' : ''} ${instant ? '' : 'pop'}`; tileEl.innerHTML = kind === 'trap' ? TRAP : COIN; tileEl.disabled = true;
  }
  function setNow() {
    tower.querySelectorAll('.tw-row').forEach((row) => {
      const r = +row.dataset.r;
      row.classList.toggle('now', !!game && r === step());
      row.classList.toggle('done', !!game && r < step());
    });
  }
  function reveal(layout) {          // show every trap, and the safe tiles in the rows you never reached
    layout.forEach((traps, r) => {
      for (let c = 0; c < RISKS[risk].cols; c++) { const tileEl = tile(r, c); if (tileEl && !tileEl.disabled) mark(r, c, traps.includes(c) ? 'trap' : 'safe', true, true); }
    });
  }
  function paint() {
    const R = RISKS[risk], active = !!game;
    $('#risk-info').textContent = tp(R.traps, '{casillas} casillas por fila, {n} trampa · la primera fila paga {x}', '{casillas} casillas por fila, {n} trampas · la primera fila paga {x}', { casillas: R.cols, x: fmtX(R.mults[1]) });
    paintProgress(host, { bet: game ? game.bet : bp.value(), mult: game && game.step ? game.mult : null, nextMult: game ? game.nextMult : R.mults[1] });
    go.classList.toggle('hidden', active); cash.classList.toggle('hidden', !active);
    bp.lock(active || busy); riskSel.disabled = active || busy;
    cash.disabled = busy || !active || !game.step;
    cash.textContent = active && game.step ? t('Plantarme con {cantidad}', { cantidad: money(game.payoutNow) }) : t('Plantarme');
    go.disabled = busy || !bp.valid();
    tower.classList.toggle('live', active && !busy);
    setNow();
  }
  bp.onChange(paint);
  riskSel.addEventListener('change', () => { if (game || busy) return; risk = riskSel.value; build(); paint(); });

  async function settle(res, win) {
    if (res.layout) reveal(res.layout);
    setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; paint();
    await sleep(win ? 2000 : 2300); if (dead) return;
    busy = false; build(); say(t('Elige un riesgo. Empieza a subir.')); paint();
  }

  go.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; paint();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/tower/start', { amount, risk });
      setUser(res.user); game = res; build(); say(t('Fila de abajo. Elige una casilla.'));
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  tower.addEventListener('click', async (e) => {
    const tileEl = e.target.closest('.tw-tile'); if (!tileEl || !game || busy || tileEl.disabled || +tileEl.dataset.r !== step()) return;
    busy = true; paint();
    const r = +tileEl.dataset.r, c = +tileEl.dataset.c;
    try {
      const res = await post('/api/games/tower/pick', { tile: c });
      const b = tileEl.getBoundingClientRect(), s = stage.getBoundingClientRect(), x = b.left - s.left + b.width / 2, y = b.top - s.top + b.height / 2;
      if (res.crashed) {
        mark(r, c, 'trap'); shake(stage); burst(stage, x, y, { count: 30, power: 250, colors: ['#FF4B2B', '#EFE6D2', '#0E0C0A'] });
        say(t('Trampa. Te caíste de la fila {n}. Pierdes {cantidad}.', { n: r + 1, cantidad: money(game.bet) }));
        resultPop({ net: -game.bet, label: t('Caíste en la fila {n}', { n: r + 1 }) });
        return settle(res, false);
      }
      mark(r, c, 'safe'); burst(stage, x, y, { count: 10, power: 140, size: 7, colors: ['#C6F432', '#EFE6D2'], life: 650 });
      game = { ...game, ...res };
      if (res.finished) {
        say(t('La cima de la torre. {x}. Mírate nada más.', { x: fmtX(res.mult) }));
        resultPop({ net: res.payout - game.bet, label: t('Llegaste a la cima'), detail: fmtX(res.mult), bet: game.bet });
        const rr = stage.getBoundingClientRect(); burst(stage, rr.width / 2, rr.height / 2, { count: 70, power: 360, colors: WIN_COLORS });
        return settle(res, true);
      }
      say(t('Fila {n} superada. {x} · {cantidad} si te plantas.', { n: res.step, x: fmtX(res.mult), cantidad: money(res.payoutNow) }));
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  cash.addEventListener('click', async () => {
    if (busy || !game || !game.step) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/tower/cashout', {});
      say(t('Te llevas {cantidad}. Que la torre se quede con lo demás.', { cantidad: money(res.payout) }));
      resultPop({ net: res.payout - game.bet, label: t('Te plantaste en {x}', { x: fmtX(res.mult) }), bet: game.bet });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.45, { count: 46, power: 300, colors: WIN_COLORS });
      return settle(res, true);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  try {
    const cur = await get('/api/games/state');
    if (cur.tower && !dead) {
      game = cur.tower; risk = game.risk; riskSel.value = risk; build(game.picks);
      say(game.step ? t('Bienvenido de vuelta. Fila {n} lista, {x} · {cantidad} si te plantas.', { n: game.step, x: fmtX(game.mult), cantidad: money(game.payoutNow) }) : t('Fila de abajo. Elige una casilla.'));
    } else build();
  } catch { build(); }
  paint();
  return { unmount() { dead = true; bp.destroy(); } };
}
