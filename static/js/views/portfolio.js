/* The Portfolio: where all your money is. Two pictures (the weekly account and the accumulated account), then the shares you
   own and the polls you have bet in. Everything comes from one server answer (/api/portfolio/overview), so it always agrees
   with the header, the Weekly page and the Exchange. */
import { get } from '../api.js';
import { esc, money, moneyFull, num, dateShort } from '../util.js';
import { emptyState } from './components.js';
import { recall, remember } from '../viewstate.js';

// Each kind of money gets a colour and a pattern, so the bar can be read without colour too.
const LOOK = {
  weekly: { cash: ['var(--lime)', ''], polls: ['#EFE6D2', 'p-stripes'], casino: ['var(--verm)', 'p-dots'], poker: ['#2F6B47', 'p-checker'] },
  accumulated: { cash: ['var(--lime)', ''], stocks: ['#6EC6FF', 'p-dots'] },
};
const pct = (v, total) => (total > 0 ? (v / total) * 100 : 0);
const fmtPct = (p) => (p >= 10 ? p.toFixed(0) : p.toFixed(1)) + '%';
const sign = (x) => (x > 0.004 ? 'up' : x < -0.004 ? 'down' : '');
const price = (p) => '$' + Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default {
  async mount(root) {
    let D = await get('/api/portfolio/overview'), dead = false;
    let tab = ['open', 'closed'].includes(recall('portfolio').tab) ? recall('portfolio').tab : 'open';

    const summary = (kind, A) => {
      const cash = A.parts.find((p) => p.key === 'cash').amount;
      if (A.total <= 0) return 'There is nothing in this account right now.';
      if (kind === 'weekly') {
        const working = A.parts.filter((p) => p.key !== 'cash' && p.amount > 0);
        return working.length
          ? `<b>${fmtPct(pct(cash, A.total))}</b> is cash you can spend. The other <b>${fmtPct(100 - pct(cash, A.total))}</b> is working for you: ${working.map((p) => `${money(p.amount)} ${p.label.toLowerCase()}`).join(', ')}.`
          : 'All of it is cash. Nothing is riding on a poll, a casino round or a poker table.';
      }
      const shares = A.parts.find((p) => p.key === 'stocks').amount;
      return shares > 0 ? `<b>${fmtPct(pct(cash, A.total))}</b> is cash for the Store and the Exchange. <b>${fmtPct(pct(shares, A.total))}</b> is in shares.` : 'All of it is cash. You do not own any shares.';
    };

    const accountCard = (kind, title, kicker, A, links) => {
      const looks = LOOK[kind];
      const visible = A.parts.filter((p) => p.amount > 0);
      const rows = A.parts.filter((p) => p.amount > 0 || p.key === 'cash');
      return `<section class="pfo-card card-box" aria-label="${esc(title)}">
        <div class="pfo-head"><div><span class="kicker">${kicker}</span><h2>${title}</h2></div><b class="num pfo-total" title="${moneyFull(A.total)}">${money(A.total)}</b></div>
        <p class="spread-line">${summary(kind, A)}</p>
        ${visible.length ? `<div class="spread-bar" role="img" aria-label="${esc(visible.map((p) => `${p.label} ${fmtPct(pct(p.amount, A.total))}`).join(', '))}">
          ${visible.map((p) => `<i class="${looks[p.key][1]}" style="flex:${Math.max(p.amount, A.total * 0.012)};--fill:${looks[p.key][0]}" title="${esc(p.label)}: ${moneyFull(p.amount)}"></i>`).join('')}</div>` : '<div class="spread-bar pfo-none" aria-hidden="true"></div>'}
        <div class="pfo-legend">${rows.map((p) => `<div class="pfo-row"><i class="sw ${looks[p.key][1]}" style="--fill:${looks[p.key][0]}"></i>
          <div class="pfo-what"><b>${esc(p.label)}</b><small>${esc(p.note)}</small></div>
          <b class="num" title="${moneyFull(p.amount)}">${money(p.amount)}</b><span class="num pfo-share">${fmtPct(pct(p.amount, A.total))}</span></div>`).join('')}</div>
        <p class="pfo-links">${links}</p></section>`;
    };

    const stocksBlock = () => {
      const S_ = D.stocks;
      if (!S_) return `<div class="card-box pad"><p class="muted" style="margin:0">The Exchange is not open at the moment, so your shares can't be shown. They are safe.</p></div>`;
      if (!S_.positions.length) return emptyState({ art: 'chartdown', tone: 'cream', tight: true, kicker: 'No shares', title: 'You do not own any shares.', text: 'Buy a few shares of a pretend company with your accumulated account and they will show up here.', actions: '<a class="btn btn-primary" href="#/exchange">See the Exchange</a>' });
      return `<div class="stats pfo-stats"><div class="stat"><small>Shares worth</small><b class="num">${money(S_.value)}</b></div><div class="stat"><small>What you paid</small><b class="num">${money(S_.invested)}</b></div>
          <div class="stat"><small>Unrealized gain/loss</small><b class="num ${sign(S_.unrealized)}">${money(S_.unrealized, { plus: true })}</b></div><div class="stat"><small>Realized gain/loss</small><b class="num ${sign(S_.realized)}">${money(S_.realized, { plus: true })}</b></div></div>
        <div class="card-box tbl-wrap" style="margin-top:14px"><table class="tbl pfo-tbl sh"><thead><tr><th>Company</th><th class="r">Shares</th><th class="r hide-sm">Avg cost</th><th class="r hide-sm">Price</th><th class="r">Worth</th><th class="r">Gain / loss</th></tr></thead><tbody>
          ${S_.positions.map((p) => `<tr data-sym="${esc(p.symbol)}" tabindex="0" role="link" aria-label="${esc(p.name)}" style="cursor:pointer"><td class="c"><b class="mono sym">${esc(p.symbol)}</b> ${esc(p.name)}</td><td class="r num n">${num(p.shares, 0)}</td><td class="r num hide-sm">${price(p.avgCost)}</td><td class="r num hide-sm">${price(p.price)}</td><td class="r num w">${money(p.value)}</td>
            <td class="r num g ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} <small>(${num(p.unrealizedPct, 1)}%)</small></td></tr>`).join('')}</tbody></table></div>`;
    };

    const pollsBlock = () => {
      const P = D.polls, closed = tab === 'closed', rows = closed ? P.closed : P.open;
      const tabs = `<div class="tabs" id="ptabs" style="margin-top:0">${[['open', `Open (${P.open.length})`], ['closed', `Settled (${P.closed.length})`]].map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${l}</button>`).join('')}</div>`;
      if (!rows.length) {
        return tabs + emptyState({ art: closed ? 'paper' : 'slip', tone: 'cream', tight: true, kicker: closed ? 'Nothing settled' : 'No open bets',
          title: closed ? 'No settled polls yet.' : 'You have not bet in any open poll.',
          text: closed ? 'Polls you bet in show up here once they have a result.' : 'Pick a poll and put a little on it. Your bets show up here, with what they are worth right now.',
          actions: closed ? '' : '<a class="btn btn-primary" href="#/">Browse the polls</a>' });
      }
      const sum = closed ? '' : `<p class="muted" style="margin:0 0 12px">You have <b class="num">${money(P.openInvested)}</b> in open polls, worth <b class="num">${money(P.openValue)}</b> if you cashed out right now (<span class="num ${sign(P.openPnl)}">${money(P.openPnl, { plus: true })}</span>).</p>`;
      return tabs + sum + `<div class="card-box tbl-wrap"><table class="tbl pfo-tbl pl"><thead><tr><th>Poll</th><th>Your bet</th><th class="r hide-sm">Put in</th><th class="r">${closed ? 'Paid' : 'Worth now'}</th><th class="r">Gain / loss</th>${closed ? '' : '<th class="r hide-sm">Closes</th>'}</tr></thead><tbody>
        ${rows.map((r) => `<tr data-m="${esc(r.market)}" tabindex="0" role="link" aria-label="${esc(r.question)}" style="cursor:pointer"><td class="q"><b>${esc(r.question)}</b></td>
          <td class="t"><span class="tag ${r.side === 'yes' ? 'good' : 'bad'}">${esc(r.label)}</span></td><td class="r num hide-sm">${money(r.invested)}</td><td class="r num w">${money(r.value ?? 0)}</td>
          <td class="r num g ${r.refunded ? '' : sign(r.pnl || 0)}">${r.refunded ? 'refund' : money(r.pnl || 0, { plus: true })}</td>
          ${closed ? '' : `<td class="r hide-sm muted">${r.status === 'closed' ? 'waiting for a result' : r.closes ? dateShort(r.closes) : 'no closing date'}</td>`}</tr>`).join('')}</tbody></table></div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">Where your money is</span><h1 class="page-title">Your portfolio.</h1></div></div>
        <div class="stats pfo-tiles"><div class="stat"><small>Everything you own</small><b class="num" title="${moneyFull(D.total)}">${money(D.total)}</b></div>
          <div class="stat"><small>Weekly account</small><b class="num" title="${moneyFull(D.weekly.total)}">${money(D.weekly.total)}</b></div>
          <div class="stat"><small>Accumulated account</small><b class="num" title="${moneyFull(D.accumulated.total)}">${money(D.accumulated.total)}</b></div></div>
        <div class="pfo-grid">
          ${accountCard('weekly', 'Your weekly money', 'This week\'s chips', D.weekly, `Set back to your weekly amount every Monday. <a href="#/weekly">The Weekly</a> · <a href="#/games">Casino</a> · <a href="#/">Polls</a>`)}
          ${accountCard('accumulated', 'Your accumulated money', 'What you keep', D.accumulated, `Weekly rewards land here. <a href="#/store">Store</a> · <a href="#/exchange">Exchange</a> · <a href="#/statement">Statement</a>`)}
        </div>
        <div class="section-head" style="margin-top:44px"><div><span class="kicker">On the Exchange</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">Your shares</h2></div></div>
        ${stocksBlock()}
        <div class="section-head" style="margin-top:44px"><div><span class="kicker">Paid from the weekly account</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">Polls you have bet in</h2></div></div>
        ${pollsBlock()}
        <p class="muted" style="margin:26px 2px 0;font-size:13px;max-width:72ch">Open poll bets and shares are valued at what you could get for them right now, not what you paid. Practice money is never counted here.</p></div>`;
    };
    draw();

    const reload = async () => { try { const next = await get('/api/portfolio/overview'); if (dead) return; D = next; draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', (e) => {
      const t = e.target.closest('#ptabs button');
      if (t) { tab = t.dataset.t; remember('portfolio', { tab }); draw(); return; }
      const sym = e.target.closest('[data-sym]'); if (sym) { location.hash = `#/exchange/${sym.dataset.sym}`; return; }
      const m = e.target.closest('[data-m]'); if (m) location.hash = `#/market/${m.dataset.m}`;
    });
    root.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const r = e.target.closest('[data-sym],[data-m]'); if (!r) return;
      location.hash = r.dataset.sym ? `#/exchange/${r.dataset.sym}` : `#/market/${r.dataset.m}`;
    });
    const timer = setInterval(reload, 15000);                 // prices move; look again every so often
    return {
      onEvent(ev) { if (['market', 'week', 'reward', 'market-edited'].includes(ev.type)) reload(); },
      unmount() { dead = true; clearInterval(timer); },
    };
  },
};
