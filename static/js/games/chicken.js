import { get, post } from '../api.js';
import { S, setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake } from './common.js';
import { money, sleep, esc } from '../util.js';
import { toast } from '../ui.js';
import { t, intlLocale } from '../i18n.js';

const LANE_W = 100, START_W = 170, END_W = 140;
const CAR_COLORS = ['#ef476f', '#ffd166', '#06d6a0', '#4cc9f0', '#b388ff', '#ff9f1c', '#f8f9fa', '#118ab2'];
const DIFFS = [['easy', 'Fácil'], ['medium', 'Medio'], ['hard', 'Difícil'], ['hardcore', 'Extremo']];      // i18n: claves

const CHICKEN_SVG = `<svg viewBox="0 0 64 72" width="58" height="65" fill="none" stroke="#0E0C0A" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round">
  <path d="M28 59v8M38 59v8M23 69h9M34 69h9" stroke-width="6"/><path d="M28 59v8M38 59v8M23 69h9M34 69h9" stroke="#C6F432" stroke-width="2.2"/>
  <path d="M12 36Q2 26 8 18Q12 27 19 31Z" fill="#EFE6D2"/><ellipse cx="32" cy="43" rx="20" ry="18" fill="#EFE6D2"/><path d="M23 43Q32 34 43 45Q34 55 23 43Z" fill="#CFC3A8"/>
  <circle cx="44" cy="23" r="11" fill="#EFE6D2"/><path d="M39 14Q40 5 44 10Q47 3 51 11Q55 12 51 18Z" fill="#FF4B2B"/>
  <path d="M53 23l10 3-10 4z" fill="#C6F432"/><ellipse cx="52" cy="32" rx="2.7" ry="4" fill="#FF4B2B"/><circle cx="47.5" cy="21" r="2.1" fill="#0E0C0A" stroke="none"/></svg>`;
const CAR_SVG = `<svg viewBox="0 0 44 84" width="44" height="84" stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round">
  <rect x="1.5" y="14" width="7" height="16" rx="2" fill="#0E0C0A"/><rect x="35.500" y="14" width="7" height="16" rx="2" fill="#0E0C0A"/><rect x="1.500" y="54" width="7" height="16" rx="2" fill="#0E0C0A"/><rect x="35.500" y="54" width="7" height="16" rx="2" fill="#0E0C0A"/>
  <rect x="5" y="3" width="34" height="78" rx="9" class="car-body"/><rect x="10" y="22" width="24" height="17" rx="3" fill="#EFE6D2"/><rect x="10" y="52" width="24" height="12" rx="3" fill="#EFE6D2"/>
  <rect x="9" y="6" width="9" height="5" fill="#EFE6D2" stroke-width="2"/><rect x="26" y="6" width="9" height="5" fill="#EFE6D2" stroke-width="2"/></svg>`;
const TREE_SVG = `<svg class="ck-tree" viewBox="0 0 130 160" stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round"><rect x="56" y="92" width="18" height="68" fill="#CFC3A8"/>
  <circle cx="64" cy="62" r="44" fill="#2F6B47"/><circle cx="30" cy="84" r="30" fill="#2F6B47"/><circle cx="100" cy="82" r="32" fill="#2F6B47"/><circle cx="48" cy="46" r="9" fill="#4C8F63" stroke="none"/><circle cx="92" cy="64" r="7" fill="#1E3B2C" stroke="none"/></svg>`;
