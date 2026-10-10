/* The statement: every movement in both accounts, newest first, from the server's ledger. */
import { get } from '../api.js';
import { S } from '../state.js';
import { esc, money, moneyFull, dateLong, ago, ICON } from '../util.js';
import { emptyState } from './components.js';
import { recall, remember } from '../viewstate.js';

const REASONS = {
  welcome: 'Welcome money', opening: 'Balance carried over when the two accounts began', voucher: 'Rescue voucher', deposit: 'Funds added (voted in)', 'weekly.midweek': 'Wednesday bonus',
  'weekly.allocation': 'New week: weekly account refilled', 'weekly.expired': 'New week: leftover weekly money expired', 'weekly.reward': 'Weekly reward',
  'market.buy': 'Bought shares in a bet', 'market.sell': 'Sold shares in a bet', 'market.payout': 'Bet won', 'market.refund': 'Bet refunded', 'market.withdraw': 'Withdrew a bet at cost',
  'stocks.buy': 'Bought shares on the Exchange', 'stocks.sell': 'Sold shares on the Exchange', 'store.buy': 'Bought in the Store', poker: 'Poker',
  'casino.horses': 'Horse racing', other: 'Other',
  'loan.borrow': 'Loan received', 'loan.repay': 'Loan repayment', 'loan.collect': 'Loan collected from the weekly account',
  'challenge.weekly': 'Weekly challenge reward', 'challenge.accumulated': 'Weekly challenge reward', milestone: 'Milestone reward',
  'transfer.out': 'Sent to a friend', 'transfer.in': 'Received from a friend',
};
const label = (r) => REASONS[r] || (r.startsWith('casino.') ? `Casino: ${r.slice(7)}` : r);

export default {
  async mount(root) {
    let account = recall('statement').account || '', data = null, more = [], busy = false;
    const draw = () => {
      const rows = [...data.entries, ...more].filter((e) => !account || e.account === account);
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">Every cent, written down</span><h1 class="page-title">Statement.</h1></div></div>
        <div class="acct-cards">
          <div class="card-box pad-lg acct ${account === 'weekly' ? 'sel' : ''}"><span class="lbl">Weekly account</span><b class="num">${moneyFull(data.balances.weekly)}</b>
            <p class="muted">Chips for this week: bets, the casino and poker. It is set up again every Monday and never turns into accumulated money.</p></div>
          <div class="card-box pad-lg acct ${account === 'accumulated' ? 'sel' : ''}"><span class="lbl">Accumulated account</span><b class="num">${moneyFull(data.balances.accumulated)}</b>
            <p class="muted">What you keep. Weekly rewards land here, and the Store and the Exchange spend from it.</p></div></div>
        <div class="tabs" id="stabs"><button data-a="" class="${!account ? 'active' : ''}">Both</button><button data-a="weekly" class="${account === 'weekly' ? 'active' : ''}">Weekly</button><button data-a="accumulated" class="${account === 'accumulated' ? 'active' : ''}">Accumulated</button></div>
        ${rows.length ? `<div class="card-box tbl-wrap"><table class="tbl st-tbl"><thead><tr><th>When</th><th>What</th><th>Account</th><th class="r">Amount</th><th class="r">Balance after</th><th class="id-col">Transaction</th></tr></thead><tbody>
          ${rows.map((e) => `<tr><td class="muted" title="${esc(dateLong(e.t))}">${esc(dateLong(e.t))}</td>
            <td><b>${esc(label(e.reason))}</b>${e.note ? `<div class="muted" style="font-size:12px">${esc(e.note)}</div>` : ''}${e.external ? ' <span class="tag" title="Money that came from or went outside play. It never counts as winnings.">outside play</span>' : ''}</td>
            <td><span class="tag ${e.account === 'accumulated' ? 'good' : ''}">${e.account === 'weekly' ? 'Weekly' : 'Accumulated'}</span></td>
            <td class="r num ${e.amount > 0 ? 'up' : e.amount < 0 ? 'down' : ''}">${money(e.amount, { plus: true })}</td><td class="r num">${money(e.balance)}</td>
            <td class="id-col mono muted" style="font-size:11px">${esc(e.id)}</td></tr>`).join('')}</tbody></table></div>
          ${rows.length >= 60 ? '<div style="text-align:center;margin-top:14px"><button class="btn btn-secondary" id="st-more">Show older</button></div>' : ''}`
          : emptyState({ art: 'paper', tone: 'cream', tight: true, kicker: 'Nothing here', title: 'No movements yet.', text: 'As soon as you bet, win, buy or get paid, it is written here.' })}
        ${data.older.length ? `<details style="margin-top:28px"><summary class="lbl" style="cursor:pointer">Older activity, added up by week</summary>
          <div class="card-box tbl-wrap" style="margin-top:10px"><table class="tbl"><thead><tr><th>Week of</th><th>What</th><th>Account</th><th class="r">Movements</th><th class="r">Total</th></tr></thead><tbody>
          ${data.older.filter((o) => !account || o.account === account).map((o) => `<tr><td>${esc(o.week)}</td><td>${esc(label(o.reason))}</td><td>${o.account === 'weekly' ? 'Weekly' : 'Accumulated'}</td><td class="r num">${o.count}</td><td class="r num ${o.amount >= 0 ? 'up' : 'down'}">${money(o.amount, { plus: true })}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
      </div>`;
    };
    data = await get('/api/ledger?limit=60');
    draw();
    root.addEventListener('click', async (e) => {
      const t = e.target.closest('button'); if (!t || busy) return;
      if (t.dataset.a !== undefined && t.closest('#stabs')) { account = t.dataset.a; remember('statement', { account }); draw(); }
      else if (t.id === 'st-more') {
        busy = true;
        try {
          const all = [...data.entries, ...more];
          const d = await get(`/api/ledger?limit=60&before=${all[all.length - 1].t}`);
          more.push(...d.entries); draw();
        } finally { busy = false; }
      }
    });
    return { onEvent(ev) { if (ev.type !== 'chat' && ev.type !== 'presence' && ev.type !== 'voice') get('/api/ledger?limit=60').then((d) => { data = d; more = []; draw(); }).catch(() => {}); } };
  },
};
