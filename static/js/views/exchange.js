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
import { t, th, tp, intlLocale, CHIP_SIGN } from '../i18n.js';

const rid = () => 'ord-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const sign = (x) => (x > 0 ? 'up' : x < 0 ? 'down' : '');
const arrow = (x) => (x > 0 ? '▲' : x < 0 ? '▼' : '■');
const price = (p) => CHIP_SIGN + Number(p).toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const spark = (pts, up) => {
  if (!pts || pts.length < 2) return '';
  const lo = Math.min(...pts), hi = Math.max(...pts), w = 96, h = 28, d = pts.map((p, i) => `${i ? 'L' : 'M'}${((i / (pts.length - 1)) * w).toFixed(1)} ${(h - 2 - ((p - lo) / ((hi - lo) || 1)) * (h - 4)).toFixed(1)}`).join('');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><path d="${d}" fill="none" stroke="${up ? 'var(--pos)' : 'var(--neg)'}" stroke-width="2" stroke-linejoin="round"/></svg>`;
};
const SIM = () => `<span class="tag sim" title="${esc(t('Todo en la Bolsa es inventado: las empresas, los precios y las noticias.'))}">${t('Simulado')}</span>`;
const sideWord = (s) => (s === 'buy' ? t('compra') : t('venta'));

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
      <div class="section-head"><div><span class="kicker">${t('Acciones de mentira, sentimientos de verdad')}</span><h1 class="page-title">${t('La bolsa.')} ${SIM()}</h1></div>
        <div class="ex-bal"><span class="lbl">${t('Cuenta acumulada')}</span><b class="num" data-bal>${moneyFull(D.accumulated)}</b></div></div>
      <p class="muted" style="max-width:72ch;margin:0 0 18px">${t('Diez empresas inventadas cuyos precios se mueven cada segundo, igual para todos. Compra y vende con tu cuenta <b>acumulada</b>. Sin préstamos ni ventas en corto. Nada de lo que hagas mueve los precios.')}
        ${D.catchup && D.catchup.replayedSeconds >= 180 ? `<span class="muted"> ${D.catchup.capped ? t('El mercado se repitió {n} minutos después de que el servidor estuvo apagado (el apagón fue más largo: solo se repite la última parte).', { n: Math.round(D.catchup.replayedSeconds / 60) }) : t('El mercado se repitió {n} minutos después de que el servidor estuvo apagado.', { n: Math.round(D.catchup.replayedSeconds / 60) })}</span>` : ''}</p>
      <div class="card-box tbl-wrap"><table class="tbl ex-tbl"><thead><tr><th>${t('Empresa')}</th><th class="hide-sm">${t('Sector')}</th><th class="hide-sm">${t('Última hora')}</th><th class="r">${t('Precio')}</th><th class="r">${t('Hoy')}</th><th class="r hide-md">${t('Tienes')}</th></tr></thead><tbody>
        ${D.stocks.map((s) => `<tr data-sym="${s.symbol}" tabindex="0" role="link" aria-label="${esc(s.name)}">
          <td><b class="mono sym">${s.symbol}</b> <span>${esc(s.name)}</span>${s.halted ? ` <span class="tag bad">${t('En pausa')}</span>` : ''}</td><td class="hide-sm muted">${esc(s.sector)}</td>
          <td class="hide-sm">${spark(s.spark, s.changePct >= 0)}</td><td class="r num"><b data-p="${s.symbol}">${price(s.price)}</b></td>
          <td class="r num ${sign(s.change)}" data-c="${s.symbol}">${arrow(s.change)} ${num(Math.abs(s.changePct), 2)}%</td>
          <td class="r num hide-md muted">${s.mine ? `${num(s.mine.shares, 0)} · ${money(s.mine.value)}` : '—'}</td></tr>`).join('')}</tbody></table></div>
      <div class="section-head" style="margin-top:34px"><div><span class="kicker">${t('Noticias simuladas')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Lo que movió el mercado')}</h2></div></div>
      <div class="card-box pad" id="ex-news">${newsHtml(D.news)}</div></div>`;
  };
  const newsHtml = (n) => (n.length ? n.map((x) => `<div class="list-row"><span class="tag sim">${t('Simulado')}</span><div class="grow">${esc(x.text)}</div><span class="muted mono" style="font-size:12px">${ago(x.t)}</span></div>`).join('') : `<p class="quiet">${t('Todo tranquilo por ahora.')}</p>`);
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
  const intervals = [['live', 'En vivo'], ['1m', '1 min'], ['5m', '5 min'], ['1h', '1 hora'], ['1d', '1 día']];      // i18n: claves
  const load = async () => {
    const iv = interval === 'live' ? '1m' : interval;
    D = await get(`/api/stocks/${sym}?interval=${iv}&limit=${interval === 'live' ? 15 : 240}`);
  };
  try { await load(); } catch (ex) { root.innerHTML = `<div class="page">${emptyState({ art: 'wheel', tone: 'verm', kicker: t('Esa empresa no existe'), title: esc(t('Esa clave de cotización no existe.')), text: esc(ex.message), actions: `<a class="btn btn-primary" href="#/exchange">${t('Volver a la Bolsa')}</a>` })}</div>`; return { unmount() {} }; }

  const todayText = () => t('{flecha} {cambio} ({pct}%) hoy', { flecha: arrow(D.change), cambio: price(Math.abs(D.change)), pct: num(Math.abs(D.changePct), 2) });
  const head = () => `<div class="section-head"><div><span class="kicker mono">${esc(D.symbol)} · ${esc(D.sector)}</span><h1 class="page-title">${esc(D.name)} ${SIM()}</h1></div>
    <div class="ex-price"><b class="num" id="px">${price(D.price)}</b><span class="num ${sign(D.change)}" id="chg">${todayText()}</span></div></div>
    ${D.halted ? `<div class="notice bad">${t('Las operaciones están en pausa un momento después de un movimiento muy brusco (un freno simulado). Los precios siguen moviéndose; las órdenes regresan pronto.')}</div>` : ''}`;
  const ticket = () => `<div class="card-box pad-lg otk"><div class="tk-top"><div class="seg2" role="tablist"><button data-side="buy" class="${side === 'buy' ? 'on y' : ''}">${t('Comprar')}</button><button data-side="sell" class="${side === 'sell' ? 'on n' : ''}">${t('Vender')}</button></div></div>
      <label class="lbl" for="tk-sh">${t('Acciones (números enteros)')}</label>
      <div class="bp-input" style="margin:6px 0"><input id="tk-sh" inputmode="numeric" autocomplete="off" value="${esc(shares)}" placeholder="0" aria-label="${esc(t('Número de acciones'))}"><button type="button" data-q="1">+1</button><button type="button" data-q="10">+10</button><button type="button" data-q="max">${side === 'buy' ? t('Máx.') : t('Todas')}</button></div>
      <div class="tk-lines" id="tk-lines"></div><div class="error-text" id="tk-err" style="min-height:18px"></div>
      <button class="btn ${side === 'buy' ? 'btn-primary' : 'btn-no'} btn-block" id="tk-go" ${D.halted ? 'disabled' : ''}>${side === 'buy' ? t('Revisar compra') : t('Revisar venta')}</button>
      <p class="muted" style="font-size:12.5px;margin:10px 0 0">${t('Se paga con tu cuenta acumulada. Ves el precio exacto y el total, del servidor, antes de confirmar. El precio puede moverse hasta 0.50% antes de que confirmes; si se mueve más, no se ejecuta nada.')}</p></div>`;
  const mine = () => { const p = D.position; return p.shares ? `<div class="card-box pad-lg"><span class="lbl">${t('Tienes')}</span><b class="num" style="font-size:28px;display:block">${tp(p.shares, '{n} acción', '{n} acciones')}</b>
      <div class="kv"><span>${t('Costo promedio')}</span><b class="num">${price(p.avgCost)}</b><span>${t('Valen si vendes ahora')}</span><b class="num">${money(p.value)}</b><span>${t('Sin realizar')}</span><b class="num ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} (${num(p.unrealizedPct, 2)}%)</b><span>${t('Realizado hasta ahora')}</span><b class="num ${sign(p.realized)}">${money(p.realized, { plus: true })}</b></div></div>`
      : `<div class="card-box pad-lg"><span class="lbl">${t('Tienes')}</span><p class="muted" style="margin:6px 0 0">${t('Nada todavía.')}${p.realized ? ` ${t('Realizado hasta ahora:')} <b class="num ${sign(p.realized)}">${money(p.realized, { plus: true })}</b>` : ''}</p></div>`; };

  function drawAll() {
    root.innerHTML = `<div class="page">${head()}
      <div class="ex-grid"><div class="stack">
        <div class="card-box pad-lg"><div class="ex-ctl"><div class="tabs" id="ivs" style="margin:0;border:0">${intervals.map(([k, l]) => `<button data-iv="${k}" class="${interval === k ? 'active' : ''}">${esc(t(l))}</button>`).join('')}</div>
          <span class="muted mono" style="font-size:11.5px">${interval === 'live' ? t('últimos 10 minutos · cada segundo') : t('velas')}</span></div><div id="chart"></div>
          <div class="ex-stats"><div><span class="lbl">${t('Máximo de 24 h')}</span><b class="num">${price(D.high24)}</b></div><div><span class="lbl">${t('Mínimo de 24 h')}</span><b class="num">${price(D.low24)}</b></div>
            <div><span class="lbl">${t('Puedes comprar a')}</span><b class="num" id="ask">${price(D.ask)}</b></div><div><span class="lbl">${t('Puedes vender a')}</span><b class="num" id="bid">${price(D.bid)}</b></div></div></div>
        <div class="card-box pad-lg"><span class="lbl">${t('Acerca de')}</span><p style="margin:6px 0 0">${esc(D.about)}</p></div>
        <div class="card-box pad-lg"><span class="lbl">${t('Noticias simuladas')}</span><div id="news">${D.news.length ? D.news.map((n) => `<div class="list-row"><span class="tag sim">${t('Simulado')}</span><div class="grow">${esc(n.text)}</div><span class="muted mono" style="font-size:12px">${ago(n.t)}</span></div>`).join('') : `<p class="quiet">${t('No le ha pasado nada a esta empresa últimamente.')}</p>`}</div></div></div>
        <div class="stack ex-side"><div id="ticket">${ticket()}</div><div id="mine">${mine()}</div>
          <div class="card-box pad-lg"><span class="lbl">${t('Tus movimientos recientes aquí')}</span><div id="trades">${tradesHtml()}</div></div></div></div></div>`;
    paintChart(); paintLines();
  }
  const tradesHtml = () => (D.trades.length ? D.trades.map((tr) => `<div class="list-row"><span class="tag ${tr.side === 'buy' ? 'good' : 'bad'}">${esc(sideWord(tr.side))}</span><div class="grow">${num(tr.shares, 0)} @ ${price(tr.price)}</div><b class="num">${money(tr.total)}</b><span class="muted mono" style="font-size:11.5px">${ago(tr.t)}</span></div>`).join('') : `<p class="quiet">${t('Ninguno todavía.')}</p>`);
  const paintChart = () => { const el = root.querySelector('#chart'); if (el) drawStockChart(el, { type: interval === 'live' ? 'line' : 'candles', ticks: interval === 'live' ? D.ticks.filter(([t]) => t >= D.t - 600_000) : [], candles: interval === 'live' ? [] : D.candles, height: 300 }); };
  const paintLines = () => {
    const el = root.querySelector('#tk-lines'); if (!el) return;
    const n = parseInt(shares, 10) || 0, px = side === 'buy' ? D.ask : D.bid, tot = n * px;
    const bal = D.accumulated, after = side === 'buy' ? bal - tot : bal + tot;
    el.innerHTML = `<div><span>${side === 'buy' ? t('Precio que pagas (venta)') : t('Precio que recibes (compra)')}</span><b class="num">${price(px)}</b></div>
      <div><span>${side === 'buy' ? t('Costo estimado') : t('Lo que recibes, estimado')}</span><b class="num">${money(tot)}</b></div>
      <div><span>${t('Cuenta acumulada después')}</span><b class="num ${side === 'buy' && after < 0 ? 'down' : ''}">${money(after)}</b></div>`;
    if (side === 'buy' && n && tot > bal) root.querySelector('#tk-err').textContent = t('Te faltan {cantidad} en tu cuenta acumulada.', { cantidad: money(tot - bal) });
    else if (side === 'sell' && n > D.position.shares) root.querySelector('#tk-err').textContent = tp(D.position.shares, 'Solo tienes {n} acción.', 'Solo tienes {n} acciones.');
    else root.querySelector('#tk-err').textContent = '';
  };
  const paintLive = () => {
    const p = root.querySelector('#px'); if (!p) return;
    roll(p, price(D.price)); const c = root.querySelector('#chg'); c.className = `num ${sign(D.change)}`; c.textContent = todayText();
    root.querySelector('#ask').textContent = price(D.ask); root.querySelector('#bid').textContent = price(D.bid);
    paintLines();
    if (Date.now() - lastDraw > (interval === 'live' ? 1000 : 5000)) { paintChart(); lastDraw = Date.now(); }
    root.querySelector('#mine').innerHTML = mine(); root.querySelector('#trades').innerHTML = tradesHtml();
  };

  // ---- the order: ask the server for a quote, then confirm that quote
  async function review() {
    const n = parseInt(shares, 10);
    const err = root.querySelector('#tk-err');
    if (!(n >= 1)) { err.textContent = t('Escribe cuántas acciones.'); return; }
    err.textContent = '';
    let q;
    try { q = await post('/api/stocks/quote', { symbol: sym, side, shares: n }); } catch (ex) { err.textContent = ex.message; return; }
    confirmOrder(q);
  }
  function confirmOrder(q, note = '') {
    const orderId = rid();
    const m = modal(`<span class="lbl">${t('Revisa tu orden')} · ${SIM()}</span><h2>${q.side === 'buy' ? tp(q.shares, 'Comprar {n} acción de {empresa}', 'Comprar {n} acciones de {empresa}', { empresa: esc(q.name) }) : tp(q.shares, 'Vender {n} acción de {empresa}', 'Vender {n} acciones de {empresa}', { empresa: esc(q.name) })}</h2>
      ${note ? `<div class="notice">${esc(note)}</div>` : ''}
      <div class="buy-lines"><div><span>${q.side === 'buy' ? t('Precio que pagas (venta)') : t('Precio que recibes (compra)')}</span><b class="num">${t('{precio} cada una', { precio: price(q.price) })}</b></div>
        <div><span>${q.side === 'buy' ? t('Costo estimado') : t('Lo que recibes, estimado')}</span><b class="num">${moneyFull(q.total)}</b></div>
        <div><span>${t('Cuenta acumulada ahora')}</span><b class="num">${moneyFull(q.balance)}</b></div>
        <div class="after"><span>${t('Cuenta acumulada después')}</span><b class="num ${q.canAfford ? '' : 'down'}">${moneyFull(q.balanceAfter)}</b></div>
        <div><span>${t('Tendrías')}</span><b class="num">${tp(q.ownedAfter, '{n} acción', '{n} acciones')}</b></div></div>
      <p class="muted" style="font-size:13px">${th('Esta cotización sirve por <b id="q-left" class="num">{seg}</b> s. El precio puede moverse hasta {desliz}% antes de que confirmes; si se mueve más, no pasa nada y te damos otra cotización. Se ejecuta al precio de ese momento ({limite} {peor} en total). Comprar y vender de inmediato cuesta el diferencial ({dif}%).', { seg: Number(q.ttlSeconds), desliz: num(q.maxSlippageBps / 100, 2), limite: q.side === 'buy' ? t('cuando mucho') : t('por lo menos'), peor: moneyFull(q.worstTotal), dif: num(q.spreadBps / 100, 2) })}</p>
      <div class="error-text" id="o-err" style="min-height:18px"></div>
      <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn ${q.side === 'buy' ? 'btn-primary' : 'btn-no'}" id="o-go" ${q.canAfford ? '' : 'disabled'}>${q.side === 'buy' ? t('Confirmar compra') : t('Confirmar venta')}</button></div>`);
    const left = m.el.querySelector('#q-left'), go = m.el.querySelector('#o-go'), oerr = m.el.querySelector('#o-err');
    const tick = setInterval(() => {
      const s = Math.max(0, Math.round((q.expiresAt - Date.now()) / 1000));
      left.textContent = s;
      if (s <= 0) { clearInterval(tick); go.disabled = true; go.textContent = t('Pedir otra cotización'); go.dataset.fresh = '1'; go.disabled = false; oerr.textContent = t('Esa cotización ya venció.'); }
    }, 500);
    const origClose = m.close; m.close = () => { clearInterval(tick); origClose(); };
    go.addEventListener('click', async () => {
      if (go.dataset.fresh) { try { const f = await post('/api/stocks/quote', { symbol: sym, side: q.side, shares: q.shares }); m.close(); confirmOrder(f); } catch (ex) { oerr.textContent = ex.message; } return; }
      go.disabled = true;
      try {
        const d = await post('/api/stocks/trade', { quoteId: q.quoteId, requestId: orderId });
        setUser(d.user); m.close(); shares = ''; remember(VIEW, { shares: '' });
        const done = { n: num(d.shares, 0), clave: d.symbol, precio: price(d.price), saldo: money(d.balanceAfter) };
        toast(d.side === 'buy' ? t('Compraste {n} {clave} a {precio}. Acumulada: {saldo}.', done) : t('Vendiste {n} {clave} a {precio}. Acumulada: {saldo}.', done), 'ok');
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
    root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">${t('Lo que tienes aquí')}</span><h1 class="page-title">${t('Portafolio de la Bolsa.')} ${SIM()}</h1></div></div>
      <div class="stats"><div class="stat"><small>${t('Valor total')}</small><b class="num">${money(P.total)}</b></div><div class="stat"><small>${t('Fichas libres acumuladas')}</small><b class="num">${money(P.cash)}</b></div>
        <div class="stat"><small>${t('Valen tus acciones')}</small><b class="num">${money(P.stockValue)}</b></div>
        <div class="stat"><small>${t('Ganancia o pérdida sin realizar')}</small><b class="num ${sign(P.unrealized)}">${money(P.unrealized, { plus: true })}</b></div>
        <div class="stat"><small>${t('Ganancia o pérdida realizada')}</small><b class="num ${sign(P.realized)}">${money(P.realized, { plus: true })}</b></div></div>
      <p class="muted" style="margin:10px 2px 0;max-width:70ch">${t('Las acciones valen lo que podrías obtener al venderlas ahora mismo (la compra). Esto es tu cuenta acumulada más tus acciones; tu cuenta semanal y el ranking semanal van aparte.')}</p>
      ${P.positions.length ? `<div class="card-box tbl-wrap" style="margin-top:20px"><table class="tbl"><thead><tr><th>${t('Empresa')}</th><th class="r">${t('Acciones')}</th><th class="r hide-sm">${t('Costo prom.')}</th><th class="r">${t('Precio')}</th><th class="r">${t('Valor')}</th><th class="r">${t('Ganancia o pérdida')}</th></tr></thead><tbody>
        ${P.positions.map((p) => `<tr data-sym="${p.symbol}" style="cursor:pointer"><td><b class="mono sym">${p.symbol}</b> ${esc(p.name)}</td><td class="r num">${num(p.shares, 0)}</td><td class="r num hide-sm">${price(p.avgCost)}</td><td class="r num">${price(p.price)}</td><td class="r num">${money(p.value)}</td>
          <td class="r num ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} <small>(${num(p.unrealizedPct, 1)}%)</small></td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: 'chartdown', tone: 'cream', tight: true, kicker: t('Sin acciones'), title: esc(t('Todavía no tienes nada aquí.')), text: esc(t('Elige una empresa y compra unas acciones con tu cuenta acumulada.')), actions: `<a class="btn btn-primary" href="#/exchange">${t('Ver el mercado')}</a>` })}
      <div class="section-head" style="margin-top:34px"><div><span class="kicker">${t('Lo más nuevo primero')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Movimientos recientes')}</h2></div></div>
      ${P.trades.length ? `<div class="card-box pad">${P.trades.map((tr) => `<div class="list-row"><span class="tag ${tr.side === 'buy' ? 'good' : 'bad'}">${esc(sideWord(tr.side))}</span><div class="grow"><b class="mono">${esc(tr.symbol)}</b> ${tp(tr.shares, '{n} acción', '{n} acciones')} @ ${price(tr.price)}</div>${tr.realized != null ? `<span class="num ${sign(tr.realized)}">${t('{cantidad} realizado', { cantidad: money(tr.realized, { plus: true }) })}</span>` : ''}<b class="num">${money(tr.total)}</b><span class="muted mono" style="font-size:12px">${ago(tr.t)}</span></div>`).join('')}</div>` : `<p class="quiet">${t('Todavía no hay movimientos.')}</p>`}</div>`;
  };
  draw();
  root.addEventListener('click', (e) => { const r = e.target.closest('[data-sym]'); if (r) location.hash = `#/exchange/${r.dataset.sym}`; });
  every(async () => { P = await get('/api/stocks/portfolio'); draw(); }, 5000);
  return () => {};
}
