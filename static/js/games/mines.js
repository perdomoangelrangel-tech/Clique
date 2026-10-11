import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX, progressHtml, paintProgress } from './common.js';
import { money, sleep, debounce, esc } from '../util.js';
import { glyph } from '../art.js';
import { toast } from '../ui.js';
import { t } from '../i18n.js';

const svg = (name) => `<svg viewBox="0 0 64 64" aria-hidden="true">${glyph(name)}</svg>`;
const GEM = svg('gem'), BOMB = svg('bomb');
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const SIZES = meta.mines.sizes;
  host.innerHTML = `<div class="gm mines">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>${t('Tamaño de la cuadrícula')}</label><div class="seg stretch" id="sizes">${SIZES.map((n) => `<button data-n="${n}" class="${n === 25 ? 'active' : ''}">${n}</button>`).join('')}</div></div>
      <div class="gm-field"><label for="mines">${t('Minas')}</label>
        <div class="mn-range"><span class="mn-count"><i class="mn-ico">${GEM}</i><b id="gems">22</b></span>
          <input type="range" class="gm-range" id="mines" min="1" max="24" value="3">
          <span class="mn-count bomb"><b id="mcount">3</b><i class="mn-ico">${BOMB}</i></span></div></div>
      ${progressHtml()}
      <button class="btn-bet" id="go">${t('Apostar')}</button>
      <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      <button class="mini hidden" id="rand">${t('Abrir una casilla al azar')}</button>
      <div class="gm-note">${t('Abre casillas seguras para subir. Plántate cuando quieras después de la primera. Si abres una bomba, se acabó. Más bombas, más salto por casilla.')}</div>
    </div>
    <div class="gm-stage mn-stage" id="stage"><div class="mn-grid" id="grid"></div><div class="mn-msg" id="msg">${t('Elige cuadrícula, elige tu miedo, dale a Apostar.')}</div></div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-mines' });
  const stage = $('#stage'), grid = $('#grid'), msg = $('#msg'), go = $('#go'), cash = $('#cash'), rand = $('#rand'), range = $('#mines'), sizesEl = $('#sizes');
  let size = 25, mines = 3, game = null, busy = false, dead = false, table = [];

  const side = () => Math.round(Math.sqrt(size));
  const say = (text) => { msg.textContent = text; };
  const tile = (i) => grid.querySelector(`[data-i="${i}"]`);

  function buildGrid(picked = []) {
    grid.style.setProperty('--n', side());
    grid.innerHTML = Array.from({ length: size }, (_, i) => `<button class="mn-tile" data-i="${i}" aria-label="${esc(t('Casilla {n}', { n: i + 1 }))}"></button>`).join('');
    picked.forEach((i) => reveal(i, 'gem', true));
  }
  function reveal(i, kind, instant = false, ghost = false) {
    const tileEl = tile(i); if (!tileEl) return;
    tileEl.className = `mn-tile ${kind} ${ghost ? 'ghost' : ''} ${instant ? '' : 'pop'}`;
    tileEl.innerHTML = kind === 'bomb' ? BOMB : GEM; tileEl.disabled = true;
  }
  function revealAll(res) {
    const bombs = new Set(res.mineIndices || []);
    for (let i = 0; i < size; i++) { const tileEl = tile(i); if (tileEl && !tileEl.disabled) reveal(i, bombs.has(i) ? 'bomb' : 'gem', true, true); }
  }
  async function loadTable() {
    try { table = (await get(`/api/games/mines/table?size=${size}&mines=${mines}`)).mults; } catch { table = []; }
    paint();
  }
  const reloadTable = debounce(() => loadTable(), 120);
  function paint() {
    const bet = game ? game.bet : bp.value();
    paintProgress(host, { bet, mult: game ? game.mult : null, nextMult: game ? game.nextMult : table[1] });
    $('#gems').textContent = String(size - mines); $('#mcount').textContent = String(mines);
    range.max = String(size - 1);
    const active = !!game;
    go.classList.toggle('hidden', active); cash.classList.toggle('hidden', !active); rand.classList.toggle('hidden', !active);
    bp.lock(active || busy); range.disabled = active || busy; sizesEl.classList.toggle('locked', active || busy);
    cash.disabled = busy || !active || !game.picked.length;
    cash.textContent = active && game.picked.length ? t('Plantarme con {cantidad}', { cantidad: money(game.payoutNow) }) : t('Plantarme');
    rand.disabled = busy;
    go.disabled = busy || !bp.valid();
    grid.classList.toggle('live', active && !busy);
  }
  bp.onChange(paint);
  sizesEl.addEventListener('click', (e) => {
    const b = e.target.closest('[data-n]'); if (!b || game || busy) return;
    size = +b.dataset.n; mines = Math.min(mines, size - 1); range.value = String(mines);
    sizesEl.querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
    buildGrid(); paint(); reloadTable();
  });
  range.addEventListener('input', () => { if (game || busy) return; mines = +range.value; paint(); reloadTable(); });

  async function settle(res, kind) {      // after a round is over: show the whole board, then reset
    revealAll(res); setUser(res.user); ctx.refreshBets?.();
    game = null; busy = true; paint();
    await sleep(kind === 'lose' ? 2300 : 2000); if (dead) return;
    busy = false; buildGrid(); say(t('Elige cuadrícula, elige tu miedo, dale a Apostar.')); paint();
  }

  go.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; paint();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/mines/start', { amount, size, mines });
      setUser(res.user); game = res; buildGrid(); say(t('Abre una casilla. La que sea. Suerte con eso.'));
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  grid.addEventListener('click', async (e) => {
    const tileEl = e.target.closest('.mn-tile'); if (!tileEl || !game || busy || tileEl.disabled) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/mines/pick', { tile: +tileEl.dataset.i });
      if (res.crashed) {
        reveal(res.hit, 'bomb'); shake(stage);
        const b = tileEl.getBoundingClientRect(), s = stage.getBoundingClientRect(); burst(stage, b.left - s.left + b.width / 2, b.top - s.top + b.height / 2, { count: 30, power: 240, colors: ['#FF4B2B', '#EFE6D2', '#0E0C0A'] });
        say(t('¡Bum! Esa tenía bomba. Pierdes {cantidad}.', { cantidad: money(game.bet) }));
        resultPop({ net: -game.bet, label: t('Bomba') });
        return settle(res, 'lose');
      }
      reveal(+tileEl.dataset.i, 'gem'); game = { ...game, ...res };
      const b = tileEl.getBoundingClientRect(), s = stage.getBoundingClientRect(); burst(stage, b.left - s.left + b.width / 2, b.top - s.top + b.height / 2, { count: 9, power: 130, size: 7, colors: ['#C6F432', '#EFE6D2'], life: 650 });
      if (res.finished) {
        say(t('Limpiaste el tablero. {x}. Presumido.', { x: fmtX(res.mult) }));
        resultPop({ net: res.payout - game.bet, label: t('Lo limpiaste todo'), detail: fmtX(res.mult), bet: game.bet });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360, colors: WIN_COLORS });
        return settle(res, 'win');
      }
      say(t('{x} · {cantidad} si te plantas ahora', { x: fmtX(res.mult), cantidad: money(res.payoutNow) }));
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  cash.addEventListener('click', async () => {
    if (busy || !game || !game.picked.length) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/mines/cashout', {});
      say(t('Te llevas {cantidad}. Listo. O miedoso.', { cantidad: money(res.payout) }));
      resultPop({ net: res.payout - game.bet, label: t('Te plantaste en {x}', { x: fmtX(res.mult) }), bet: game.bet });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.45, { count: 46, power: 300, colors: WIN_COLORS });
      return settle(res, 'win');
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  rand.addEventListener('click', () => {
    const open = [...grid.querySelectorAll('.mn-tile:not(:disabled)')];
    if (open.length && !busy) open[Math.floor(Math.random() * open.length)].click();
  });

  // pick up a round in progress after a refresh
  try {
    const cur = await get('/api/games/state');
    if (cur.mines && !dead) {
      game = cur.mines; size = game.size; mines = game.mines; range.value = String(mines);
      sizesEl.querySelectorAll('button').forEach((x) => x.classList.toggle('active', +x.dataset.n === size));
      buildGrid(game.picked); say(game.picked.length ? t('Bienvenido de vuelta. {x} · {cantidad} si te plantas', { x: fmtX(game.mult), cantidad: money(game.payoutNow) }) : t('Abre una casilla. La que sea.'));
    } else buildGrid();
  } catch { buildGrid(); }
  paint(); loadTable();
  return { unmount() { dead = true; bp.destroy(); } };
}
