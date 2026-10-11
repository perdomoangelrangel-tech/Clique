/* The Stock Exchange: ten made-up companies, one shared market, paid for from the accumulated account.
   Everything here is simulated, and says so. Prices come from the server; the order ticket asks the server for a quote and
   only the server decides what an order costs. */
import { get, post } from '../api.js';
import { S, setUser } from '../state.js';
import { esc, money, moneyFull, num, ICON, ago, roll } from '../util.js';
import { toast, modal } from '../ui.js';
import { recall, remember } from '../viewstate.js';
import { drawStockChart } from './stockchart.js';
import { emptyState } from './components.js';

const rid = () => 'ord-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const sign = (x) => (x > 0 ? 'up' : x < 0 ? 'down' : '');
const arrow = (x) => (x > 0 ? '▲' : x < 0 ? '▼' : '■');
const price = (p) => '$' + Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const spark = (pts, up) => {
  if (!pts || pts.length < 2) return '';
  const lo = Math.min(...pts), hi = Math.max(...pts), w = 96, h = 28, d = pts.map((p, i) => `${i ? 'L' : 'M'}${((i / (pts.length - 1)) * w).toFixed(1)} ${(h - 2 - ((p - lo) / ((hi - lo) || 1)) * (h - 4)).toFixed(1)}`).join('');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><path d="${d}" fill="none" stroke="${up ? 'var(--pos)' : 'var(--neg)'}" stroke-width="2" stroke-linejoin="round"/></svg>`;
};
const SIM = '<span class="tag sim" title="Everything on the exchange is made up: the companies, the prices, the news.">Simulated</span>';

export default {
  async mount(root, [sym]) {
    let dead = false, timer = null;
    const stop = () => { dead = true; clearInterval(timer); };
    const every = (fn, ms) => { timer = setInterval(() => { if (!document.hidden && !dead) fn().catch(() => {}); }, ms); };
    if (sym === 'portfolio') { const h = await portfolioPage(root, every); return { unmount: stop, onEvent: h }; }
    if (sym) { const h = await companyPage(root, sym.toUpperCase(), every); return { unmount: () => { stop(); h.unmount && h.unmount(); }, onEvent: h.onEvent }; }
    await listPage(root, every);
    return { unmount: stop };
  },
};

// ------------------------------------------------------------------------------------------------ the market
async function listPage(root, every) {
  let D = await get('/api/stocks');
  const draw = () => {
    root.innerHTML = `<div class="page">
      <div class="section-head"><div><span class="kicker">Pretend shares, real feelings</span><h1 class="page-title">The exchange. ${SIM}</h1></div>
        <div class="ex-bal"><span class="lbl">Accumulated account</span><b class="num" data-bal>${moneyFull(D.accumulated)}</b></div></div>
      <p class="muted" style="max-width:72ch;margin:0 0 18px">Ten made-up companies whose prices move every second, the same for everybody. Buy and sell with your <b>accumulated</b> account. No borrowing and no short selling. Nothing you do moves the prices.
        ${D.catchup && D.catchup.replayedSeconds >= 180 ? `<span class="muted"> The market was replayed for ${Math.round(D.catchup.replayedSeconds / 60)} minutes after the server was off${D.catchup.capped ? ' (the outage was longer: only the last part is replayed)' : ''}.</span>` : ''}</p>
      <div class="card-box tbl-wrap"><table class="tbl ex-tbl"><thead><tr><th>Company</th><th class="hide-sm">Sector</th><th class="hide-sm">Last hour</th><th class="r">Price</th><th class="r">Today</th><th class="r hide-md">You hold</th></tr></thead><tbody>
        ${D.stocks.map((s) => `<tr data-sym="${s.symbol}" tabindex="0" role="link" aria-label="${esc(s.name)}">
          <td><b class="mono sym">${s.symbol}</b> <span>${esc(s.name)}</span>${s.halted ? ' <span class="tag bad">Paused</span>' : ''}</td><td class="hide-sm muted">${esc(s.sector)}</td>
          <td class="hide-sm">${spark(s.spark, s.changePct >= 0)}</td><td class="r num"><b data-p="${s.symbol}">${price(s.price)}</b></td>
          <td class="r num ${sign(s.change)}" data-c="${s.symbol}">${arrow(s.change)} ${num(Math.abs(s.changePct), 2)}%</td>
          <td class="r num hide-md muted">${s.mine ? `${num(s.mine.shares, 0)} · ${money(s.mine.value)}` : '—'}</td></tr>`).join('')}</tbody></table></div>
      <div class="section-head" style="margin-top:34px"><div><span class="kicker">Simulated news</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">What moved the market</h2></div></div>
      <div class="card-box pad" id="ex-news">${newsHtml(D.news)}</div></div>`;
  };
  const newsHtml = (n) => (n.length ? n.map((x) => `<div class="list-row"><span class="tag sim">Simulated</span><div class="grow">${esc(x.text)}</div><span class="muted mono" style="font-size:12px">${ago(x.t)}</span></div>`).join('') : '<p class="quiet">Quiet so far.</p>');
  draw();
  root.addEventListener('click', (e) => { const r = e.target.closest('[data-sym]'); if (r) location.hash = `#/exchange/${r.dataset.sym}`; });
  root.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const r = e.target.closest('[data-sym]'); if (r) location.hash = `#/exchange/${r.dataset.sym}`; } });
  every(async () => {
    const before = Object.fromEntries(D.stocks.map((s) => [s.symbol, s.price]));
    D = await get('/api/stocks');
    for (const s of D.stocks) {                                    // update in place, so the page does not jump while you read it
      const p = root.querySelector(`[data-p="${s.symbol}"]`), c = root.querySelector(`[data-c="${s.symbol}"]`); if (!p) return draw();
      roll(p, price(s.price)); p.parentElement.classList.toggle('tick-up', s.price > before[s.symbol]); p.parentElement.classList.toggle('tick-down', s.price < before[s.symbol]);
      c.className = `r num ${sign(s.change)}`; c.textContent = `${arrow(s.change)} ${num(Math.abs(s.changePct), 2)}%`;
    }
    root.querySelector('[data-bal]').textContent = moneyFull(D.accumulated);
    root.querySelector('#ex-news').innerHTML = newsHtml(D.news);
  }, 1000);
}

