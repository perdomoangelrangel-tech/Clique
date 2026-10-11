import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX, progressHtml, paintProgress } from './common.js';
import { money, sleep, esc } from '../util.js';
import { glyph } from '../art.js';
import { toast } from '../ui.js';
import { t, tp } from '../i18n.js';

const HOLE = `<svg viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round"><ellipse cx="32" cy="50" rx="27" ry="9" fill="#2A2420"/><path d="M5 50a27 9 0 0 0 54 0v3a27 9 0 0 1-54 0z" fill="#2F6B47"/></g></svg>`;
const MOLE = `<svg viewBox="0 0 64 64" aria-hidden="true">${glyph('mole')}</svg>`;
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
// hole 0 in the middle, holes 1-6 in a ring, starting at the top
const SPOTS = [[50, 50], ...Array.from({ length: 6 }, (_, k) => { const a = (-90 + k * 60) * Math.PI / 180; return [50 + 33 * Math.cos(a), 50 + 33 * Math.sin(a)]; })];

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const HOLES = meta.moles.holes, TABLES = meta.moles.tables;
  host.innerHTML = `<div class="gm moles">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label for="moles">${t('Topos')} <b class="num" id="mn">3</b> <small class="pays" id="chance"></small></label>
        <input type="range" class="gm-range" id="moles" min="1" max="${HOLES - 1}" value="3"></div>
      ${progressHtml()}
      <button class="btn-bet" id="go">${t('Apostar')}</button>
      <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      <div class="gm-note">${t('{n} hoyos. En cada ronda, de 1 a {max} esconden un topo. Elige un hoyo: si tiene topo, ganas la ronda y se multiplica tu pago. Un hoyo vacío lo pierde todo. Después de cada acierto, plántate o pega otra vez.', { n: HOLES, max: HOLES - 1 })}</div>
    </div>
    <div class="gm-stage ml-stage" id="stage"><div class="ml-field" id="field">${SPOTS.map(([x, y], i) => `<button class="ml-hole" data-h="${i}" style="left:${x}%;top:${y}%" aria-label="${esc(t('Hoyo {n}', { n: i + 1 }))}"><span class="ml-art">${HOLE}</span></button>`).join('')}</div>
      <div class="ml-msg" id="msg">${t('Siete hoyos. Algunos tienen topos. Apuesta.')}</div></div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-moles' });
  const stage = $('#stage'), field = $('#field'), msg = $('#msg'), go = $('#go'), cash = $('#cash'), slider = $('#moles');
  let moles = 3, game = null, busy = false, dead = false;
  const say = (text) => { msg.textContent = text; };
  const hole = (i) => field.querySelector(`[data-h="${i}"]`);
  const tableNow = () => TABLES[String(moles)];

  function resetHoles() { field.querySelectorAll('.ml-hole').forEach((h) => { h.className = 'ml-hole'; h.querySelector('.ml-art').innerHTML = HOLE; }); }
  function pop(i) { const h = hole(i); h.classList.add('up'); h.querySelector('.ml-art').innerHTML = MOLE; }

  function paint() {
    const T = tableNow(), active = !!game;
    $('#mn').textContent = String(moles); $('#chance').textContent = t('{pct}% por hoyo', { pct: (moles / HOLES * 100).toFixed(1) });
    paintProgress(host, { bet: game ? game.bet : bp.value(), mult: game && game.hits ? game.mult : null, nextMult: game ? game.nextMult : T[1] });
    go.classList.toggle('hidden', active); cash.classList.toggle('hidden', !active);
    bp.lock(active || busy); slider.disabled = active || busy;
    cash.disabled = busy || !active || !game.hits;
    cash.textContent = active && game.hits ? t('Plantarme con {cantidad}', { cantidad: money(game.payoutNow) }) : t('Plantarme');
    go.disabled = busy || !bp.valid();
    field.classList.toggle('live', active && !busy);
  }
  bp.onChange(paint);
  slider.addEventListener('input', () => { if (game || busy) return; moles = +slider.value; paint(); });

  async function settle(res, win) {
    setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; paint();
    await sleep(win ? 1700 : 2100); if (dead) return;
    busy = false; resetHoles(); say(t('Siete hoyos. Algunos tienen topos. Apuesta.')); paint();
  }

  go.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; paint();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/moles/start', { amount, moles });
      setUser(res.user); game = res; resetHoles(); say(t('{n} de {total} hoyos tienen topo. Elige uno.', { n: moles, total: HOLES }));
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  field.addEventListener('click', async (e) => {
    const h = e.target.closest('.ml-hole'); if (!h || !game || busy) return;
    busy = true; paint();
    const idx = +h.dataset.h;
    try {
      const res = await post('/api/games/moles/pick', { hole: idx });
      resetHoles();
      res.popped.forEach((i, k) => setTimeout(() => pop(i), k * 70));
      await sleep(260 + res.popped.length * 70); if (dead) return;
      const b = hole(idx).getBoundingClientRect(), s = stage.getBoundingClientRect(), x = b.left - s.left + b.width / 2, y = b.top - s.top + b.height / 2;
      hole(idx).classList.add(res.hit ? 'hit' : 'miss');
      if (!res.hit) {
        shake(stage); burst(stage, x, y, { count: 24, power: 220, colors: ['#FF4B2B', '#EFE6D2', '#0E0C0A'] });
        say(t('Vacío. Los topos estaban en los otros hoyos. Pierdes {cantidad}.', { cantidad: money(game.bet) }));
        resultPop({ net: -game.bet, label: t('Hoyo vacío') });
        return settle(res, false);
      }
      burst(stage, x, y, { count: 22, power: 230, size: 8, colors: WIN_COLORS });
      game = { ...game, ...res };
      if (res.finished) {
        say(t('{n} aciertos seguidos. Los topos están furiosos. {x}.', { n: res.hits, x: fmtX(res.mult) }));
        resultPop({ net: res.payout - game.bet, label: t('Máximo de golpes'), detail: fmtX(res.mult), bet: game.bet });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360, colors: WIN_COLORS });
        return settle(res, true);
      }
      say(t('¡Pum! {x} · {cantidad} si te plantas. Siguiente: {sig}.', { x: fmtX(res.mult), cantidad: money(res.payoutNow), sig: fmtX(res.nextMult) }));
      await sleep(900); if (dead) return;
      resetHoles();
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  cash.addEventListener('click', async () => {
    if (busy || !game || !game.hits) return;
    busy = true; paint();
    try {
      const res = await post('/api/games/moles/cashout', {});
      say(t('Te llevas {cantidad}. Los topos no lo van a olvidar.', { cantidad: money(res.payout) }));
      resultPop({ net: res.payout - game.bet, label: t('Te plantaste en {x}', { x: fmtX(res.mult) }), bet: game.bet });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.45, { count: 46, power: 300, colors: WIN_COLORS });
      return settle(res, true);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; paint();
  });

  try {
    const cur = await get('/api/games/state');
    if (cur.moles && !dead) {
      game = cur.moles; moles = game.moles; slider.value = String(moles);
      say(game.hits ? t('Bienvenido de vuelta. {x} · {cantidad} si te plantas.', { x: fmtX(game.mult), cantidad: money(game.payoutNow) }) : t('{n} de {total} hoyos tienen topo. Elige uno.', { n: moles, total: HOLES }));
    }
  } catch { /* new round */ }
  paint();
  return { unmount() { dead = true; bp.destroy(); } };
}
