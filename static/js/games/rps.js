/* Rock Paper Scissors against the house. Win and you climb the ladder (1.96x, then it doubles with every win), lose and it is over,
   draw and you simply go again. Cash out after any win. The server draws the house's pick only after you have picked. */
import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX } from './common.js';
import { money, sleep, esc } from '../util.js';
import { toast } from '../ui.js';
import { t } from '../i18n.js';

const STROKE = 'stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"';
const ICONS = {
  rock: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M9 42l6-18 17-8 19 8 6 17-6 14-21 6-16-6z" fill="#CFC3A8"/><path d="M21 33l9-4M37 23l9 7M26 46l11 3" fill="none" stroke-width="2.4"/></g></svg>`,
  paper: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M14 5h23l13 13v41H14z" fill="#EFE6D2"/><path d="M37 5v13h13" fill="#CFC3A8"/><path d="M21 29h22M21 38h22M21 47h14" fill="none" stroke-width="2.6"/></g></svg>`,
  scissors: `<svg viewBox="0 0 64 64" aria-hidden="true"><g ${STROKE}><path d="M17 6L45 52" fill="none" stroke-width="9"/><path d="M17 6L45 52" fill="none" stroke="#EFE6D2" stroke-width="3.4"/><path d="M47 6L19 52" fill="none" stroke-width="9"/><path d="M47 6L19 52" fill="none" stroke="#EFE6D2" stroke-width="3.4"/>
    <circle cx="19" cy="54" r="8" fill="#C6F432"/><circle cx="45" cy="54" r="8" fill="#FF4B2B"/><circle cx="32" cy="29" r="3.6" fill="#0E0C0A"/></g></svg>`,
};
const MOVES = ['rock', 'paper', 'scissors'];
const NAME = { rock: 'Piedra', paper: 'Papel', scissors: 'Tijera' };                                          // i18n: claves
const WINS_LINE = { rock: 'La piedra rompe la tijera.', paper: 'El papel envuelve la piedra.', scissors: 'La tijera corta el papel.' };      // i18n: claves
const DRAW_LINE = { rock: 'Los dos sacaron piedra.', paper: 'Los dos sacaron papel.', scissors: 'Los dos sacaron tijera.' };            // i18n: claves
const BEATS = { rock: 'scissors', paper: 'rock', scissors: 'paper' };

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const LADDER = meta.rps.ladder;
  host.innerHTML = `<div class="gm rps">
    <div class="gm-panel">
      <div id="bet"></div>
      <button class="btn-bet" id="play">${t('Apostar')}</button>
      <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      <div class="hl-read" aria-live="polite">
        <div><small>${t('Pago total')}</small><b class="num" id="pay">${money(0)}</b></div>
        <div><small>${t('Ganancia')}</small><b class="num" id="profit">${money(0)}</b></div>
        <div><small>${t('Multiplicador')}</small><b class="num" id="mult">0.00x</b></div>
      </div>
      <div class="gm-note">${t('Elige piedra, papel o tijera contra la casa. Si ganas, subes: el primer triunfo paga 1.96x y cada triunfo después lo dobla, hasta {n} seguidos. Un empate se repite sin costo. Si pierdes, se va la apuesta. Plántate después de cualquier triunfo. Cada paso devuelve 98% en promedio.', { n: LADDER.length })}</div>
    </div>
    <div class="gm-stage rp-stage" id="stage">
      <div class="rp-ladder" id="ladder" aria-label="${esc(t('La escalera'))}"></div>
      <div class="rp-duel">
        <div class="rp-side"><small>${t('Tú')}</small><div class="rp-pick" id="you"><span class="q">?</span></div></div>
        <div class="rp-vs">VS</div>
        <div class="rp-side"><small>${t('La casa')}</small><div class="rp-pick" id="house"><span class="q">?</span></div></div>
      </div>
      <div class="rp-msg" id="msg">${t('Haz una apuesta y luego elige tu jugada.')}</div>
      <div class="rp-choices" id="choices">${MOVES.map((m) => `<button class="rp-choice" data-m="${m}" disabled><span class="rp-ico">${ICONS[m]}</span><b>${esc(t(NAME[m]))}</b></button>`).join('')}</div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-rps' });
  const stage = $('#stage'), msg = $('#msg'), playBtn = $('#play'), cashBtn = $('#cash'), you = $('#you'), house = $('#house');
  let game = null, busy = false, dead = false;

  const say = (text) => { msg.textContent = text; };
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
    cashBtn.textContent = game && game.wins ? t('Plantarme con {cantidad}', { cantidad: money(game.payoutNow) }) : t('Plantarme');
    drawLadder();
  }
  bp.onChange(() => { if (!game) playBtn.disabled = busy || !bp.valid(); });

  async function resetRound(delay = 2000) {
    await sleep(delay); if (dead) return;
    game = null; busy = false; pickBox(you, null); pickBox(house, null); say(t('Haz una apuesta y luego elige tu jugada.')); setUi();
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
      setUser(res.user); game = res; pickBox(you, null); pickBox(house, null); say(t('Elige tu jugada.'));
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
      if (res.result === 'draw') { say(`${t(DRAW_LINE[pick])} ${t('Empate: otra vez, no cuesta nada.')}`); game = res; }
      else if (res.result === 'win') {
        say(`${t(WINS_LINE[pick])} ${t('{x} · {cantidad} si te plantas ahora.', { x: fmtX(res.mult), cantidad: money(res.payoutNow) })}`);
        burst(stage, r.width / 2, r.height * 0.45, { count: 18, colors: ['#C6F432', '#EFE6D2'], power: 200, size: 8, life: 800 });
        game = res;
        if (res.finished) {
          say(t('{n} triunfos seguidos. Llegaste a lo más alto de la escalera: pagado.', { n: res.wins }));
          burst(stage, r.width / 2, r.height / 2, { count: 80, power: 380 });
          finish(res, t('{n} triunfos seguidos', { n: res.wins }), old.bet, fmtX(res.mult)); return resetRound(2800);
        }
      } else {
        shake(stage); stage.classList.add('flash-red'); setTimeout(() => stage.classList.remove('flash-red'), 500);
        say(`${t(WINS_LINE[res.house])} ${t('Gana la casa.')}`);
        finish(res, t('Perdiste contra {jugada}', { jugada: t(NAME[res.house]) }), old.bet); return resetRound(2400);
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
      say(t('Te llevas {cantidad}. Listo. O miedoso.', { cantidad: money(res.payout) }));
      finish(res, t('Te plantaste en {x}', { x: fmtX(res.mult) }), old.bet); return resetRound(2200);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  const reduced = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  try {                                                         // pick up a round that was in progress
    const cur = await get('/api/games/state');
    if (cur.rps && !dead) { game = cur.rps; say(game.wins ? t('Bienvenido de vuelta. {x} · {cantidad} si te plantas ahora.', { x: fmtX(game.mult), cantidad: money(game.payoutNow) }) : t('Elige tu jugada.')); }
  } catch { /* an empty table */ }
  setUi();
  return { unmount() { dead = true; bp.destroy(); } };
}
