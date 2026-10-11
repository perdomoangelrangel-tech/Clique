import { get, post } from '../api.js';
import { setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake } from './common.js';
import { money, sleep, ICON, esc } from '../util.js';
import { tween, toast } from '../ui.js';
import { t, CHIP_SIGN, intlLocale } from '../i18n.js';

const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
const MAX_COUNT = 9800;                       // 98.00% is the most likely bet allowed
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// a six-sided die built from six faces: pips sit on a 3x3 grid, cells 1 to 9 left to right, top to bottom
const PIPS = { 1: [5], 2: [1, 9], 3: [1, 5, 9], 4: [1, 3, 7, 9], 5: [1, 3, 5, 7, 9], 6: [1, 3, 4, 6, 7, 9] };
const dieHtml = () => `<div class="dc-throw"><div class="dc-hop"><div class="dc-tilt"><div class="dc-die">${[1, 2, 3, 4, 5, 6].map((n) =>
  `<div class="dc-face f${n}">${PIPS[n].map((c) => `<i style="grid-area:${Math.ceil(c / 3)} / ${((c - 1) % 3) + 1}"></i>`).join('')}</div>`).join('')}</div></div></div></div>`;
const FACE_UP = { 1: [0, 0], 2: [0, -90], 3: [-90, 0], 4: [90, 0], 5: [0, 90], 6: [0, 180] };          // [rotateX, rotateY] that turns that face to the front

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const RTP = meta.dice.rtp;
  host.innerHTML = `<div class="gm dice">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>${t('Pago')}</label><div class="gm-ro"><span>${CHIP_SIGN}</span><input id="payout" readonly value="0.00"><em id="payx">2.0000x</em></div></div>
      <button class="btn-bet" id="go">${t('Tirar')}</button>
      <div class="gm-note">${t('La tirada es un número de 0.00 a 99.99. Arriba gana con tu número o más; Abajo gana por debajo de él. Mueve la línea, o escribe un multiplicador, un número o una probabilidad. Entre menor la probabilidad, mayor el pago, hasta 9,900x.')}</div>
    </div>
    <div class="gm-stage dc-stage" id="stage">
      <div class="dc-hist" id="hist"></div>
      <div class="dc-ticket"><div class="dc-num" id="roll">50.00</div><div class="dc-cap" id="cap">${t('Mueve la línea. Luego tira.')}</div></div>
      <div class="dc-rail">
        <div class="dc-scale"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
        <div class="dc-track" id="track"><i class="dc-lose" id="lose"></i><i class="dc-win" id="win"></i>
          <input type="range" class="dc-slider" id="slider" min="0" max="10000" step="1" aria-label="${esc(t('Número objetivo'))}">
          <div class="dc-pin" id="pin"><span id="pin-n">50.00</span></div>
          <div class="dc-lane" id="lane">${dieHtml()}${dieHtml()}</div></div>
      </div>
      <div class="dc-fields">
        <div class="gm-field"><label for="f-mult">${t('Multiplicador')}</label><div class="gm-input"><input id="f-mult" inputmode="decimal" autocomplete="off"><span class="x">${ICON.x}</span></div></div>
        <div class="gm-field"><label for="f-target" id="f-dir">${t('Arriba de')}</label><div class="gm-input"><input id="f-target" inputmode="decimal" autocomplete="off"><button type="button" class="swap" id="swap" title="${esc(t('Cambiar arriba/abajo'))}" aria-label="${esc(t('Cambiar entre arriba y abajo'))}">${ICON.redo}</button></div></div>
        <div class="gm-field"><label for="f-chance">${t('Probabilidad de ganar')}</label><div class="gm-input"><input id="f-chance" inputmode="decimal" autocomplete="off"><span>%</span></div></div>
      </div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-dice' });
  const stage = $('#stage'), go = $('#go'), slider = $('#slider'), pin = $('#pin');
  let dir = 'over', tc = 5050, busy = false, dead = false;
  const hist = [];
  const lane = $('#lane'), throws = [...lane.querySelectorAll('.dc-throw')], hops = [...lane.querySelectorAll('.dc-hop')], dice = [...lane.querySelectorAll('.dc-die')];
  const DIE = 40, GAP = 23;                                                    // a die is 40px wide; the pair lands 46px apart
  const pose = (v, extraX = 0, extraY = 0) => { const [rx, ry] = FACE_UP[v]; return `rotateX(${rx + extraX}deg) rotateY(${ry + extraY}deg)`; };
  const poses = [pose(3), pose(5)];
  dice.forEach((d, i) => { d.style.transform = poses[i]; });

  /**
   * The pair is thrown in from the far edge of the line, rolls along it, hops, and stops on the number that came up.
   * `roll` is 0 to 99.99, the same scale the line is drawn on, so they land right on top of the marker.
   */
  function throwDice(roll, values, ms) {
    lane.classList.add('on');
    const calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const w = lane.clientWidth, fromLeft = roll >= 50;                         // always start from the longer side
    throws.forEach((throwEl, i) => {
      const off = i ? GAP : -GAP;
      throwEl.style.left = roll + '%'; throwEl.style.marginLeft = (off - DIE / 2) + 'px';
      const dx = (fromLeft ? -70 : w + 70) - (w * roll / 100 + off);            // how far from the landing spot the throw starts
      const turns = Math.max(1, Math.round(Math.abs(dx) / (4 * DIE))), way = dx < 0 ? 1 : -1;       // a cube turns a quarter for every die-width it rolls
      const from = poses[i];
      poses[i] = pose(values[i]); dice[i].style.transform = poses[i];
      if (calm) return;
      const d = ms + i * 130, delay = i * 90, o = { duration: d, delay, fill: 'backwards' };
      throwEl.animate([{ transform: `translateX(${dx}px)` }, { transform: 'translateX(0)' }], { ...o, easing: 'cubic-bezier(.1, .62, .2, 1)' });
      hops[i].animate([
        { transform: 'translateY(-58px)', easing: 'ease-in' }, { transform: 'translateY(0)', offset: .2, easing: 'ease-out' },
        { transform: 'translateY(-24px)', offset: .36, easing: 'ease-in' }, { transform: 'translateY(0)', offset: .5, easing: 'ease-out' },
        { transform: 'translateY(-9px)', offset: .64, easing: 'ease-in' }, { transform: 'translateY(0)', offset: .75 }, { transform: 'translateY(0)' },
      ], { ...o, easing: 'linear' });
      dice[i].animate([{ transform: `rotateZ(${way * turns * 360}deg) ${from}` },
        { transform: `rotateZ(0deg) ${pose(values[i], (i ? -1 : 1) * 360 * (1 + i), (i ? 1 : -1) * 360 * (2 - i))}` }], { ...o, easing: 'cubic-bezier(.1, .62, .2, 1)' });
    });
  }

  const count = () => (dir === 'over' ? 10000 - tc : tc);
  const multOf = (c) => Math.floor(RTP * 10000 / c * 10000) / 10000;
  const targetRange = () => (dir === 'over' ? [10000 - MAX_COUNT, 9999] : [1, MAX_COUNT]);
  const fixTc = () => { const [lo, hi] = targetRange(); tc = clamp(Math.round(tc), lo, hi); };
  const fmtMult = (m) => m.toFixed(4);
  const fmtChance = (c) => (c / 100).toFixed(2);

  function paint(skip = '') {
    fixTc();
    const c = count(), m = multOf(c), p = tc / 100;
    $('#lose').style.width = (dir === 'over' ? p : 100 - p) + '%'; $('#lose').style.left = dir === 'over' ? '0' : p + '%';
    $('#win').style.width = (dir === 'over' ? 100 - p : p) + '%'; $('#win').style.left = dir === 'over' ? p + '%' : '0';
    if (+slider.value !== tc) slider.value = tc;
    if (skip !== 'mult') $('#f-mult').value = fmtMult(m);
    if (skip !== 'target') $('#f-target').value = p.toFixed(2);
    if (skip !== 'chance') $('#f-chance').value = fmtChance(c);
    $('#f-dir').textContent = dir === 'over' ? t('Arriba de') : t('Abajo de');
    $('#payx').textContent = fmtMult(m) + 'x';
    const a = bp.value();
    $('#payout').value = Number.isFinite(a) ? (a * m).toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';
    go.textContent = dir === 'over' ? t('Tirar arriba de {n}', { n: p.toFixed(2) }) : t('Tirar abajo de {n}', { n: p.toFixed(2) });
    go.disabled = busy || !bp.valid();
  }
  bp.onChange(() => paint());

  slider.addEventListener('input', () => { if (busy) return; tc = +slider.value; paint(); });
  const fromCount = (c) => { c = clamp(Math.round(c), 1, MAX_COUNT); tc = dir === 'over' ? 10000 - c : c; };
  $('#f-target').addEventListener('change', (e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v) && !busy) tc = Math.round(v * 100); paint(); });
  $('#f-chance').addEventListener('change', (e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v) && !busy) fromCount(v * 100); paint(); });
  $('#f-mult').addEventListener('change', (e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v) && v >= 1 && !busy) fromCount(RTP * 10000 / v); paint(); });
  $('#swap').addEventListener('click', () => { if (busy) return; dir = dir === 'over' ? 'under' : 'over'; tc = 10000 - tc; paint(); });

  const drawHist = () => { $('#hist').innerHTML = hist.slice(-9).map((h) => `<i class="${h.win ? 'w' : 'l'}">${h.roll.toFixed(2)}</i>`).join(''); };

  go.addEventListener('click', async () => {
    if (busy || !bp.valid()) return;
    const amount = bp.value(); busy = true; slider.disabled = true; bp.lock(true); go.disabled = true;
    const prev = deduct(amount); pin.classList.remove('show', 'w', 'l'); $('#cap').textContent = 'Rolling...';
    try {
      const res = await post('/api/games/dice', { amount, direction: dir, target: tc / 100 });
      const num = $('#roll');
      pin.style.left = res.roll + '%'; pin.classList.add('show');
      throwDice(res.roll, [1 + (Math.floor(res.roll) % 6), 1 + (Math.round(res.roll * 100) % 6)], 1300);
      tween(num, 0, res.roll, (v) => v.toFixed(2), 1250);
      await sleep(1500); if (dead) return;
      $('#pin-n').textContent = res.roll.toFixed(2); pin.classList.add(res.win ? 'w' : 'l');
      num.classList.toggle('w', res.win); num.classList.toggle('l', !res.win);
      hist.push({ roll: res.roll, win: res.win }); drawHist(); setUser(res.user);
      if (res.win) {
        $('#cap').textContent = dir === 'over' ? t('{tirada} está arriba de {objetivo}. Paga {x}x.', { tirada: res.roll.toFixed(2), objetivo: res.target.toFixed(2), x: res.mult.toFixed(4) }) : t('{tirada} está abajo de {objetivo}. Paga {x}x.', { tirada: res.roll.toFixed(2), objetivo: res.target.toFixed(2), x: res.mult.toFixed(4) });
        resultPop({ net: res.payout - amount, label: t('Salió {x}', { x: res.roll.toFixed(2) }), detail: `${res.mult.toFixed(4)}x`, bet: amount });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.3, { count: 48, power: 300, colors: WIN_COLORS });
      } else {
        $('#cap').textContent = dir === 'over' ? t('{tirada}. No está arriba de {objetivo}. Ni modo.', { tirada: res.roll.toFixed(2), objetivo: res.target.toFixed(2) }) : t('{tirada}. No está abajo de {objetivo}. Ni modo.', { tirada: res.roll.toFixed(2), objetivo: res.target.toFixed(2) });
        resultPop({ net: -amount, label: t('Salió {x}', { x: res.roll.toFixed(2) }) });
        shake(stage);
      }
      ctx.refreshBets?.();
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); $('#cap').textContent = t('Mueve la línea. Luego tira.'); }
    busy = false; slider.disabled = false; bp.lock(false); paint();
  });

  paint();
  return { unmount() { dead = true; bp.destroy(); } };
}
