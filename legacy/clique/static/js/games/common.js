import { S, setUser, wallet } from '../state.js';
import { tween } from '../ui.js';
import { suitSvg } from '../art.js';
import { money, esc, ICON } from '../util.js';

/** Show the stake leaving the wallet right away (the server's answer replaces it afterwards). */
export function deduct(amount) {
  closeResultPop();                                    // a new round starts: the last result goes away
  if (!S.demo && S.acct === 'accumulated') {           // the accumulated account: the weekly balance is not touched
    const was = S.user;
    setUser({ ...was, accum: Math.max(0, Math.round(((was.accum || 0) - amount) * 100) / 100) });
    return was;
  }
  const prev = wallet();
  setUser({ ...prev, balance: Math.max(0, Math.round((prev.balance - amount) * 100) / 100), netWorth: prev.netWorth - amount });
  return prev;
}

const WIN_COLORS = ['#ffd23f', '#3ddc84', '#4dabf7', '#ff6b9d', '#fff'];

/** Confetti / coin burst made of tiny DOM pieces, animated with the Web Animations API. */
export function burst(container, x, y, { count = 36, colors = WIN_COLORS, power = 260, gravity = 420, size = 9, shape = 'mix', life = 1100 } = {}) {
  const layer = document.createElement('div');
  layer.style.cssText = 'position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:30';
  container.appendChild(layer);
  for (let i = 0; i < count; i++) {
    const p = document.createElement('i');
    const s = size * (0.6 + Math.random() * 0.8);
    const kind = shape === 'mix' ? (Math.random() < 0.5 ? 'rect' : 'round') : shape;
    p.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${s}px;height:${kind === 'rect' ? s * 0.55 : s}px;background:${colors[i % colors.length]};border-radius:${kind === 'round' ? '50%' : '2px'};`;
    layer.appendChild(p);
    const a = Math.random() * Math.PI * 2, v = power * (0.35 + Math.random() * 0.75);
    const dx = Math.cos(a) * v, dy = Math.sin(a) * v - power * 0.35, t = life * (0.7 + Math.random() * 0.6) / 1000;
    const rot = (Math.random() - 0.5) * 900;
    p.animate([
      { transform: 'translate(0,0) rotate(0deg)', opacity: 1 },
      { transform: `translate(${dx * t * 0.6}px, ${dy * t * 0.6 + 0.5 * gravity * (t * 0.6) ** 2}px) rotate(${rot * 0.6}deg)`, opacity: 1, offset: 0.6 },
      { transform: `translate(${dx * t}px, ${dy * t + 0.5 * gravity * t * t}px) rotate(${rot}deg)`, opacity: 0 },
    ], { duration: t * 1000, easing: 'cubic-bezier(.2,.7,.4,1)', fill: 'forwards' });
  }
  setTimeout(() => layer.remove(), life * 1.5);
}

export const countUp = (el, to, fmt, ms = 700) => tween(el, 0, to, fmt, ms);

/** Big floating result text in the middle of a stage. */
export function banner(stage, html, kind = 'win', ms = 2200) {
  const b = document.createElement('div');
  b.className = `gm-banner ${kind}`;
  b.innerHTML = html;
  stage.appendChild(b);
  setTimeout(() => { b.classList.add('out'); setTimeout(() => b.remove(), 400); }, ms);
  return b;
}

export const shake = (el) => { el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake'); };


/** A paper playing card (the same one Blackjack deals). `down` shows the back, which flips over when removed. */
export function cardEl(card, { down = false, instant = false } = {}) {
  const el = document.createElement('div');
  const red = card && (card.s === 'H' || card.s === 'D');
  el.className = `pc ${red ? 'red' : ''} ${down ? 'down' : ''} ${instant ? '' : 'deal'}`;
  el.innerHTML = `<div class="pc-in"><div class="pc-front"></div><div class="pc-back"><span></span></div></div>`;
  if (card && !card.hidden) fillFront(el, card);
  return el;
}
export function fillFront(el, card) {
  el.classList.toggle('red', card.s === 'H' || card.s === 'D');
  el.querySelector('.pc-front').innerHTML = `<span class="tl">${card.r}${suitSvg(card.s, 15)}</span><span class="mid">${suitSvg(card.s, 44)}</span><span class="br">${card.r}${suitSvg(card.s, 15)}</span>`;
}

export const fmtX = (m) => (m == null ? '—' : m.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + 'x');

/** "Current profit  >  Next" readout used by the step games (Mines, Moles, Tower). */
export const progressHtml = () => `<div class="gm-prog" aria-live="polite">
  <div class="pr-top"><div><small>Current profit</small><b class="num" data-pr="profit">$0.00</b></div><span class="pr-arrow">${ICON.chevR}</span><div><small>Next</small><b class="num" data-pr="next">$0.00</b></div></div>
  <div class="pr-bot"><span class="num" data-pr="mult">0.00x</span><span class="num" data-pr="nextmult">—</span></div></div>`;

/** bet = the stake in play (or the amount typed), mult = current multiplier (null before the round starts). */
export function paintProgress(root, { bet = 0, mult = null, nextMult = null } = {}) {
  const q = (k) => root.querySelector(`[data-pr="${k}"]`);
  const b = Number.isFinite(bet) ? bet : 0;
  q('profit').textContent = money(mult ? Math.max(0, b * mult - b) : 0);
  q('next').textContent = nextMult ? money(Math.max(0, b * nextMult - b)) : '$0.00';
  q('mult').textContent = fmtX(mult ?? 0);
  q('nextmult').textContent = nextMult ? fmtX(nextMult) : '—';
}


// ---- the pop-up that says what a round came to --------------------------------------------------------------
let pop = null, popTimer = null, popAway = null;

export function closeResultPop() {
  clearTimeout(popTimer);
  if (popAway) { document.removeEventListener('pointerdown', popAway, true); popAway = null; }
  const el = pop; pop = null;
  if (el) { el.classList.add('out'); setTimeout(() => el.remove(), 260); }
}

/**
 * A window in the middle of the screen: "You won +$12.00" / "You lost -$5.00" / "Push".
 * net = what the round came to in dollars (profit if positive, the loss if negative). It closes by itself,
 * on the next click anywhere, or when the next round starts.
 */
export function resultPop({ net = 0, label = '', detail = '', bet = null, ms = 4000 } = {}) {
  closeResultPop();
  const cents = Math.round(net * 100), kind = cents > 0 ? 'win' : cents < 0 ? 'lose' : 'push';
  const amount = Math.abs(cents) / 100, sign = kind === 'win' ? '+' : '\u2212';
  const meta = [label, detail, bet != null ? `Bet ${money(bet)}` : ''].filter(Boolean).map(esc).join(' \u00b7 ');
  const el = document.createElement('div');
  el.className = `gm-pop ${kind}`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `<button class="gm-pop-x" aria-label="Close">${ICON.x}</button>${S.demo ? '<span class="gm-pop-demo">Demo bets</span>' : ''}
    <span class="gm-pop-head">${kind === 'win' ? 'You won' : kind === 'lose' ? 'You lost' : 'Push'}</span>
    <b class="gm-pop-amt num">${kind === 'push' ? 'Bet back' : sign + money(0)}</b>${meta ? `<span class="gm-pop-meta">${meta}</span>` : ''}
    <i class="gm-pop-bar" style="animation-duration:${ms}ms"></i>`;
  document.body.appendChild(el);
  pop = el;
  const amt = el.querySelector('.gm-pop-amt');
  if (kind !== 'push') { amt.textContent = sign + money(amount); tween(amt, 0, amount, (v) => sign + money(v), 650); }      // the true number is already there if the count-up never runs
  popTimer = setTimeout(closeResultPop, ms);
  popAway = () => closeResultPop();
  document.addEventListener('pointerdown', popAway, true);
  return el;
}
