/* Hi-Lo: a card is showing. Higher or lower? Every right guess multiplies your payout, a wrong one loses it all, and you can cash
   out after any right guess. The server draws every card, and the next one is only drawn when you guess. */
import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, cardEl, fmtX } from './common.js';
import { money, sleep, esc } from '../util.js';
import { toast } from '../ui.js';
import { t } from '../i18n.js';

const pickWord = (p) => (p === 'higher' ? t('mayor o igual') : t('menor o igual'));
const pctText = (c) => (c * 100).toFixed(2) + '%';
const fx = (m) => fmtX(Math.floor(m * 100 + 1e-6) / 100);        // shown rounded down, like the payout, so 2.665x is never advertised as 2.67x

export default async function mount(host, ctx = {}) {
  host.innerHTML = `<div class="gm hilo">
    <div class="gm-panel">
      <div id="bet"></div>
      <button class="btn-bet" id="play">${t('Apostar')}</button>
      <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      <div class="hl-read" aria-live="polite">
        <div><small>${t('Pago total')}</small><b class="num" id="pay">${money(0)}</b></div>
        <div><small>${t('Ganancia')}</small><b class="num" id="profit">${money(0)}</b></div>
        <div><small>${t('Multiplicador')}</small><b class="num" id="mult">0.00x</b></div>
      </div>
      <div class="gm-note">${t('Sale una carta. Adivina si la siguiente es mayor o menor. Una carta del mismo valor cuenta como acierto en ambos casos. Entre más rara la predicción, más paga: cada una devuelve 96% en promedio. No se ofrece una predicción que nunca podría perder. Plántate después de cualquier acierto, o sáltate una carta que no te guste.')}</div>
    </div>
    <div class="gm-stage hl-stage" id="stage">
      <div class="hl-trail" id="trail" aria-label="${esc(t('Cartas hasta ahora'))}"></div>
      <div class="hl-table">
        <button class="hl-opt lower" id="lower" disabled><span class="hl-arrow">&#9660;</span><b>${t('Menor o igual')}</b><em class="num" data-x>x0.00</em><small class="num" data-c>0.00%</small></button>
        <div class="hl-card" id="cardbox"></div>
        <button class="hl-opt higher" id="higher" disabled><span class="hl-arrow">&#9650;</span><b>${t('Mayor o igual')}</b><em class="num" data-x>x0.00</em><small class="num" data-c>0.00%</small></button>
      </div>
      <button class="hl-skip" id="skip" disabled>${t('Saltar carta')} <span id="skips" class="num"></span></button>
      <div class="hl-msg" id="msg">${t('Haz una apuesta y sale una carta.')}</div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-hilo' });
  const stage = $('#stage'), cardbox = $('#cardbox'), trail = $('#trail'), msg = $('#msg');
  const playBtn = $('#play'), cashBtn = $('#cash'), skipBtn = $('#skip'), lowerBtn = $('#lower'), higherBtn = $('#higher');
  let game = null, busy = false, dead = false;

  const say = (text) => { msg.textContent = text; };
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
    trail.innerHTML = h.map((c) => `<span class="hl-mini ${c.t === 'skip' ? 'skipped' : ''} ${c.s === 'H' || c.s === 'D' ? 'red' : ''}" title="${esc(c.t === 'skip' ? t('saltada') : c.t === 'start' ? t('primera carta') : t('acierto'))}">${c.r}</span>`).join('');
  };
  const paintOptions = () => {
    for (const [btn, key] of [[lowerBtn, 'lower'], [higherBtn, 'higher']]) {
      const o = game && game.options[key];
      btn.querySelector('[data-x]').textContent = o && o.offered ? 'x' + o.mult.toFixed(2) : '\u2014';
      btn.querySelector('[data-c]').textContent = o ? (o.offered ? pctText(o.chance) : t('no pierde')) : '0.00%';
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
    $('#skips').textContent = active ? t('(quedan {n})', { n: game.skipsLeft }) : '';
    const bet = game ? game.bet : bp.value() || 0;
    const mult = game && game.wins ? game.mult : 0;
    $('#pay').textContent = money(game ? game.payoutNow : 0);
    $('#profit').textContent = money(game && game.wins ? Math.max(0, game.payoutNow - bet) : 0);
    $('#mult').textContent = fx(mult);
    cashBtn.textContent = game && game.wins ? t('Plantarme con {cantidad}', { cantidad: money(game.payoutNow) }) : t('Plantarme');
    paintOptions(); drawTrail();
  }
  bp.onChange(() => { if (!game) playBtn.disabled = busy || !bp.valid(); });

  async function resetRound(delay = 1900) {
    await sleep(delay); if (dead) return;
    game = null; busy = false; showBack(); trail.innerHTML = ''; say(t('Haz una apuesta y sale una carta.')); setUi();
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
      say(t('¿Mayor o menor? Elige.'));
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
        say(t('{carta} no es {prediccion}. Se fue todo.', { carta: res.next.r, prediccion: pickWord(pick) }));
        await finish(res, t('Fallaste {prediccion} con un {carta}', { prediccion: pickWord(pick), carta: old.card.r }), old.bet);
        return resetRound(2200);
      }
      const r = stage.getBoundingClientRect();
      burst(stage, r.width / 2, r.height / 2, { count: 14, colors: ['#C6F432', '#EFE6D2'], power: 170, size: 8, life: 800 });
      game = res;
      if (res.finished) {
        say(t('{x}. Hasta aquí llega: pagado.', { x: fx(res.mult) }));
        burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360 });
        await finish(res, t('{n} aciertos seguidos', { n: res.wins }), old.bet, fx(res.mult));
        return resetRound(2600);
      }
      say(t('Bien. {x} · {cantidad} si te plantas ahora.', { x: fx(res.mult), cantidad: money(res.payoutNow) }));
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
      game = res; showCard(res.card, { flip: true }); say(t('Carta nueva. Misma apuesta, misma racha.'));
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
      say(t('Te llevas {cantidad}. Listo. O miedoso.', { cantidad: money(res.payout) }));
      await finish(res, t('Te plantaste en {x}', { x: fx(res.mult) }), old.bet);
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
      say(game.wins ? t('Bienvenido de vuelta. {x} · {cantidad} si te plantas ahora.', { x: fx(game.mult), cantidad: money(game.payoutNow) }) : t('¿Mayor o menor? Elige.'));
    }
  } catch { /* start from an empty table */ }
  setUi();

  return { unmount() { dead = true; bp.destroy(); } };
}
