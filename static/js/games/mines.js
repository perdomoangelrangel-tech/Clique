import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX, progressHtml, paintProgress } from './common.js';
import { money, sleep, debounce } from '../util.js';
import { glyph } from '../art.js';
import { toast } from '../ui.js';

const svg = (name) => `<svg viewBox="0 0 64 64" aria-hidden="true">${glyph(name)}</svg>`;
const GEM = svg('gem'), BOMB = svg('bomb');
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const SIZES = meta.mines.sizes;
  host.innerHTML = `<div class="gm mines">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>Grid size</label><div class="seg stretch" id="sizes">${SIZES.map((n) => `<button data-n="${n}" class="${n === 25 ? 'active' : ''}">${n}</button>`).join('')}</div></div>
      <div class="gm-field"><label for="mines">Mines</label>
        <div class="mn-range"><span class="mn-count"><i class="mn-ico">${GEM}</i><b id="gems">22</b></span>
          <input type="range" class="gm-range" id="mines" min="1" max="24" value="3">
          <span class="mn-count bomb"><b id="mcount">3</b><i class="mn-ico">${BOMB}</i></span></div></div>
      ${progressHtml()}
      <button class="btn-bet" id="go">Bet</button>
      <button class="btn-bet cash hidden" id="cash">Cash out</button>
      <button class="mini hidden" id="rand">Open a random tile</button>
      <div class="gm-note">Open safe tiles to climb. Cash out any time after the first one. Open a bomb and it is over. More bombs, bigger jump per tile.</div>
    </div>
    <div class="gm-stage mn-stage" id="stage"><div class="mn-grid" id="grid"></div><div class="mn-msg" id="msg">Pick a grid, pick your fear, hit bet.</div></div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-mines' });
  const stage = $('#stage'), grid = $('#grid'), msg = $('#msg'), go = $('#go'), cash = $('#cash'), rand = $('#rand'), range = $('#mines'), sizesEl = $('#sizes');
  let size = 25, mines = 3, game = null, busy = false, dead = false, table = [];

  const side = () => Math.round(Math.sqrt(size));
  const say = (t) => { msg.textContent = t; };
  const tile = (i) => grid.querySelector(`[data-i="${i}"]`);

  function buildGrid(picked = []) {
    grid.style.setProperty('--n', side());
    grid.innerHTML = Array.from({ length: size }, (_, i) => `<button class="mn-tile" data-i="${i}" aria-label="Tile ${i + 1}"></button>`).join('');
    picked.forEach((i) => reveal(i, 'gem', true));
  }
  function reveal(i, kind, instant = false, ghost = false) {
    const t = tile(i); if (!t) return;
    t.className = `mn-tile ${kind} ${ghost ? 'ghost' : ''} ${instant ? '' : 'pop'}`;
    t.innerHTML = kind === 'bomb' ? BOMB : GEM; t.disabled = true;
  }
  function revealAll(res) {
    const bombs = new Set(res.mineIndices || []);
    for (let i = 0; i < size; i++) { const t = tile(i); if (t && !t.disabled) reveal(i, bombs.has(i) ? 'bomb' : 'gem', true, true); }
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
    cash.textContent = active && game.picked.length ? `Cash out ${money(game.payoutNow)}` : 'Cash out';
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
    busy = false; buildGrid(); say('Pick a grid, pick your fear, hit bet.'); paint();
  }

  go.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; paint();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/mines/start', { amount, size, mines });
      setUser(res.user); game = res; buildGrid(); say('Open a tile. Any tile. Good luck with that.');
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  grid.addEventListener('click', async (e) => {
    const t = e.target.closest('.mn-tile'); if (!t || !game || busy || t.disabled) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/mines/pick', { tile: +t.dataset.i });
      if (res.crashed) {
        reveal(res.hit, 'bomb'); shake(stage);
        const b = t.getBoundingClientRect(), s = stage.getBoundingClientRect(); burst(stage, b.left - s.left + b.width / 2, b.top - s.top + b.height / 2, { count: 30, power: 240, colors: ['#FF4B2B', '#EFE6D2', '#0E0C0A'] });
        say(`Boom. That one had a bomb in it. You lose ${money(game.bet)}.`);
        resultPop({ net: -game.bet, label: 'Bomb' });
        return settle(res, 'lose');
      }
      reveal(+t.dataset.i, 'gem'); game = { ...game, ...res };
      const b = t.getBoundingClientRect(), s = stage.getBoundingClientRect(); burst(stage, b.left - s.left + b.width / 2, b.top - s.top + b.height / 2, { count: 9, power: 130, size: 7, colors: ['#C6F432', '#EFE6D2'], life: 650 });
      if (res.finished) {
        say(`Cleared the board. ${fmtX(res.mult)}. Show-off.`);
        resultPop({ net: res.payout - game.bet, label: 'Cleared it all', detail: fmtX(res.mult), bet: game.bet });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360, colors: WIN_COLORS });
        return settle(res, 'win');
      }
      say(`${fmtX(res.mult)} · ${money(res.payoutNow)} if you leave now`);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  cash.addEventListener('click', async () => {
    if (busy || !game || !game.picked.length) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/mines/cashout', {});
      say(`Banked ${money(res.payout)}. Smart. Or scared.`);
      resultPop({ net: res.payout - game.bet, label: `Left at ${fmtX(res.mult)}`, bet: game.bet });
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
      buildGrid(game.picked); say(game.picked.length ? `Welcome back. ${fmtX(game.mult)} · ${money(game.payoutNow)} if you leave` : 'Open a tile. Any tile.');
    } else buildGrid();
  } catch { buildGrid(); }
  paint(); loadTable();
  return { unmount() { dead = true; bp.destroy(); } };
}
