import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, fmtX } from './common.js';
import { money, sleep, ICON } from '../util.js';
import { coinFace } from '../art.js';
import { toast } from '../ui.js';
import { t, tp, intlLocale, CHIP_SIGN } from '../i18n.js';

const sideWord = (s) => (s === 'heads' ? t('Águila') : t('Sol'));
const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const MULTS = meta.coinflip.mults, MAX = meta.coinflip.maxFlips;
  host.innerHTML = `<div class="gm coinflip">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>${t('Modo')}</label><div class="seg" id="mode"><button data-m="classic" class="active">${t('Clásico')}</button><button data-m="target">${t('Racha')}</button></div></div>
      <div class="gm-field hidden" id="flips-f"><label for="flips">${t('Volados seguidos')} <b class="num" id="flips-n">2</b></label><input type="range" class="gm-range" id="flips" min="1" max="${MAX}" value="2"></div>
      <div class="gm-field"><label>${t('Lo que cantas')}</label>
        <div class="cf-sides" id="sides"><button data-s="heads" class="on">${ICON.crown} ${t('Águila')}</button><button data-s="tails">${ICON.star} ${t('Sol')}</button></div></div>
      <div class="gm-field"><label>${t('Pago')}</label><div class="gm-ro"><span>${CHIP_SIGN}</span><input id="payout" readonly value="0.00"><em id="payx">1.98x</em></div></div>
      <button class="btn-bet" id="go">${t('Lanzar')}</button>
      <div class="gm-note">${t('El clásico paga 1.98x. Modo racha: canta el mismo lado varios volados seguidos. Dos seguidos pagan 3.96x, diez pagan 1,013.76x. Un solo fallo y se acabó.')}</div>
    </div>
    <div class="gm-stage cf-stage" id="stage">
      <div class="cf-toss" id="toss"><div class="cf-coin" id="coin"><div class="cf-face">${coinFace('heads')}</div><div class="cf-face back">${coinFace('tails')}</div></div></div>
      <div class="cf-trail" id="trail"></div>
      <div class="cf-sub" id="sub">${t('Canta. Luego lanza.')}</div>
      <div class="cf-stats">
        <div class="gm-field"><label>${t('Multiplicador')}</label><div class="gm-ro"><input id="mult" readonly><span>x</span></div></div>
        <div class="gm-field"><label>${t('Probabilidad')}</label><div class="gm-ro"><input id="chance" readonly><span>%</span></div></div>
      </div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-coinflip' });
  const stage = $('#stage'), coin = $('#coin'), toss = $('#toss'), trail = $('#trail'), sub = $('#sub'), go = $('#go');
  let mode = 'classic', side = 'heads', flips = 2, busy = false, dead = false, angle = 0;

  const count = () => (mode === 'classic' ? 1 : flips);
  const refresh = () => {
    const n = count(), mult = MULTS[n - 1], a = bp.value();
    $('#payout').value = Number.isFinite(a) ? (a * mult).toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';
    $('#payx').textContent = fmtX(mult);
    $('#mult').value = mult.toFixed(2); $('#chance').value = (100 / 2 ** n).toFixed(n > 7 ? 3 : 2);
    $('#flips-n').textContent = String(flips);
    go.textContent = mode === 'classic' ? t('Lanzar') : t('Lanzar {n}', { n });
    go.disabled = busy || !bp.valid();
  };
  bp.onChange(refresh);
  $('#mode').addEventListener('click', (e) => {
    const b = e.target.closest('[data-m]'); if (!b || busy) return;
    mode = b.dataset.m; host.querySelectorAll('#mode button').forEach((x) => x.classList.toggle('active', x === b));
    $('#flips-f').classList.toggle('hidden', mode === 'classic'); refresh();
  });
  $('#flips').addEventListener('input', (e) => { flips = +e.target.value; refresh(); });
  $('#sides').addEventListener('click', (e) => {
    const b = e.target.closest('[data-s]'); if (!b || busy) return;
    side = b.dataset.s; host.querySelectorAll('#sides button').forEach((x) => x.classList.toggle('on', x === b));
  });

  // The coin turns on its edge a few times and lands on the face the server picked.
  async function flipTo(result) {
    let a = angle + 1080;
    a = a - (a % 360) + (result === 'heads' ? 0 : 180);
    if (a <= angle + 720) a += 360;
    toss.classList.remove('toss'); void toss.offsetWidth; toss.classList.add('toss');
    coin.style.transform = `rotateY(${a}deg)`; angle = a;
    await sleep(1050);
  }
  const chip = (win) => `<i class="cf-chip ${win ? 'w' : 'l'}" title="${win ? t('Atinaste') : t('Fallaste')}">${win ? ICON.check : ICON.x}</i>`;

  go.addEventListener('click', async () => {
    if (busy || !bp.valid()) return;
    const amount = bp.value(); busy = true; go.disabled = true; bp.lock(true); trail.innerHTML = '';
    const prev = deduct(amount); sub.textContent = t('En el aire...');
    try {
      const body = { amount, side, mode };
      if (mode === 'target') body.flips = flips;
      const res = await post('/api/games/coinflip', body);
      for (const r of res.results) {
        if (dead) return;
        await flipTo(r);
        trail.insertAdjacentHTML('beforeend', chip(r === side));
        await sleep(160);
      }
      setUser(res.user);
      const last = res.results[res.results.length - 1];
      if (res.win) {
        sub.textContent = res.flips > 1 ? t('{lado}. {n} seguidos. Paga {x}.', { lado: sideWord(last), n: res.flips, x: fmtX(res.mult) }) : t('{lado}. Paga {x}.', { lado: sideWord(last), x: fmtX(res.mult) });
        resultPop({ net: res.payout - amount, label: res.flips > 1 ? t('{n} seguidos', { n: res.flips }) : t('Le atinaste'), detail: fmtX(res.mult), bet: amount });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.4, { count: 54, power: 320, colors: WIN_COLORS });
      } else {
        sub.textContent = t('{lado}. Lado equivocado. A la moneda le da igual.', { lado: sideWord(last) });
        resultPop({ net: -amount, label: sideWord(last) });
        shake(stage);
      }
      ctx.refreshBets?.();
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); sub.textContent = t('Canta. Luego lanza.'); }
    busy = false; bp.lock(false); refresh();
  });

  refresh();
  return { unmount() { dead = true; bp.destroy(); } };
}
