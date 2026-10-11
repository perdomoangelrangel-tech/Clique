import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX, progressHtml, paintProgress } from './common.js';
import { money, sleep, esc } from '../util.js';
import { glyph } from '../art.js';
import { toast } from '../ui.js';

const svg = (name) => `<svg viewBox="0 0 64 64" aria-hidden="true">${glyph(name)}</svg>`;
const COIN = svg('coin'), TRAP = svg('flame');
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
const LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard', expert: 'Expert', master: 'Master' };

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const ROWS = meta.tower.rows, RISKS = meta.tower.risks;
  host.innerHTML = `<div class="gm tower">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label for="risk">Risk</label>
        <select class="gm-select" id="risk">${Object.keys(RISKS).map((k) => `<option value="${k}">${esc(LABEL[k] || k)}</option>`).join('')}</select>
        <small class="muted" id="risk-info"></small></div>
      ${progressHtml()}
      <button class="btn-bet" id="go">Bet</button>
      <button class="btn-bet cash hidden" id="cash">Cash out</button>
      <div class="gm-note">Climb ${ROWS} rows. Pick one tile per row: safe and you climb, a trap and you fall. Cash out after any row. Safer towers pay less per floor.</div>
    </div>
    <div class="gm-stage tw-stage" id="stage"><div class="tw-tower" id="tower"></div><div class="tw-msg" id="msg">Pick a risk. Start climbing.</div></div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-tower' });
  const stage = $('#stage'), tower = $('#tower'), msg = $('#msg'), go = $('#go'), cash = $('#cash'), riskSel = $('#risk');
  let risk = 'easy', game = null, busy = false, dead = false;
  const say = (t) => { msg.textContent = t; };
  const tile = (r, c) => tower.querySelector(`.tw-tile[data-r="${r}"][data-c="${c}"]`);
  const step = () => (game ? game.step : 0);

  function build(picks = []) {
    const R = RISKS[risk];
    tower.style.setProperty('--cols', R.cols);
    let html = '';
    for (let r = ROWS - 1; r >= 0; r--) {
      html += `<div class="tw-row" data-r="${r}"><span class="tw-mult num">${fmtX(R.mults[r + 1])}</span><div class="tw-tiles">${Array.from({ length: R.cols }, (_, c) => `<button class="tw-tile" data-r="${r}" data-c="${c}" aria-label="Row ${r + 1}, tile ${c + 1}"></button>`).join('')}</div></div>`;
    }
    tower.innerHTML = html;
    picks.forEach((c, r) => mark(r, c, 'safe', true));
    setNow();
  }
  function mark(r, c, kind, instant = false, ghost = false) {
    const t = tile(r, c); if (!t) return;
    t.className = `tw-tile ${kind} ${ghost ? 'ghost' : ''} ${instant ? '' : 'pop'}`; t.innerHTML = kind === 'trap' ? TRAP : COIN; t.disabled = true;
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
      for (let c = 0; c < RISKS[risk].cols; c++) { const t = tile(r, c); if (t && !t.disabled) mark(r, c, traps.includes(c) ? 'trap' : 'safe', true, true); }
    });
  }
  function paint() {
    const R = RISKS[risk], active = !!game;
    $('#risk-info').textContent = `${R.cols} tiles a row, ${R.traps} ${R.traps === 1 ? 'trap' : 'traps'} · first row pays ${fmtX(R.mults[1])}`;
    paintProgress(host, { bet: game ? game.bet : bp.value(), mult: game && game.step ? game.mult : null, nextMult: game ? game.nextMult : R.mults[1] });
    go.classList.toggle('hidden', active); cash.classList.toggle('hidden', !active);
    bp.lock(active || busy); riskSel.disabled = active || busy;
    cash.disabled = busy || !active || !game.step;
    cash.textContent = active && game.step ? `Cash out ${money(game.payoutNow)}` : 'Cash out';
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
    busy = false; build(); say('Pick a risk. Start climbing.'); paint();
  }

  go.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; paint();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/tower/start', { amount, risk });
      setUser(res.user); game = res; build(); say('Bottom row. Pick a tile.');
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  tower.addEventListener('click', async (e) => {
    const t = e.target.closest('.tw-tile'); if (!t || !game || busy || t.disabled || +t.dataset.r !== step()) return;
    busy = true; paint();
    const r = +t.dataset.r, c = +t.dataset.c;
    try {
      const res = await post('/api/games/tower/pick', { tile: c });
      const b = t.getBoundingClientRect(), s = stage.getBoundingClientRect(), x = b.left - s.left + b.width / 2, y = b.top - s.top + b.height / 2;
      if (res.crashed) {
        mark(r, c, 'trap'); shake(stage); burst(stage, x, y, { count: 30, power: 250, colors: ['#FF4B2B', '#EFE6D2', '#0E0C0A'] });
        say(`Trap. You fell from row ${r + 1}. You lose ${money(game.bet)}.`);
        resultPop({ net: -game.bet, label: `Fell on row ${r + 1}` });
        return settle(res, false);
      }
      mark(r, c, 'safe'); burst(stage, x, y, { count: 10, power: 140, size: 7, colors: ['#C6F432', '#EFE6D2'], life: 650 });
      game = { ...game, ...res };
      if (res.finished) {
        say(`Top of the tower. ${fmtX(res.mult)}. Look at you.`);
        resultPop({ net: res.payout - game.bet, label: 'Reached the top', detail: fmtX(res.mult), bet: game.bet });
        const rr = stage.getBoundingClientRect(); burst(stage, rr.width / 2, rr.height / 2, { count: 70, power: 360, colors: WIN_COLORS });
        return settle(res, true);
      }
      say(`Row ${res.step} cleared. ${fmtX(res.mult)} · ${money(res.payoutNow)} if you leave.`);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  cash.addEventListener('click', async () => {
    if (busy || !game || !game.step) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/tower/cashout', {});
      say(`Banked ${money(res.payout)}. The tower can keep the rest.`);
      resultPop({ net: res.payout - game.bet, label: `Left at ${fmtX(res.mult)}`, bet: game.bet });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.45, { count: 46, power: 300, colors: WIN_COLORS });
      return settle(res, true);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  try {
    const cur = await get('/api/games/state');
    if (cur.tower && !dead) {
      game = cur.tower; risk = game.risk; riskSel.value = risk; build(game.picks);
      say(game.step ? `Welcome back. Row ${game.step} done, ${fmtX(game.mult)} · ${money(game.payoutNow)} if you leave.` : 'Bottom row. Pick a tile.');
    } else build();
  } catch { build(); }
  paint();
  return { unmount() { dead = true; bp.destroy(); } };
}
