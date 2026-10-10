/* Hi-Lo: a card is showing. Higher or lower? Every right guess multiplies your payout, a wrong one loses it all, and you can cash
   out after any right guess. The server draws every card, and the next one is only drawn when you guess. */
import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, cardEl, fmtX } from './common.js';
import { money, sleep } from '../util.js';
import { toast } from '../ui.js';

const pctText = (c) => (c * 100).toFixed(2) + '%';
const fx = (m) => fmtX(Math.floor(m * 100 + 1e-6) / 100);        // shown rounded down, like the payout, so 2.665x is never advertised as 2.67x

export default async function mount(host, ctx = {}) {
  host.innerHTML = `<div class="gm hilo">
    <div class="gm-panel">
      <div id="bet"></div>
      <button class="btn-bet" id="play">Bet</button>
      <button class="btn-bet cash hidden" id="cash">Cash out</button>
      <div class="hl-read" aria-live="polite">
        <div><small>Total payout</small><b class="num" id="pay">$0.00</b></div>
        <div><small>Profit</small><b class="num" id="profit">$0.00</b></div>
        <div><small>Multiplier</small><b class="num" id="mult">0.00x</b></div>
      </div>
      <div class="gm-note">A card is dealt. Guess whether the next one is higher or lower. A card of the same rank counts as a win either way. The rarer the guess, the more it pays: every guess returns 96% on average. A guess that could never lose is not offered. Cash out after any right guess, or skip a card you do not like.</div>
    </div>
    <div class="gm-stage hl-stage" id="stage">
      <div class="hl-trail" id="trail" aria-label="Cards so far"></div>
      <div class="hl-table">
        <button class="hl-opt lower" id="lower" disabled><span class="hl-arrow">&#9660;</span><b>Lower or same</b><em class="num" data-x>x0.00</em><small class="num" data-c>0.00%</small></button>
        <div class="hl-card" id="cardbox"></div>
        <button class="hl-opt higher" id="higher" disabled><span class="hl-arrow">&#9650;</span><b>Higher or same</b><em class="num" data-x>x0.00</em><small class="num" data-c>0.00%</small></button>
      </div>
      <button class="hl-skip" id="skip" disabled>Skip card <span id="skips" class="num"></span></button>
      <div class="hl-msg" id="msg">Place a bet and a card is dealt.</div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { label: 'Bet Amount', key: 'bet-hilo' });
  const stage = $('#stage'), cardbox = $('#cardbox'), trail = $('#trail'), msg = $('#msg');
  const playBtn = $('#play'), cashBtn = $('#cash'), skipBtn = $('#skip'), lowerBtn = $('#lower'), higherBtn = $('#higher');
  let game = null, busy = false, dead = false;

  const say = (t) => { msg.textContent = t; };
  const showCard = (c, { flip = false } = {}) => {
    cardbox.innerHTML = '';
    const el = cardEl(c, { down: flip, instant: true });
    cardbox.appendChild(el);
    if (flip) { void el.offsetWidth; requestAnimationFrame(() => el.classList.remove('down')); }
    return el;
  };
  const showBack = () => { cardbox.innerHTML = ''; cardbox.appendChild(cardEl(null, { down: true, instant: true })); };
  const drawTrail = () => {
    const h = game ? game.history.slice(0, -1).slice(-8) : [];
    trail.innerHTML = h.map((c) => `<span class="hl-mini ${c.t === 'skip' ? 'skipped' : ''} ${c.s === 'H' || c.s === 'D' ? 'red' : ''}" title="${c.t === 'skip' ? 'skipped' : c.t === 'start' ? 'first card' : 'right guess'}">${c.r}</span>`).join('');
  };
  const paintOptions = () => {
    for (const [btn, key] of [[lowerBtn, 'lower'], [higherBtn, 'higher']]) {
      const o = game && game.options[key];
      btn.querySelector('[data-x]').textContent = o && o.offered ? 'x' + o.mult.toFixed(2) : '\u2014';
      btn.querySelector('[data-c]').textContent = o ? (o.offered ? pctText(o.chance) : 'can\'t lose') : '0.00%';
      btn.disabled = busy || !game || !o || !o.offered;
      btn.classList.toggle('never', !!(game && o && !o.offered));
    }
  };
  function setUi() {
    const active = !!game;
    playBtn.classList.toggle('hidden', active); cashBtn.classList.toggle('hidden', !active);
    bp.lock(active || busy);
    playBtn.disabled = busy || !bp.valid();
    cashBtn.disabled = busy || !active || game.wins < 1;
    skipBtn.disabled = busy || !active || game.skipsLeft < 1;
    $('#skips').textContent = active ? `(${game.skipsLeft} left)` : '';
    const bet = game ? game.bet : bp.value() || 0;
    const mult = game && game.wins ? game.mult : 0;
    $('#pay').textContent = money(game ? game.payoutNow : 0);
    $('#profit').textContent = money(game && game.wins ? Math.max(0, game.payoutNow - bet) : 0);
    $('#mult').textContent = fx(mult);
    cashBtn.textContent = game && game.wins ? `Cash out ${money(game.payoutNow)}` : 'Cash out';
    paintOptions(); drawTrail();
  }
  bp.onChange(() => { if (!game) playBtn.disabled = busy || !bp.valid(); });

  async function resetRound(delay = 1900) {
    await sleep(delay); if (dead) return;
    game = null; busy = false; showBack(); trail.innerHTML = ''; say('Place a bet and a card is dealt.'); setUi();
  }
  const finish = async (res, label, bet, detail = '') => {
    resultPop({ net: res.payout - bet, label, detail, bet });
    setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; setUi();
  };

  playBtn.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; setUi();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/hilo/start', { amount });
      setUser(res.user); game = res; trail.innerHTML = ''; showCard(res.card, { flip: true });
      say('Higher or lower? Pick one.');
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  async function guess(pick) {
    if (busy || !game) return;
    busy = true; setUi();
    const old = game;
    try {
      const res = await post('/api/games/hilo/guess', { pick });
      showCard(res.next, { flip: true });                        // the card is turned over
      await sleep(650);
      if (!res.won) {
        shake(stage); stage.classList.add('flash-red'); setTimeout(() => stage.classList.remove('flash-red'), 500);
        say(`${res.next.r} is not ${pick}. Everything is gone.`);
        await finish(res, `Missed ${pick} on a ${old.card.r}`, old.bet);
        return resetRound(2200);
      }
      const r = stage.getBoundingClientRect();
      burst(stage, r.width / 2, r.height / 2, { count: 14, colors: ['#C6F432', '#EFE6D2'], power: 170, size: 8, life: 800 });
      game = res;
      if (res.finished) {
        say(`${fx(res.mult)}. That is as far as it goes: paid out.`);
        burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360 });
        await finish(res, `${res.wins} right in a row`, old.bet, fx(res.mult));
        return resetRound(2600);
      }
      say(`Right. ${fx(res.mult)} · ${money(res.payoutNow)} if you leave now.`);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  }
  lowerBtn.addEventListener('click', () => guess('lower'));
  higherBtn.addEventListener('click', () => guess('higher'));

  skipBtn.addEventListener('click', async () => {
    if (busy || !game) return;
    busy = true; setUi();
    try {
      const res = await post('/api/games/hilo/skip', {});
      game = res; showCard(res.card, { flip: true }); say('New card. Same stake, same streak.');
    } catch (ex) { toast(ex.message, 'err'); }
    busy = false; setUi();
  });

  cashBtn.addEventListener('click', async () => {
    if (busy || !game || game.wins < 1) return;
    busy = true; setUi();
    const old = game;
    try {
      const res = await post('/api/games/hilo/cashout', {});
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 50, power: 320 });
      say(`Banked ${money(res.payout)}. Smart. Or scared.`);
      await finish(res, `Left at ${fx(res.mult)}`, old.bet);
      return resetRound(2200);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  // resume a round that was in progress (another tab, a refresh, a long coffee break)
  showBack();
  try {
    const cur = await get('/api/games/state');
    if (cur.hilo && !dead) {
      game = cur.hilo; showCard(game.card);
      say(game.wins ? `Welcome back. ${fx(game.mult)} · ${money(game.payoutNow)} if you leave now.` : 'Higher or lower? Pick one.');
    }
  } catch { /* start from an empty table */ }
  setUi();

  return { unmount() { dead = true; bp.destroy(); } };
}
