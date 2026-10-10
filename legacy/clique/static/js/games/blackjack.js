import { get, post } from '../api.js';
import { setUser, refreshMe, wallet } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, cardEl, fillFront } from './common.js';
import { money, sleep, ICON } from '../util.js';
import { toast } from '../ui.js';

const CHIPS = [0.1, 1, 5, 10, 25, 100, 500];
const chipLabel = (v) => (v >= 1000 ? `${v / 1000}K` : String(v));

export default async function mount(host, ctx = {}) {
  host.innerHTML = `<div class="gm solo bj">
    <div class="gm-stage bj-stage" id="stage">
      <div class="bj-shoe"><i></i><i></i><i></i></div>
      <div class="bj-oval">
        <div class="bj-zone bj-dealer"><div class="bj-label">Dealer <span class="bj-total" id="d-total"></span></div><div class="bj-cards" id="d-cards"></div></div>
        <div class="bj-ribbon">BLACKJACK PAYS 3 TO 2<small>DEALER STANDS ON 17</small></div>
        <div class="bj-hands" id="hands"></div>
      </div>
      <button class="btn-bet bj-deal" id="deal">Deal</button>
      <div class="bj-bar">
        <div class="bj-actions" id="actions">
          <button data-a="double"><b>x2</b> Double</button><button data-a="hit">${ICON.plus} Hit</button><button data-a="stand">${ICON.hand} Stand</button><button data-a="split">${ICON.split} Split</button></div>
        <div class="bj-betrow">
          <div class="rl-chips sm" id="chips">${CHIPS.map((v) => `<button class="rchip v${String(v).replace('.', '_')}" data-v="${v}" title="Add ${money(v)}"><span>${chipLabel(v)}</span></button>`).join('')}</div>
          <div id="bet" class="bj-bet-in"></div>
        </div>
      </div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-blackjack', compact: true });
  const stage = $('#stage'), dealBtn = $('#deal'), actions = $('#actions'), dCards = $('#d-cards'), dTotal = $('#d-total'), handsEl = $('#hands');
  let busy = false, dead = false, handEls = [], dealerCount = 0, holeEl = null, st = null;

  $('#chips').addEventListener('click', (e) => { const c = e.target.closest('[data-v]'); if (c && !busy && !(st && st.phase === 'player')) bp.add(Number(c.dataset.v)); });

  const totalText = (h) => (h.status === 'bust' ? 'Bust' : h.blackjack ? 'Blackjack' : h.soft && h.total < 21 ? `Soft ${h.total}` : String(h.total));

  function buildHands(hands) {
    handsEl.innerHTML = ''; handEls = [];
    hands.forEach(() => {
      const el = document.createElement('div'); el.className = 'bj-hand';
      el.innerHTML = `<div class="bj-cards"></div><div class="bj-meta"><span class="bj-total"></span><span class="bj-bet">$0</span><span class="bj-res hidden"></span></div>`;
      handsEl.appendChild(el); handEls.push({ el, cards: el.querySelector('.bj-cards'), count: 0 });
    });
  }
  const updateMeta = (hands, active, done) => hands.forEach((h, i) => {
    const e = handEls[i]; if (!e) return;
    e.el.classList.toggle('active', !done && i === active && hands.length > 1);
    e.el.querySelector('.bj-total').textContent = h.cards.length ? totalText(h) : '';
    e.el.querySelector('.bj-bet').textContent = money(h.bet, { noCents: true });
    e.el.querySelector('.bj-bet').title = money(h.bet);
  });

  async function addCard(container, card, { down = false, instant = false } = {}) {
    const el = cardEl(card, { down, instant });
    container.appendChild(el);
    if (!instant) await sleep(330);
    return el;
  }

  /** Brings the table in line with the server's state, animating whatever is new. */
  async function sync(state, { instant = false } = {}) {
    st = state;
    const hands = state.hands;
    const fresh = !handEls.length;
    if (handEls.length && hands.length !== handEls.length) {      // split: rebuild and deal the new second cards
      buildHands(hands);
      for (let i = 0; i < hands.length; i++) { await addCard(handEls[i].cards, hands[i].cards[0], { instant: true }); handEls[i].count = 1; }
      for (let i = 0; i < hands.length; i++) { await addCard(handEls[i].cards, hands[i].cards[1]); handEls[i].count = 2; updateMeta(hands, state.active, false); }
    }
    if (fresh) {
      buildHands(hands); dCards.innerHTML = ''; dealerCount = 0; holeEl = null;
      if (instant) {
        hands[0].cards.forEach((c) => handEls[0].cards.appendChild(cardEl(c, { instant: true }))); handEls[0].count = hands[0].cards.length;
        state.dealer.forEach((c) => { const e = cardEl(c, { down: !!c.hidden, instant: true }); dCards.appendChild(e); if (c.hidden) holeEl = e; }); dealerCount = state.dealer.length;
      } else {
        await addCard(handEls[0].cards, hands[0].cards[0]); handEls[0].count = 1; updateMeta(hands, 0, false);
        await addCard(dCards, state.dealer[0]); dealerCount = 1;
        dTotal.textContent = state.dealer[0].r === 'A' ? '11' : ['10', 'J', 'Q', 'K'].includes(state.dealer[0].r) ? '10' : state.dealer[0].r;
        await addCard(handEls[0].cards, hands[0].cards[1]); handEls[0].count = 2; updateMeta(hands, 0, false);
        const hole = state.dealer[1]; holeEl = await addCard(dCards, hole, { down: true }); dealerCount = 2;
        if (!hole.hidden) { await sleep(300); holeEl.classList.remove('down'); holeEl = null; await sleep(600); }
      }
    }
    for (let i = 0; i < hands.length; i++) {                       // hit / double
      const e = handEls[i];
      while (e.count < hands[i].cards.length) { await addCard(e.cards, hands[i].cards[e.count]); e.count++; updateMeta(hands, state.active, false); }
    }
    updateMeta(hands, state.active, state.phase === 'done');
    if (state.phase === 'done') {                                   // dealer reveals and draws
      if (holeEl && !state.dealer[1].hidden) { fillFront(holeEl, state.dealer[1]); holeEl.classList.remove('down'); holeEl = null; await sleep(650); }
      while (dealerCount < state.dealer.length) { await addCard(dCards, state.dealer[dealerCount]); dealerCount++; await sleep(250); }
      dTotal.textContent = state.dealer.length === 2 && state.dealerTotal === 21 ? 'Blackjack' : state.dealerTotal > 21 ? `Bust (${state.dealerTotal})` : String(state.dealerTotal);
    } else dTotal.textContent = String(state.dealerTotal);
  }

  function setControls(state) {
    const playing = !!state && state.phase === 'player';
    dealBtn.classList.toggle('hidden', playing);
    const btn = (a) => actions.querySelector(`[data-a="${a}"]`);
    btn('hit').disabled = !playing || busy; btn('stand').disabled = !playing || busy;
    btn('double').disabled = !playing || busy || !state.canDouble; btn('split').disabled = !playing || busy || !state.canSplit;
    bp.lock(playing || busy);
    host.querySelector('#chips').classList.toggle('locked', playing || busy);
    if (!playing) dealBtn.disabled = busy || !bp.valid();
  }
  bp.onChange(() => { if (!st || st.phase === 'done') dealBtn.disabled = busy || !bp.valid(); });

  function showResult(state) {
    state.hands.forEach((h, i) => {
      const r = handEls[i].el.querySelector('.bj-res'); r.classList.remove('hidden');
      r.className = `bj-res ${h.result === 'win' || h.result === 'blackjack' ? 'w' : h.result === 'push' ? 'p' : 'l'}`;
      r.textContent = { win: 'Win', blackjack: 'Blackjack', push: 'Push', lose: 'Lose', bust: 'Bust' }[h.result];
      handEls[i].el.classList.add(h.result === 'win' || h.result === 'blackjack' ? 'won' : h.result === 'push' ? 'pushed' : 'lost');
    });
    const profit = Math.round((state.payout - state.totalBet) * 100) / 100;
    const hasBJ = state.hands.some((h) => h.result === 'blackjack');
    if (profit > 0) {
      resultPop({ net: profit, label: hasBJ ? 'Blackjack' : 'You beat the dealer', bet: state.totalBet });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.55, { count: 44, power: 300 });
    } else if (profit === 0) resultPop({ net: 0, label: 'Nobody wins' });
    else { resultPop({ net: profit, label: state.hands.every((h) => h.status === 'bust') ? 'You busted' : 'Dealer wins' }); shake(stage); }
  }

  async function finishRound(state, user) {
    await sync(state);
    if (state.phase === 'done') { showResult(state); ctx.refreshBets?.(); }
    setUser(user);
    busy = false; setControls(state);
  }

  dealBtn.addEventListener('click', async () => {
    if (busy || !bp.valid()) return;
    const amount = bp.value(); busy = true; dealBtn.disabled = true; bp.lock(true);
    dealerCount = 0; holeEl = null; handEls = []; handsEl.innerHTML = ''; dCards.innerHTML = ''; dTotal.textContent = ''; st = null;
    stage.querySelectorAll('.gm-banner').forEach((b) => b.remove());
    const prev = deduct(amount);
    try {
      const res = await post('/api/games/blackjack/deal', { amount });
      if (res.phase === 'player') setUser(res.user);
      await finishRound(res, res.user);
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); busy = false; bp.lock(false); dealBtn.disabled = false; setControls(null); }
  });

  actions.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-a]'); if (!b || busy || b.disabled) return;
    const a = b.dataset.a; busy = true; setControls(st);
    const extra = (a === 'double' || a === 'split') ? st.hands[st.active].bet : 0;
    const prev = extra ? deduct(extra) : wallet();
    try {
      const res = await post('/api/games/blackjack/action', { action: a });
      if (res.phase === 'player') setUser(res.user);
      await finishRound(res, res.user);
    } catch (ex) { toast(ex.message, 'err'); if (extra) setUser(prev); refreshMe().catch(() => {}); busy = false; setControls(st); }
  });

  // resume a hand that was in progress
  try {
    const cur = await get('/api/games/state');
    if (cur.blackjack && !dead) { busy = true; await sync(cur.blackjack, { instant: true }); busy = false; setControls(cur.blackjack); toast('Your hand was waiting for you.'); }
    else setControls(null);
  } catch { setControls(null); }

  return { unmount() { dead = true; bp.destroy(); } };
}
