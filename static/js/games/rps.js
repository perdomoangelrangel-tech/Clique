/* Rock Paper Scissors against the house. Win and you climb the ladder (1.96x, then it doubles with every win), lose and it is over,
   draw and you simply go again. Cash out after any win. The server draws the house's pick only after you have picked. */
import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX } from './common.js';
import { money, sleep, esc } from '../util.js';
import { toast } from '../ui.js';

const STROKE = 'stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"';
const ICONS = {
  rock: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M9 42l6-18 17-8 19 8 6 17-6 14-21 6-16-6z" fill="#CFC3A8"/><path d="M21 33l9-4M37 23l9 7M26 46l11 3" fill="none" stroke-width="2.4"/></g></svg>`,
  paper: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M14 5h23l13 13v41H14z" fill="#EFE6D2"/><path d="M37 5v13h13" fill="#CFC3A8"/><path d="M21 29h22M21 38h22M21 47h14" fill="none" stroke-width="2.6"/></g></svg>`,
  scissors: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M17 6L45 52" fill="none" stroke-width="9"/><path d="M17 6L45 52" fill="none" stroke="#EFE6D2" stroke-width="3.4"/><path d="M47 6L19 52" fill="none" stroke-width="9"/><path d="M47 6L19 52" fill="none" stroke="#EFE6D2" stroke-width="3.4"/>
    <circle cx="19" cy="54" r="8" fill="#C6F432"/><circle cx="45" cy="54" r="8" fill="#FF4B2B"/><circle cx="32" cy="29" r="3.6" fill="#0E0C0A"/></g></svg>`,
};
const MOVES = ['rock', 'paper', 'scissors'];
const NAME = { rock: 'Rock', paper: 'Paper', scissors: 'Scissors' };
const VERB = { rock: 'breaks', paper: 'covers', scissors: 'cuts' };
const BEATS = { rock: 'scissors', paper: 'rock', scissors: 'paper' };

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const LADDER = meta.rps.ladder;
  host.innerHTML = `<div class="gm rps">
    <div class="gm-panel">
      <div id="bet"></div>
      <button class="btn-bet" id="play">Bet</button>
      <button class="btn-bet cash hidden" id="cash">Cash out</button>
      <div class="hl-read" aria-live="polite">
        <div><small>Total payout</small><b class="num" id="pay">$0.00</b></div>
        <div><small>Profit</small><b class="num" id="profit">$0.00</b></div>
        <div><small>Multiplier</small><b class="num" id="mult">0.00x</b></div>
      </div>
      <div class="gm-note">Pick rock, paper or scissors against the house. Win and you climb: the first win pays 1.96x and every win after that doubles it, up to ${LADDER.length} in a row. A draw is simply played again and costs nothing. Lose and the bet is gone. Cash out after any win. Every step returns 98% on average.</div>
    </div>
    <div class="gm-stage rp-stage" id="stage">
      <div class="rp-ladder" id="ladder" aria-label="The ladder"></div>
      <div class="rp-duel">
        <div class="rp-side"><small>You</small><div class="rp-pick" id="you"><span class="q">?</span></div></div>
        <div class="rp-vs">VS</div>
        <div class="rp-side"><small>House</small><div class="rp-pick" id="house"><span class="q">?</span></div></div>
      </div>
      <div class="rp-msg" id="msg">Place a bet, then pick your move.</div>
      <div class="rp-choices" id="choices">${MOVES.map((m) => `<button class="rp-choice" data-m="${m}" disabled><span class="rp-ico">${ICONS[m]}</span><b>${esc(NAME[m])}</b></button>`).join('')}</div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { label: 'Bet Amount', key: 'bet-rps' });
  const stage = $('#stage'), msg = $('#msg'), playBtn = $('#play'), cashBtn = $('#cash'), you = $('#you'), house = $('#house');
  let game = null, busy = false, dead = false;

  const say = (t) => { msg.textContent = t; };
  const pickBox = (el, move, cls = '') => { el.className = `rp-pick ${cls}`; el.innerHTML = move ? ICONS[move] : '<span class="q">?</span>'; };
  const drawLadder = () => {
    const wins = game ? game.wins : 0;
    $('#ladder').innerHTML = LADDER.map((m, i) => `<span class="rp-rung ${i < wins ? 'done' : i === wins && game ? 'next' : ''}"><small>${i + 1}</small><b class="num">${m.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x</b></span>`).join('');
  };
  function setUi() {
    const active = !!game;
    playBtn.classList.toggle('hidden', active); cashBtn.classList.toggle('hidden', !active);
    bp.lock(active || busy);
    playBtn.disabled = busy || !bp.valid();
    cashBtn.disabled = busy || !active || game.wins < 1;
    host.querySelectorAll('.rp-choice').forEach((b) => { b.disabled = busy || !active; });
    const bet = game ? game.bet : 0;
    $('#pay').textContent = money(game ? game.payoutNow : 0);
    $('#profit').textContent = money(game && game.wins ? Math.max(0, game.payoutNow - bet) : 0);
    $('#mult').textContent = fmtX(game && game.wins ? game.mult : 0);
    cashBtn.textContent = game && game.wins ? `Cash out ${money(game.payoutNow)}` : 'Cash out';
    drawLadder();
  }
  bp.onChange(() => { if (!game) playBtn.disabled = busy || !bp.valid(); });

  async function resetRound(delay = 2000) {
    await sleep(delay); if (dead) return;
    game = null; busy = false; pickBox(you, null); pickBox(house, null); say('Place a bet, then pick your move.'); setUi();
  }
  const finish = (res, label, bet, detail = '') => {
    resultPop({ net: res.payout - bet, label, detail, bet });
    setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; setUi();
  };

  playBtn.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; setUi();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/rps/start', { amount });
      setUser(res.user); game = res; pickBox(you, null); pickBox(house, null); say('Pick your move.');
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  $('#choices').addEventListener('click', async (e) => {
    const b = e.target.closest('.rp-choice'); if (!b || busy || !game) return;
    const pick = b.dataset.m; busy = true; setUi();
    const old = game;
    pickBox(you, pick); pickBox(house, null); house.classList.add('think'); say('…');
    try {
      const res = await post('/api/games/rps/play', { pick });
      await sleep(reduced() ? 100 : 650);
      pickBox(house, res.house, res.result === 'lose' ? 'win' : res.result === 'win' ? 'lose' : 'draw');
      you.classList.add(res.result === 'win' ? 'win' : res.result === 'lose' ? 'lose' : 'draw');
      const r = stage.getBoundingClientRect();
      if (res.result === 'draw') { say(`Both picked ${NAME[pick].toLowerCase()}. A draw: go again, it costs nothing.`); game = res; }
      else if (res.result === 'win') {
        say(`${NAME[pick]} ${VERB[pick]} ${res.house}. ${fmtX(res.mult)} · ${money(res.payoutNow)} if you leave now.`);
        burst(stage, r.width / 2, r.height * 0.45, { count: 18, colors: ['#C6F432', '#EFE6D2'], power: 200, size: 8, life: 800 });
        game = res;
        if (res.finished) {
          say(`${res.wins} wins in a row. That is the top of the ladder: paid out.`);
          burst(stage, r.width / 2, r.height / 2, { count: 80, power: 380 });
          finish(res, `${res.wins} wins in a row`, old.bet, fmtX(res.mult)); return resetRound(2800);
        }
      } else {
        shake(stage); stage.classList.add('flash-red'); setTimeout(() => stage.classList.remove('flash-red'), 500);
        say(`${NAME[res.house]} ${VERB[res.house]} ${pick}. The house wins.`);
        finish(res, `Lost to ${res.house}`, old.bet); return resetRound(2400);
      }
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); pickBox(house, null); }
    busy = false; setUi();
  });

  cashBtn.addEventListener('click', async () => {
    if (busy || !game || game.wins < 1) return;
    busy = true; setUi();
    const old = game;
    try {
      const res = await post('/api/games/rps/cashout', {});
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 50, power: 320 });
      say(`Banked ${money(res.payout)}. Smart. Or scared.`);
      finish(res, `Left at ${fmtX(res.mult)}`, old.bet); return resetRound(2200);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  const reduced = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  try {                                                         // pick up a round that was in progress
    const cur = await get('/api/games/state');
    if (cur.rps && !dead) { game = cur.rps; say(game.wins ? `Welcome back. ${fmtX(game.mult)} · ${money(game.payoutNow)} if you leave now.` : 'Pick your move.'); }
  } catch { /* an empty table */ }
  setUi();
  return { unmount() { dead = true; bp.destroy(); } };
}
