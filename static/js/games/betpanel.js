import { S, bus, balanceNow } from '../state.js';
import { money, moneyFull, parseAmount, floorCents } from '../util.js';

/**
 * Bet amount box shared by all games.
 * Any amount from the minimum (0.10) upward is allowed. The only cap is the player's own balance.
 * options: label, key (remembers the last bet), start, presets (quick amounts), compact (just the input row)
 */
export function betPanel(host, { label = 'Bet Amount', key = 'bet', start = 1, presets = [], compact = false } = {}) {
  let saved = start;
  try { const s = parseFloat(localStorage.getItem('clique-' + key)); if (s > 0) saved = s; } catch { /* ignore */ }
  let locked = false;
  const cbs = [];

  host.innerHTML = `<div class="bp ${compact ? 'compact' : ''}">${compact ? '' : `<div class="bp-top"><label for="bp-amt">${label}</label></div>`}
    <div class="bp-input"><span class="bp-cur">$</span><input id="bp-amt" inputmode="decimal" autocomplete="off" value="${saved}" aria-label="${label}">
      <button type="button" data-k="half" title="Half your bet">1/2</button><button type="button" data-k="dbl" title="Double your bet">2x</button><button type="button" data-k="max" title="All in">Max</button></div>
    ${presets.length ? `<div class="bp-presets">${presets.map((p) => `<button type="button" data-p="${p}">${money(p, { noCents: true })}</button>`).join('')}</div>` : ''}
    <div class="bp-err" id="bp-err"></div></div>`;
  const input = host.querySelector('#bp-amt'), err = host.querySelector('#bp-err');

  const value = () => { const v = parseAmount(input.value); return Number.isFinite(v) ? Math.round(v * 100) / 100 : NaN; };
  const validate = () => {
    const v = value(); let msg = '';
    if (!(v >= S.minBet - 1e-9)) msg = `Smallest bet is ${money(S.minBet)}.`;
    else if (v > balanceNow() + 1e-9) msg = S.demo ? 'Not enough demo chips. Reset your demo balance or bet less.' : S.acct === 'accumulated' ? 'Not enough in your accumulated account. Bet less, or switch to the weekly account.' : S.user.voucher && S.user.voucher.eligible ? 'Not enough chips. Redeem your voucher at the top, or bet less.' : 'Not enough chips. Add funds or bet less.';
    err.textContent = msg; input.closest('.bp-input').classList.toggle('bad', !!msg);
    return !msg;
  };
  const changed = () => { try { const v = value(); if (v > 0) localStorage.setItem('clique-' + key, String(v)); } catch { /* ignore */ } validate(); cbs.forEach((f) => f()); };
  const set = (v) => { input.value = String(Math.max(0, Math.round(v * 100) / 100)); changed(); };

  input.addEventListener('input', () => {
    let v = input.value.replace(/[^\d.]/g, ''); const p = v.split('.');
    if (p.length > 2) v = p[0] + '.' + p.slice(1).join('');
    if (v.includes('.')) { const [a, b] = v.split('.'); v = a + '.' + b.slice(0, 2); }
    if (v !== input.value) input.value = v; changed();
  });
  host.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b || locked) return;
    const v = value() || 0;
    if (b.dataset.k === 'half') set(Math.max(S.minBet, v / 2));
    else if (b.dataset.k === 'dbl') set(v * 2);
    else if (b.dataset.k === 'max') set(floorCents(balanceNow()));
    else if (b.dataset.p) set(Number(b.dataset.p));
  });
  const refreshBal = () => { validate(); cbs.forEach((f) => f()); };
  bus.addEventListener('user', refreshBal);
  refreshBal();

  return {
    value, valid: validate,
    onChange(f) { cbs.push(f); },
    lock(on) { locked = on; input.disabled = on; host.querySelector('.bp').classList.toggle('locked', on); },
    set,
    add(x) { set((value() || 0) + x); },
    destroy() { bus.removeEventListener('user', refreshBal); },
  };
}