// ------------------------------------------------------------------------------------------------ a company
async function companyPage(root, sym, every) {
  const VIEW = 'exchange:' + sym, mem = recall(VIEW);
  let interval = mem.interval || 'live', side = mem.side || 'buy', shares = mem.shares || '', D = null, lastDraw = 0, timerQ = null, dead = false;
  const intervals = [['live', 'Live'], ['1m', '1 min'], ['5m', '5 min'], ['1h', '1 hour'], ['1d', '1 day']];
  const load = async () => {
    const iv = interval === 'live' ? '1m' : interval;
    D = await get(`/api/stocks/${sym}?interval=${iv}&limit=${interval === 'live' ? 15 : 240}`);
  };
  try { await load(); } catch (ex) { root.innerHTML = `<div class="page">${emptyState({ art: 'wheel', tone: 'verm', kicker: 'No such company', title: 'That ticker does not exist.', text: esc(ex.message), actions: '<a class="btn btn-primary" href="#/exchange">Back to the exchange</a>' })}</div>`; return { unmount() {} }; }

  const head = () => `<div class="section-head"><div><span class="kicker mono">${D.symbol} · ${esc(D.sector)}</span><h1 class="page-title">${esc(D.name)} ${SIM}</h1></div>
    <div class="ex-price"><b class="num" id="px">${price(D.price)}</b><span class="num ${sign(D.change)}" id="chg">${arrow(D.change)} ${price(Math.abs(D.change))} (${num(Math.abs(D.changePct), 2)}%) today</span></div></div>
    ${D.halted ? '<div class="notice bad">Trading is paused for a moment after a very sharp move (a simulated circuit breaker). Prices keep moving; orders resume shortly.</div>' : ''}`;
  const ticket = () => `<div class="card-box pad-lg otk"><div class="tk-top"><div class="seg2" role="tablist"><button data-side="buy" class="${side === 'buy' ? 'on y' : ''}">Buy</button><button data-side="sell" class="${side === 'sell' ? 'on n' : ''}">Sell</button></div></div>
      <label class="lbl" for="tk-sh">Shares (whole numbers)</label>
      <div class="bp-input" style="margin:6px 0"><input id="tk-sh" inputmode="numeric" autocomplete="off" value="${esc(shares)}" placeholder="0" aria-label="Number of shares"><button type="button" data-q="1">+1</button><button type="button" data-q="10">+10</button><button type="button" data-q="max">${side === 'buy' ? 'Max' : 'All'}</button></div>
      <div class="tk-lines" id="tk-lines"></div><div class="error-text" id="tk-err" style="min-height:18px"></div>
      <button class="btn ${side === 'buy' ? 'btn-primary' : 'btn-no'} btn-block" id="tk-go" ${D.halted ? 'disabled' : ''}>Review ${side}</button>
      <p class="muted" style="font-size:12.5px;margin:10px 0 0">Paid from your accumulated account. You see the exact price and total, from the server, before you confirm. The price can move up to 0.50% before you do; beyond that nothing is filled.</p></div>`;
  const mine = () => { const p = D.position; return p.shares ? `<div class="card-box pad-lg"><span class="lbl">You hold</span><b class="num" style="font-size:28px;display:block">${num(p.shares, 0)} shares</b>
      <div class="kv"><span>Average cost</span><b class="num">${price(p.avgCost)}</b><span>Worth if sold now</span><b class="num">${money(p.value)}</b><span>Unrealized</span><b class="num ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} (${num(p.unrealizedPct, 2)}%)</b><span>Realized so far</span><b class="num ${sign(p.realized)}">${money(p.realized, { plus: true })}</b></div></div>`
      : `<div class="card-box pad-lg"><span class="lbl">You hold</span><p class="muted" style="margin:6px 0 0">Nothing yet.${p.realized ? ` Realized so far: <b class="num ${sign(p.realized)}">${money(p.realized, { plus: true })}</b>` : ''}</p></div>`; };

  function drawAll() {
    root.innerHTML = `<div class="page">${head()}
      <div class="ex-grid"><div class="stack">
        <div class="card-box pad-lg"><div class="ex-ctl"><div class="tabs" id="ivs" style="margin:0;border:0">${intervals.map(([k, l]) => `<button data-iv="${k}" class="${interval === k ? 'active' : ''}">${l}</button>`).join('')}</div>
          <span class="muted mono" style="font-size:11.5px">${interval === 'live' ? 'last 10 minutes · every second' : 'candles'}</span></div><div id="chart"></div>
          <div class="ex-stats"><div><span class="lbl">24h high</span><b class="num">${price(D.high24)}</b></div><div><span class="lbl">24h low</span><b class="num">${price(D.low24)}</b></div>
            <div><span class="lbl">You can buy at</span><b class="num" id="ask">${price(D.ask)}</b></div><div><span class="lbl">You can sell at</span><b class="num" id="bid">${price(D.bid)}</b></div></div></div>
        <div class="card-box pad-lg"><span class="lbl">About</span><p style="margin:6px 0 0">${esc(D.about)}</p></div>
        <div class="card-box pad-lg"><span class="lbl">Simulated news</span><div id="news">${D.news.length ? D.news.map((n) => `<div class="list-row"><span class="tag sim">Simulated</span><div class="grow">${esc(n.text)}</div><span class="muted mono" style="font-size:12px">${ago(n.t)}</span></div>`).join('') : '<p class="quiet">Nothing has happened to this company lately.</p>'}</div></div></div>
        <div class="stack ex-side"><div id="ticket">${ticket()}</div><div id="mine">${mine()}</div>
          <div class="card-box pad-lg"><span class="lbl">Your recent transactions here</span><div id="trades">${tradesHtml()}</div></div></div></div></div>`;
    paintChart(); paintLines();
  }
  const tradesHtml = () => (D.trades.length ? D.trades.map((t) => `<div class="list-row"><span class="tag ${t.side === 'buy' ? 'good' : 'bad'}">${t.side}</span><div class="grow">${num(t.shares, 0)} @ ${price(t.price)}</div><b class="num">${money(t.total)}</b><span class="muted mono" style="font-size:11.5px">${ago(t.t)}</span></div>`).join('') : '<p class="quiet">None yet.</p>');
  const paintChart = () => { const el = root.querySelector('#chart'); if (el) drawStockChart(el, { type: interval === 'live' ? 'line' : 'candles', ticks: interval === 'live' ? D.ticks.filter(([t]) => t >= D.t - 600_000) : [], candles: interval === 'live' ? [] : D.candles, height: 300 }); };
  const paintLines = () => {
    const el = root.querySelector('#tk-lines'); if (!el) return;
    const n = parseInt(shares, 10) || 0, px = side === 'buy' ? D.ask : D.bid, tot = n * px;
    const bal = D.accumulated, after = side === 'buy' ? bal - tot : bal + tot;
    el.innerHTML = `<div><span>${side === 'buy' ? 'Price you pay (ask)' : 'Price you get (bid)'}</span><b class="num">${price(px)}</b></div>
      <div><span>${side === 'buy' ? 'Estimated cost' : 'Estimated proceeds'}</span><b class="num">${money(tot)}</b></div>
      <div><span>Accumulated account after</span><b class="num ${side === 'buy' && after < 0 ? 'down' : ''}">${money(after)}</b></div>`;
    if (side === 'buy' && n && tot > bal) root.querySelector('#tk-err').textContent = `You need ${money(tot - bal)} more in your accumulated account.`;
    else if (side === 'sell' && n > D.position.shares) root.querySelector('#tk-err').textContent = `You only own ${num(D.position.shares, 0)} share${D.position.shares === 1 ? '' : 's'}.`;
    else root.querySelector('#tk-err').textContent = '';
  };
  const paintLive = () => {
    const p = root.querySelector('#px'); if (!p) return;
    roll(p, price(D.price)); const c = root.querySelector('#chg'); c.className = `num ${sign(D.change)}`; c.textContent = `${arrow(D.change)} ${price(Math.abs(D.change))} (${num(Math.abs(D.changePct), 2)}%) today`;
    root.querySelector('#ask').textContent = price(D.ask); root.querySelector('#bid').textContent = price(D.bid);
    paintLines();
    if (Date.now() - lastDraw > (interval === 'live' ? 1000 : 5000)) { paintChart(); lastDraw = Date.now(); }
    root.querySelector('#mine').innerHTML = mine(); root.querySelector('#trades').innerHTML = tradesHtml();
  };

  // ---- the order: ask the server for a quote, then confirm that quote
  async function review() {
    const n = parseInt(shares, 10);
    const err = root.querySelector('#tk-err');
    if (!(n >= 1)) { err.textContent = 'Enter how many shares.'; return; }
    err.textContent = '';
    let q;
    try { q = await post('/api/stocks/quote', { symbol: sym, side, shares: n }); } catch (ex) { err.textContent = ex.message; return; }
    confirmOrder(q);
  }
  function confirmOrder(q, note = '') {
    const orderId = rid();
    const m = modal(`<span class="lbl">Review your order · ${SIM}</span><h2>${q.side === 'buy' ? 'Buy' : 'Sell'} ${num(q.shares, 0)} share${q.shares === 1 ? '' : 's'} of ${esc(q.name)}</h2>
      ${note ? `<div class="notice">${esc(note)}</div>` : ''}
      <div class="buy-lines"><div><span>${q.side === 'buy' ? 'Price you pay (ask)' : 'Price you get (bid)'}</span><b class="num">${price(q.price)} each</b></div>
        <div><span>${q.side === 'buy' ? 'Estimated cost' : 'Estimated proceeds'}</span><b class="num">${moneyFull(q.total)}</b></div>
        <div><span>${esc('Accumulated account now')}</span><b class="num">${moneyFull(q.balance)}</b></div>
        <div class="after"><span>Accumulated account after</span><b class="num ${q.canAfford ? '' : 'down'}">${moneyFull(q.balanceAfter)}</b></div>
        <div><span>You would own</span><b class="num">${num(q.ownedAfter, 0)} shares</b></div></div>
      <p class="muted" style="font-size:13px">This quote is good for <b id="q-left" class="num">${q.ttlSeconds}</b>s. The price may move up to ${num(q.maxSlippageBps / 100, 2)}% before you confirm; if it moves more, nothing happens and you get a new quote. You are filled at the price at that moment (${q.side === 'buy' ? 'at most' : 'at least'} ${moneyFull(q.worstTotal)} in total). Buying and then selling straight away costs the spread (${num(q.spreadBps / 100, 2)}%).</p>
      <div class="error-text" id="o-err" style="min-height:18px"></div>
      <div class="modal-actions"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn ${q.side === 'buy' ? 'btn-primary' : 'btn-no'}" id="o-go" ${q.canAfford ? '' : 'disabled'}>Confirm ${q.side}</button></div>`);
    const left = m.el.querySelector('#q-left'), go = m.el.querySelector('#o-go'), oerr = m.el.querySelector('#o-err');
    const tick = setInterval(() => {
      const s = Math.max(0, Math.round((q.expiresAt - Date.now()) / 1000));
      left.textContent = s;
      if (s <= 0) { clearInterval(tick); go.disabled = true; go.textContent = 'Get a new quote'; go.dataset.fresh = '1'; go.disabled = false; oerr.textContent = 'That quote expired.'; }
    }, 500);
    const origClose = m.close; m.close = () => { clearInterval(tick); origClose(); };
    go.addEventListener('click', async () => {
      if (go.dataset.fresh) { try { const f = await post('/api/stocks/quote', { symbol: sym, side: q.side, shares: q.shares }); m.close(); confirmOrder(f); } catch (ex) { oerr.textContent = ex.message; } return; }
      go.disabled = true;
      try {
        const d = await post('/api/stocks/trade', { quoteId: q.quoteId, requestId: orderId });
        setUser(d.user); m.close(); shares = ''; remember(VIEW, { shares: '' });
        toast(`${d.side === 'buy' ? 'Bought' : 'Sold'} ${num(d.shares, 0)} ${d.symbol} at ${price(d.price)}. Accumulated: ${money(d.balanceAfter)}.`, 'ok');
        await load(); drawAll();
      } catch (ex) {
        if (ex.status === 409 && ex.quote) { m.close(); confirmOrder(ex.quote, ex.message); return; }
        oerr.textContent = ex.message; go.disabled = false;
      }
    });
  }
  // `post` throws an Error; the server's fresh quote rides along on it
  drawAll();
  root.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.iv) { interval = b.dataset.iv; remember(VIEW, { interval }); load().then(() => { drawAll(); lastDraw = Date.now(); }); }
    else if (b.dataset.side) { side = b.dataset.side; remember(VIEW, { side }); root.querySelector('#ticket').innerHTML = ticket(); paintLines(); }
    else if (b.dataset.q) {
      const add = b.dataset.q === 'max' ? (side === 'buy' ? Math.floor(D.accumulated / D.ask) : D.position.shares) : (parseInt(shares, 10) || 0) + parseInt(b.dataset.q, 10);
      shares = String(Math.max(0, add)); remember(VIEW, { shares }); root.querySelector('#tk-sh').value = shares; paintLines();
    }
    else if (b.id === 'tk-go') review();
  });
  root.addEventListener('input', (e) => { if (e.target.id === 'tk-sh') { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 7); shares = e.target.value; remember(VIEW, { shares }); paintLines(); } });
  every(async () => { await load(); paintLive(); }, interval === 'live' ? 1000 : 2000);
  return { unmount() { dead = true; }, onEvent() {} };
}

