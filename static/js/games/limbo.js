import { post } from '../api.js';
import { S, setUser, refreshMe } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, shake, resultPop } from './common.js';
import { money, ICON } from '../util.js';
import { toast } from '../ui.js';
import { t, th, intlLocale, CHIP_SIGN } from '../i18n.js';

const RTP = 0.99, MIN_T = 1.01, MAX_T = 1000000;
const clampT = (v) => Math.min(MAX_T, Math.max(MIN_T, Math.round((Number.isFinite(v) ? v : 2) * 100) / 100));
const fmtX = (v) => v.toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + 'x';

export default async function mount(host, ctx = {}) {
  host.innerHTML = `<div class="gm">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label>${t('Pago')}</label><div class="gm-ro"><span>${CHIP_SIGN}</span><input id="payout" readonly value="0.00"><em id="payx">2.00x</em></div></div>
      <button class="btn-bet" id="go">${t('Apostar')}</button>
      <div class="gm-note">${t('Tu probabilidad de ganar es 99 entre tu objetivo. Los objetivos van de 1.01x a 1,000,000x. La ambición está permitida.')}</div>
    </div>
    <div class="gm-stage limbo-stage" id="stage"><canvas id="cv"></canvas>
      <div class="limbo-hist" id="hist"></div>
      <div class="limbo-card" id="card"><div class="limbo-num" id="num">1.00x</div></div>
      <div class="limbo-sub" id="sub">${t('Elige un número. Dale a Apostar.')}</div>
      <div class="limbo-ctl">
        <div class="gm-field"><label for="target">${t('Multiplicador')}</label><div class="gm-input"><input id="target" inputmode="decimal" value="2.00" autocomplete="off"><span class="x">${ICON.x}</span></div></div>
        <div class="gm-field"><label for="chance">${t('Probabilidad')}</label><div class="gm-input"><input id="chance" inputmode="decimal" autocomplete="off"><span>%</span></div></div>
      </div>
    </div>
  </div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-limbo' });
  const stage = $('#stage'), cv = $('#cv'), ctx2 = cv.getContext('2d'), numEl = $('#num'), card = $('#card'), sub = $('#sub');
  const tIn = $('#target'), cIn = $('#chance'), payout = $('#payout'), go = $('#go');
  let dead = false, busy = false, target = 2;

  // --------------------------------------------------------------- inputs
  const fmtChance = (c) => (c >= 10 ? c.toFixed(2) : c >= 1 ? c.toFixed(3) : c.toFixed(5)).replace(/\.?0+$/, '');
  const updatePayout = () => {
    const a = bp.value();
    payout.value = Number.isFinite(a) ? (a * target).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';
    $('#payx').textContent = fmtX(target);
    go.disabled = busy || !bp.valid();
  };
  const setTarget = (v, fromChance = false) => {
    target = clampT(v);
    if (!fromChance) tIn.value = target.toFixed(2);
    cIn.value = fmtChance(Math.min(98.02, RTP / target * 100));
    updatePayout();
  };
  tIn.addEventListener('input', () => { const v = parseFloat(tIn.value); if (Number.isFinite(v)) { target = clampT(v); cIn.value = fmtChance(Math.min(98.02, RTP / target * 100)); updatePayout(); } });
  tIn.addEventListener('blur', () => setTarget(parseFloat(tIn.value)));
  cIn.addEventListener('input', () => { const c = parseFloat(cIn.value); if (c > 0) { target = clampT(RTP / (c / 100)); tIn.value = target.toFixed(2); updatePayout(); } });
  cIn.addEventListener('blur', () => setTarget(target));
  bp.onChange(updatePayout);
  setTarget(2);

  // --------------------------------------------------------------- canvas scene
  let dpr = 1, W = 0, H = 0, GY = 0;
  // The canvas follows the stage's real size (it changes with the window AND with the pinned header, so the window alone is not enough), and the screen's pixel ratio (browser zoom changes it without changing the stage), so it stays sharp.
  const resize = () => { dpr = Math.min(2, window.devicePixelRatio || 1); const r = stage.getBoundingClientRect(); W = r.width; H = r.height; GY = H - (window.matchMedia('(max-width: 640px)').matches ? 190 : 124); cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px'; ctx2.setTransform(dpr, 0, 0, dpr, 0, 0); };
  const stageWatch = window.ResizeObserver ? new ResizeObserver(resize) : null;
  resize(); window.addEventListener('resize', resize); if (stageWatch) stageWatch.observe(stage);
  const stars = Array.from({ length: 70 }, () => ({ x: Math.random(), y: Math.random(), z: 0.3 + Math.random() * 0.9 }));
  let parts = [];
  const fly = { on: false, p: 0, v: 1, result: 1, rx: 0, ry: 0, boom: null };
  let speed = 0.05;

  function drawRocket(x, y, ang, flame) {
    const c = ctx2, INK = '#0E0C0A';
    c.save(); c.translate(x, y); c.rotate(ang);
    c.lineJoin = 'round'; c.lineWidth = 3; c.strokeStyle = INK;
    if (flame > 0) {                                   // flat two-layer flame that flickers
      const fl = 22 + Math.random() * 14 * flame;
      c.fillStyle = '#C6F432'; c.beginPath(); c.moveTo(-20, -9); c.lineTo(-20 - fl * 1.5, 0); c.lineTo(-20, 9); c.closePath(); c.fill(); c.stroke();
      c.fillStyle = '#EFE6D2'; c.beginPath(); c.moveTo(-20, -4.5); c.lineTo(-20 - fl * .8, 0); c.lineTo(-20, 4.5); c.closePath(); c.fill();
    }
    c.fillStyle = '#FF4B2B';                           // fins
    c.beginPath(); c.moveTo(-4, -12); c.lineTo(-22, -26); c.lineTo(-24, -9); c.closePath(); c.fill(); c.stroke();
    c.beginPath(); c.moveTo(-4, 12); c.lineTo(-22, 26); c.lineTo(-24, 9); c.closePath(); c.fill(); c.stroke();
    c.fillStyle = '#EFE6D2';                           // body
    c.beginPath(); c.moveTo(34, 0); c.bezierCurveTo(24, -15, 0, -16, -22, -11); c.lineTo(-22, 11); c.bezierCurveTo(0, 16, 24, 15, 34, 0); c.fill(); c.stroke();
    c.fillStyle = '#FF4B2B';                           // nose
    c.beginPath(); c.moveTo(34, 0); c.bezierCurveTo(27, -9, 19, -13, 14, -13); c.lineTo(14, 13); c.bezierCurveTo(19, 13, 27, 9, 34, 0); c.fill(); c.stroke();
    c.fillStyle = '#2F6B47'; c.beginPath(); c.arc(1, 0, 6, 0, 7); c.fill(); c.stroke();
    c.restore();
  }
  function spawn(x, y, n, o) {
    for (let i = 0; i < n; i++) { const a = o.a ?? Math.random() * 6.28, s = (o.s || 60) * (0.4 + Math.random()); parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: o.life || 0.7, t: 0, c: o.c[i % o.c.length], r: o.r || 3 }); }
  }
  let last = performance.now();
  function frame(now) {
    if (dead) return;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const c = ctx2;
    c.clearRect(0, 0, W, H);
    c.fillStyle = '#141110'; c.fillRect(0, 0, W, H);
    for (const s of stars) {
      s.x -= speed * s.z * dt; if (s.x < 0) { s.x += 1; s.y = Math.random(); }
      c.globalAlpha = 0.25 + 0.4 * s.z; c.fillStyle = '#EFE6D2';
      c.fillRect(s.x * W, s.y * H, 1 + speed * 70 * s.z, 1.5 * s.z);
    }
    c.globalAlpha = 1;
    c.fillStyle = '#1E3B2C'; c.fillRect(0, GY, W, H - GY);                       // the ground
    c.fillStyle = '#2F6B47'; c.fillRect(W * .12 - 46, GY - 6, 92, 6);               // the pad
    c.strokeStyle = '#0E0C0A'; c.lineWidth = 3; c.beginPath(); c.moveTo(0, GY); c.lineTo(W, GY); c.stroke();

    if (fly.on) {
      fly.rx = W * (0.12 + 0.68 * fly.p);
      const alt = Math.min(1, Math.log(fly.v) / Math.log(Math.max(fly.result, 3)));
      fly.ry = (GY - 30) - ((GY - 30) - H * 0.26) * alt;
      const ang = -0.5 + (1 - fly.p) * 0.12;
      spawn(fly.rx - 24, fly.ry + 6, 2, { a: Math.PI - 0.5 + (Math.random() - .5) * .6, s: 90, life: 0.55, c: ['#C6F432', '#EFE6D2', '#A09482'], r: 3.4 });
      drawRocket(fly.rx, fly.ry, ang, 1);
    } else if (!fly.boom) {
      drawRocket(W * 0.12, GY - 26, -0.5, 0.15);
    }
    parts = parts.filter((p) => (p.t += dt) < p.life);
    for (const p of parts) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 120 * dt; c.globalAlpha = 1 - p.t / p.life; c.fillStyle = p.c; c.beginPath(); c.arc(p.x, p.y, p.r * (1 - p.t / p.life * .4), 0, 7); c.fill(); }
    c.globalAlpha = 1;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  const hist = [];
  const drawHist = () => { $('#hist').innerHTML = hist.slice(0, 9).map((h) => `<span class="${h.win ? 'w' : 'l'}">${h.r.toLocaleString(undefined, { minimumFractionDigits: 2 })}x</span>`).join(''); };

  function animate(res) {
    return new Promise((resolve) => {
      const result = res.result;
      const dur = Math.min(3600, 800 + Math.log10(result) * 800);
      numEl.className = 'limbo-num flying'; card.className = 'limbo-card'; sub.textContent = t('Objetivo {x}', { x: fmtX(res.target) });
      speed = 0.35; fly.result = Math.max(1.01, result); fly.v = 1; fly.p = 0; fly.on = result > 1.005; fly.boom = null;
      const t0 = performance.now();
      const step = (now) => {
        if (dead) return resolve();
        const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 2.2);
        fly.p = e; fly.v = Math.exp(Math.log(result) * e);
        numEl.textContent = fmtX(k >= 1 ? result : fly.v);
        if (res.win && fly.v >= res.target) numEl.classList.add('hit');
        if (k < 1) return requestAnimationFrame(step);
        speed = 0.05;
        const rx = fly.rx || W * .12, ry = fly.ry || GY - 30;
        fly.on = false;
        if (res.win) {
          numEl.className = 'limbo-num win'; card.className = 'limbo-card win'; sub.innerHTML = `<b style="color:#C6F432">${money(res.payout - bp.value(), { plus: true })}</b> · ${th('superó {x}', { x: fmtX(res.target) })}`;
          burst(stage, rx, ry, { count: 46, power: 300 });
        } else {
          fly.boom = true; numEl.className = 'limbo-num lose'; card.className = 'limbo-card lose'; sub.innerHTML = `<b style="color:#FF4B2B">−${money(bp.value())}</b> · ${th('necesitaba {x}', { x: fmtX(res.target) })}`;
          spawn(rx, ry, 60, { s: 220, life: 0.9, c: ['#FF4B2B', '#C6F432', '#EFE6D2', '#0E0C0A'], r: 4.5 }); shake(stage);
          setTimeout(() => { fly.boom = null; }, 700);
        }
        resolve();
      };
      requestAnimationFrame(step);
    });
  }

  async function play() {
    if (busy || !bp.valid()) return;
    const amount = bp.value();
    busy = true; go.disabled = true; bp.lock(true);
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/limbo', { amount, target });
      await animate(res);
      hist.unshift({ r: res.result, win: res.win }); drawHist();
      setUser(res.user); ctx.refreshBets?.();
      resultPop({ net: res.win ? res.payout - amount : -amount, label: t('Salió {x}', { x: fmtX(res.result) }), detail: t('Objetivo {x}', { x: fmtX(res.target) }), bet: res.win ? amount : null });
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); }
    busy = false; bp.lock(false); updatePayout();
  }
  go.addEventListener('click', play);
  host.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); e.target.blur(); play(); } });

  return { unmount() { dead = true; window.removeEventListener('resize', resize); if (stageWatch) stageWatch.disconnect(); bp.destroy(); } };
}