const LAMP_SVG = `<svg class="ck-lamp" viewBox="0 0 40 110" stroke="#0E0C0A" stroke-width="3" stroke-linejoin="round"><rect x="17" y="38" width="6" height="72" fill="#CFC3A8"/><rect x="9" y="12" width="22" height="28" rx="3" fill="#C6F432"/><rect x="9" y="12" width="22" height="6" fill="#0E0C0A"/></svg>`;

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const CK = meta.chicken;
  host.innerHTML = `<div class="gm solo chicken">
    <div class="gm-stage ck-stage" id="stage"><div class="ck-scene" id="scene"></div><div class="ck-msg" id="msg">${t('Elige tu veneno. Haz tu apuesta.')}</div></div>
    <div class="ck-bar">
      <div class="ck-bar-l"><div id="bet"></div></div>
      <div class="ck-bar-c">
        <button class="btn-cross" id="step">${t('Cruzar')}</button>
        <div class="ck-profit"><span>${t('Ganancia')}</span><b id="profit" class="num">${money(0)}</b><em id="curx">0.00x</em></div>
        <button class="btn-bet" id="play">${t('Apostar')}</button>
        <button class="btn-bet cash hidden" id="cash">${t('Plantarme')}</button>
      </div>
      <div class="ck-bar-r"><label for="diff">${t('Riesgo')}</label>
        <select class="gm-select" id="diff">${DIFFS.map(([k, l]) => `<option value="${k}" ${k === 'medium' ? 'selected' : ''}>${esc(t(l))}</option>`).join('')}</select>
        <small id="diff-info" class="muted"></small></div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-chicken' });
  const stage = $('#stage'), scene = $('#scene'), msg = $('#msg'), playBtn = $('#play'), stepBtn = $('#step'), cashBtn = $('#cash'), diffSel = $('#diff');
  let diff = 'medium', game = null, busy = false, dead = false, chickenEl = null, stepNow = 0;

  const roadH = () => stage.clientHeight || 520;
  const lanesOf = (d) => CK[d].lanes;
  const multOf = (d, k) => CK[d].mults[k];
  const centerX = (k) => (k === 0 ? START_W / 2 : START_W + (k - 1) * LANE_W + LANE_W / 2);
  const fmtM = (m) => m.toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + 'x';

  function buildScene(d, atStep = 0) {
    const n = lanesOf(d), w = START_W + n * LANE_W + END_W, h = roadH();
    scene.style.width = w + 'px'; scene.style.height = h + 'px'; scene.style.setProperty('--h', h + 'px');
    let html = `<div class="ck-start" style="width:${START_W}px">${LAMP_SVG}${TREE_SVG}</div>`;
    for (let i = 0; i < n; i++) {
      const rev = i % 2 === 1, dur = 2.3 + ((i * 37) % 17) / 10, delay = -((i * 53) % 21) / 10;
      html += `<div class="ck-lane" data-i="${i}" style="width:${LANE_W}px"><div class="ck-badge">${fmtM(multOf(d, i + 1))}</div>
        <div class="ck-car ${rev ? 'rev' : ''}" style="--dur:${dur}s;--delay:${delay}s;--c:${CAR_COLORS[(i * 5 + 3) % CAR_COLORS.length]};left:${(LANE_W - 44) / 2}px">${CAR_SVG}</div></div>`;
    }
    html += `<div class="ck-end" style="width:${END_W}px"></div><div class="ck-chicken" id="chicken">${CHICKEN_SVG}<div class="ck-shadow"></div></div>`;
    scene.innerHTML = html;
    chickenEl = scene.querySelector('#chicken'); stepNow = atStep;
    for (let i = 0; i < atStep; i++) scene.querySelector(`.ck-lane[data-i="${i}"]`).classList.add('done');
    placeChicken(atStep, true); markNext();
  }
  function placeChicken(k, instant = false) {
    if (instant) chickenEl.style.transition = 'none';
    chickenEl.style.left = (centerX(k) - 29) + 'px';
    if (instant) { void chickenEl.offsetWidth; chickenEl.style.transition = ''; }
    const sw = stage.clientWidth, sceneW = parseFloat(scene.style.width);
    const off = Math.max(0, Math.min(sceneW - sw, centerX(k) - sw * 0.3));
    if (instant) scene.style.transition = 'none';
    scene.style.transform = `translateX(${-off}px)`;
    if (instant) { void scene.offsetWidth; scene.style.transition = ''; }
    scene.querySelectorAll('.ck-lane').forEach((l) => l.classList.toggle('calm', +l.dataset.i < k));
  }
  function markNext() { scene.querySelectorAll('.ck-lane').forEach((l) => l.classList.toggle('next', !!game && +l.dataset.i === stepNow)); }
  function refreshReadout() {
    const d = game ? game.difficulty : diff;
    $('#diff-info').textContent = t('{pct}% seguro por carril · {n} carriles · hasta {max}', { pct: (CK[d].chance * 100).toFixed(0), n: CK[d].lanes, max: fmtM(CK[d].mults[CK[d].lanes]) });
    if (game) {
      const m = multOf(d, stepNow), pay = game.bet * m;
      $('#profit').textContent = money(Math.max(0, pay - game.bet)); $('#curx').textContent = fmtM(stepNow ? m : 0);
      cashBtn.textContent = stepNow ? t('Plantarme con {cantidad}', { cantidad: money(pay) }) : t('Plantarme');
    } else { $('#profit').textContent = '$0.00'; $('#curx').textContent = '0.00x'; }
  }
  function setUi() {
    const active = !!game;
    playBtn.classList.toggle('hidden', active); cashBtn.classList.toggle('hidden', !active);
    bp.lock(active || busy); diffSel.disabled = active || busy;
    stepBtn.disabled = busy || !active; cashBtn.disabled = busy || !active || stepNow < 1;
    playBtn.disabled = busy || !bp.valid();
    refreshReadout();
  }
  bp.onChange(() => { if (!game) playBtn.disabled = busy || !bp.valid(); });
  diffSel.addEventListener('change', () => { if (game || busy) return; diff = diffSel.value; buildScene(diff, 0); setUi(); });

  const say = (text) => { msg.textContent = text; };
  const hopTo = async (k) => {
    chickenEl.classList.remove('hop'); void chickenEl.offsetWidth; chickenEl.classList.add('hop');
    placeChicken(k); await sleep(470); chickenEl.classList.remove('hop');
  };
  const chickenPos = () => { const r = chickenEl.getBoundingClientRect(), s = stage.getBoundingClientRect(); return [r.left - s.left + r.width / 2, r.top - s.top + r.height / 2]; };

  async function resetRound(delay = 1800) {
    await sleep(delay); if (dead) return;
    game = null; busy = false; buildScene(diff, 0); say(t('Elige tu veneno. Haz tu apuesta.')); setUi();
  }

  playBtn.addEventListener('click', async () => {
    if (busy || game || !bp.valid()) return;
    const amount = bp.value(); busy = true; setUi();
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/chicken/start', { amount, difficulty: diff });
      setUser(res.user); game = res; stepNow = 0; buildScene(res.difficulty, 0); say(t('Dale a Cruzar. El pollito no tiene idea de lo que hace.')); markNext();
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  stepBtn.addEventListener('click', async () => {
    if (busy || !game) return;
    busy = true; setUi();
    try {
      const res = await post('/api/games/chicken/step', {});
      const lane = scene.querySelector(`.ck-lane[data-i="${stepNow}"]`);
      if (res.crashed) {
        await hopTo(stepNow + 1);
        const killer = document.createElement('div'); killer.className = 'ck-car killer'; killer.style.cssText = `--c:#ff1f3d;left:${(LANE_W - 44) / 2}px`; killer.innerHTML = CAR_SVG; lane.appendChild(killer);
        await sleep(300);
        chickenEl.classList.add('smash'); lane.classList.add('crash');
        const [x, y] = chickenPos(); burst(stage, x, y, { count: 34, colors: ['#fff', '#f1f3f5', '#ffe066', '#e5383b'], power: 280, size: 8, shape: 'rect' });
        shake(stage); stage.classList.add('flash-red'); setTimeout(() => stage.classList.remove('flash-red'), 500);
        say(t('¡Splat! En el carril {n} venía un coche.', { n: stepNow + 1 }));
        resultPop({ net: -game.bet, label: t('Aplastado en el carril {n}', { n: stepNow + 1 }) });
        setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; setUi();
        return resetRound(2200);
      }
      await hopTo(res.step);
      lane.classList.add('done'); lane.classList.remove('next'); stepNow = res.step; game = { ...game, ...res };
      const [x, y] = chickenPos(); burst(stage, x, y - 30, { count: 10, colors: ['#ffd23f', '#ffe9a8'], power: 140, size: 8, shape: 'round', life: 700 });
      if (res.finished) {
        say(t('Cruzó. Quién sabe cómo. {x}', { x: fmtM(res.mult) }));
        resultPop({ net: res.payout - game.bet, label: t('Los {n} carriles', { n: res.lanes }), detail: fmtM(res.mult), bet: game.bet });
        const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height / 2, { count: 70, power: 360 });
        setUser(res.user); ctx.refreshBets?.(); game = null; busy = true; setUi(); return resetRound(2600);
      }
      say(t('Carril {n} superado. {x} · {cantidad} si te plantas ahora', { n: res.step, x: fmtM(res.mult), cantidad: money(res.payoutNow) }));
      markNext();
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  cashBtn.addEventListener('click', async () => {
    if (busy || !game || stepNow < 1) return;
    busy = true; setUi();
    try {
      const res = await post('/api/games/chicken/cashout', {});
      chickenEl.classList.add('cheer');
      const [x, y] = chickenPos(); burst(stage, x, y - 20, { count: 42, power: 300 });
      resultPop({ net: res.payout - game.bet, label: t('Te plantaste en {x}', { x: fmtM(res.mult) }), bet: game.bet });
      say(t('Te llevas {cantidad}. Listo. O miedoso.', { cantidad: money(res.payout) }));
      setUser(res.user); ctx.refreshBets?.(); game = null; setUi(); return resetRound(2200);
    } catch (ex) { toast(ex.message, 'err'); refreshMe().catch(() => {}); }
    busy = false; setUi();
  });

  const stageWatch = window.ResizeObserver ? new ResizeObserver(() => onResize()) : null;       // the road's height follows the stage, which also changes with the pinned header
  window.addEventListener('resize', onResize); if (stageWatch) stageWatch.observe(stage);
  function onResize() {                                                    // the road follows the room it has; the round itself is untouched
    if (!chickenEl) return;
    const h = roadH(); scene.style.height = h + 'px'; scene.style.setProperty('--h', h + 'px');
    placeChicken(stepNow, true);
  }

  // resume a road crossing in progress
  try {
    const cur = await get('/api/games/state');
    if (cur.chicken && !dead) {
      game = cur.chicken; diff = game.difficulty; stepNow = game.step; diffSel.value = diff;
      buildScene(diff, stepNow); say(stepNow ? t('¿Ya de vuelta? {x} · {cantidad} si te plantas', { x: fmtM(game.mult), cantidad: money(game.payoutNow) }) : t('Dale a Cruzar. El pollito no tiene idea de lo que hace.')); markNext();
    } else buildScene(diff, 0);
  } catch { buildScene(diff, 0); }
  setUi();

  return { unmount() { dead = true; window.removeEventListener('resize', onResize); if (stageWatch) stageWatch.disconnect(); bp.destroy(); } };
}