// ------------------------------------------------------------------------------------------------ my portfolio
async function portfolioPage(root, every) {
  let P = await get('/api/stocks/portfolio');
  const draw = () => {
    root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">What you own here</span><h1 class="page-title">Exchange portfolio. ${SIM}</h1></div></div>
      <div class="stats"><div class="stat"><small>Total value</small><b class="num">${money(P.total)}</b></div><div class="stat"><small>Accumulated cash</small><b class="num">${money(P.cash)}</b></div>
        <div class="stat"><small>Shares worth</small><b class="num">${money(P.stockValue)}</b></div>
        <div class="stat"><small>Unrealized gain/loss</small><b class="num ${sign(P.unrealized)}">${money(P.unrealized, { plus: true })}</b></div>
        <div class="stat"><small>Realized gain/loss</small><b class="num ${sign(P.realized)}">${money(P.realized, { plus: true })}</b></div></div>
      <p class="muted" style="margin:10px 2px 0;max-width:70ch">Shares are valued at what you could sell them for right now (the bid). This is your accumulated account plus your shares; your weekly account and the weekly leaderboard are separate.</p>
      ${P.positions.length ? `<div class="card-box tbl-wrap" style="margin-top:20px"><table class="tbl"><thead><tr><th>Company</th><th class="r">Shares</th><th class="r hide-sm">Avg cost</th><th class="r">Price</th><th class="r">Value</th><th class="r">Gain / loss</th></tr></thead><tbody>
        ${P.positions.map((p) => `<tr data-sym="${p.symbol}" style="cursor:pointer"><td><b class="mono sym">${p.symbol}</b> ${esc(p.name)}</td><td class="r num">${num(p.shares, 0)}</td><td class="r num hide-sm">${price(p.avgCost)}</td><td class="r num">${price(p.price)}</td><td class="r num">${money(p.value)}</td>
          <td class="r num ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} <small>(${num(p.unrealizedPct, 1)}%)</small></td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: 'chartdown', tone: 'cream', tight: true, kicker: 'No shares', title: 'You do not own anything here yet.', text: 'Pick a company and buy a few shares with your accumulated account.', actions: '<a class="btn btn-primary" href="#/exchange">See the market</a>' })}
      <div class="section-head" style="margin-top:34px"><div><span class="kicker">Newest first</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">Recent transactions</h2></div></div>
      ${P.trades.length ? `<div class="card-box pad">${P.trades.map((t) => `<div class="list-row"><span class="tag ${t.side === 'buy' ? 'good' : 'bad'}">${t.side}</span><div class="grow"><b class="mono">${t.symbol}</b> ${num(t.shares, 0)} shares @ ${price(t.price)}</div>${t.realized != null ? `<span class="num ${sign(t.realized)}">${money(t.realized, { plus: true })} realized</span>` : ''}<b class="num">${money(t.total)}</b><span class="muted mono" style="font-size:12px">${ago(t.t)}</span></div>`).join('')}</div>` : '<p class="quiet">No transactions yet.</p>'}</div>`;
  };
  draw();
  root.addEventListener('click', (e) => { const r = e.target.closest('[data-sym]'); if (r) location.hash = `#/exchange/${r.dataset.sym}`; });
  every(async () => { P = await get('/api/stocks/portfolio'); draw(); }, 5000);
  return () => {};
}
