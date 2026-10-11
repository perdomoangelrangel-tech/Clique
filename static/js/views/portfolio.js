/* The Portfolio: where all your money is. Two pictures (the weekly account and the accumulated account), then the shares you
   own and the polls you have bet in. Everything comes from one server answer (/api/portfolio/overview), so it always agrees
   with the header, the Weekly page and the Exchange. */
import { get } from '../api.js';
import { esc, money, moneyFull, num, dateShort, slipLabel } from '../util.js';
import { emptyState } from './components.js';
import { recall, remember } from '../viewstate.js';
import { t, th, tp, intlLocale, CHIP_SIGN } from '../i18n.js';

// Each kind of money gets a colour and a pattern, so the bar can be read without colour too.
const LOOK = {
  weekly: { cash: ['var(--lime)', ''], polls: ['#EFE6D2', 'p-stripes'], casino: ['var(--verm)', 'p-dots'], poker: ['#2F6B47', 'p-checker'] },
  accumulated: { cash: ['var(--lime)', ''], stocks: ['#6EC6FF', 'p-dots'] },
};
const pct = (v, total) => (total > 0 ? (v / total) * 100 : 0);
const fmtPct = (p) => (p >= 10 ? p.toFixed(0) : p.toFixed(1)) + '%';
const sign = (x) => (x > 0.004 ? 'up' : x < -0.004 ? 'down' : '');
const price = (p) => CHIP_SIGN + Number(p).toLocaleString(intlLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
// The parts of each account (the server's labels are in English): what to call them and one line about each.
const PART = {                                                                                                   // i18n: claves ↓
  cash: ['Fichas libres', 'Listas para apostar o gastar.'],
  polls: ['En mercados', 'Tus apuestas abiertas, a lo que valen ahora.'],
  casino: ['En el casino', 'Rondas del casino que no han terminado.'],
  poker: ['En la mesa de póker', 'Las fichas que tienes sentadas en una mesa.'],
  stocks: ['En acciones', 'Tus acciones de la Bolsa, a su precio de ahora.'],
};                                                                                                               // i18n: fin
const partLabel = (p) => (PART[p.key] ? t(PART[p.key][0]) : p.label);
const partNote = (p) => (PART[p.key] ? t(PART[p.key][1]) : p.note);

export default {
  async mount(root) {
    let D = await get('/api/portfolio/overview'), dead = false;
    let tab = ['open', 'closed'].includes(recall('portfolio').tab) ? recall('portfolio').tab : 'open';

    const summary = (kind, A) => {
      const cash = A.parts.find((p) => p.key === 'cash').amount;
      if (A.total <= 0) return esc(t('Ahorita no hay nada en esta cuenta.'));
      if (kind === 'weekly') {
        const working = A.parts.filter((p) => p.key !== 'cash' && p.amount > 0);
        return working.length
          ? th('<b>{libres}</b> son fichas libres para usar. El otro <b>{resto}</b> está trabajando: {partes}.', { libres: fmtPct(pct(cash, A.total)), resto: fmtPct(100 - pct(cash, A.total)), partes: working.map((p) => `${money(p.amount)} ${partLabel(p).toLowerCase()}`).join(', ') })
          : esc(t('Todo son fichas libres. No hay nada en mercados, rondas del casino ni mesas de póker.'));
      }
      const shares = A.parts.find((p) => p.key === 'stocks').amount;
      return shares > 0 ? th('<b>{libres}</b> son fichas libres para la Tienda y la Bolsa. <b>{acciones}</b> está en acciones.', { libres: fmtPct(pct(cash, A.total)), acciones: fmtPct(pct(shares, A.total)) }) : esc(t('Todo son fichas libres. No tienes acciones.'));
    };

    const accountCard = (kind, title, kicker, A, links) => {
      const looks = LOOK[kind];
      const visible = A.parts.filter((p) => p.amount > 0);
      const rows = A.parts.filter((p) => p.amount > 0 || p.key === 'cash');
      return `<section class="pfo-card card-box" aria-label="${esc(title)}">
        <div class="pfo-head"><div><span class="kicker">${kicker}</span><h2>${esc(title)}</h2></div><b class="num pfo-total" title="${moneyFull(A.total)}">${money(A.total)}</b></div>
        <p class="spread-line">${summary(kind, A)}</p>
        ${visible.length ? `<div class="spread-bar" role="img" aria-label="${esc(visible.map((p) => `${partLabel(p)} ${fmtPct(pct(p.amount, A.total))}`).join(', '))}">
          ${visible.map((p) => `<i class="${looks[p.key][1]}" style="flex:${Math.max(p.amount, A.total * 0.012)};--fill:${looks[p.key][0]}" title="${esc(partLabel(p))}: ${moneyFull(p.amount)}"></i>`).join('')}</div>` : '<div class="spread-bar pfo-none" aria-hidden="true"></div>'}
        <div class="pfo-legend">${rows.map((p) => `<div class="pfo-row"><i class="sw ${looks[p.key][1]}" style="--fill:${looks[p.key][0]}"></i>
          <div class="pfo-what"><b>${esc(partLabel(p))}</b><small>${esc(partNote(p))}</small></div>
          <b class="num" title="${moneyFull(p.amount)}">${money(p.amount)}</b><span class="num pfo-share">${fmtPct(pct(p.amount, A.total))}</span></div>`).join('')}</div>
        <p class="pfo-links">${links}</p></section>`;
    };

    const stocksBlock = () => {
      const S_ = D.stocks;
      if (!S_) return `<div class="card-box pad"><p class="muted" style="margin:0">${t('La Bolsa está cerrada en este momento, así que no podemos mostrar tus acciones. Están a salvo.')}</p></div>`;
      if (!S_.positions.length) return emptyState({ art: 'chartdown', tone: 'cream', tight: true, kicker: t('Sin acciones'), title: esc(t('No tienes acciones.')), text: esc(t('Compra unas acciones de una empresa de mentira con tu cuenta acumulada y aparecerán aquí.')), actions: `<a class="btn btn-primary" href="#/exchange">${t('Ver la Bolsa')}</a>` });
      return `<div class="stats pfo-stats"><div class="stat"><small>${t('Valen tus acciones')}</small><b class="num">${money(S_.value)}</b></div><div class="stat"><small>${t('Lo que pagaste')}</small><b class="num">${money(S_.invested)}</b></div>
          <div class="stat"><small>${t('Ganancia o pérdida sin realizar')}</small><b class="num ${sign(S_.unrealized)}">${money(S_.unrealized, { plus: true })}</b></div><div class="stat"><small>${t('Ganancia o pérdida realizada')}</small><b class="num ${sign(S_.realized)}">${money(S_.realized, { plus: true })}</b></div></div>
        <div class="card-box tbl-wrap" style="margin-top:14px"><table class="tbl pfo-tbl sh"><thead><tr><th>${t('Empresa')}</th><th class="r">${t('Acciones')}</th><th class="r hide-sm">${t('Costo prom.')}</th><th class="r hide-sm">${t('Precio')}</th><th class="r">${t('Valen')}</th><th class="r">${t('Ganancia o pérdida')}</th></tr></thead><tbody>
          ${S_.positions.map((p) => `<tr data-sym="${esc(p.symbol)}" tabindex="0" role="link" aria-label="${esc(p.name)}" style="cursor:pointer"><td class="c"><b class="mono sym">${esc(p.symbol)}</b> ${esc(p.name)}</td><td class="r num n">${num(p.shares, 0)}</td><td class="r num hide-sm">${price(p.avgCost)}</td><td class="r num hide-sm">${price(p.price)}</td><td class="r num w">${money(p.value)}</td>
            <td class="r num g ${sign(p.unrealized)}">${money(p.unrealized, { plus: true })} <small>(${num(p.unrealizedPct, 1)}%)</small></td></tr>`).join('')}</tbody></table></div>`;
    };

    const pollsBlock = () => {
      const P = D.polls, closed = tab === 'closed', rows = closed ? P.closed : P.open;
      const tabs = `<div class="tabs" id="ptabs" style="margin-top:0">${[['open', t('Abiertos ({n})', { n: P.open.length })], ['closed', t('Resueltos ({n})', { n: P.closed.length })]].map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${esc(l)}</button>`).join('')}</div>`;
      if (!rows.length) {
        return tabs + emptyState({ art: closed ? 'paper' : 'slip', tone: 'cream', tight: true, kicker: closed ? t('Nada resuelto') : t('Sin apuestas abiertas'),
          title: esc(closed ? t('Todavía no hay mercados resueltos.') : t('No has apostado en ningún mercado abierto.')),
          text: esc(closed ? t('Los mercados donde apostaste aparecen aquí cuando tienen resultado.') : t('Elige un mercado y ponle algo. Tus apuestas aparecen aquí, con lo que valen ahora mismo.')),
          actions: closed ? '' : `<a class="btn btn-primary" href="#/">${t('Ver los mercados')}</a>` });
      }
      const sum = closed ? '' : `<p class="muted" style="margin:0 0 12px">${th('Tienes <b class="num">{puesto}</b> en mercados abiertos, que valen <b class="num">{valor}</b> si los vendieras ahora mismo ({resultado}).', { puesto: money(P.openInvested), valor: money(P.openValue), resultado: money(P.openPnl, { plus: true }) })}</p>`;
      return tabs + sum + `<div class="card-box tbl-wrap"><table class="tbl pfo-tbl pl"><thead><tr><th>${t('Mercado')}</th><th>${t('Tu apuesta')}</th><th class="r hide-sm">${t('Puso')}</th><th class="r">${closed ? t('Cobró') : t('Vale hoy')}</th><th class="r">${t('Ganancia o pérdida')}</th>${closed ? '' : `<th class="r hide-sm">${t('Cierra')}</th>`}</tr></thead><tbody>
        ${rows.map((r) => `<tr data-m="${esc(r.market)}" tabindex="0" role="link" aria-label="${esc(r.question)}" style="cursor:pointer"><td class="q"><b>${esc(r.question)}</b></td>
          <td class="t"><span class="tag ${r.side === 'yes' ? 'good' : 'bad'}">${esc(slipLabel(r.label))}</span></td><td class="r num hide-sm">${money(r.invested)}</td><td class="r num w">${money(r.value ?? 0)}</td>
          <td class="r num g ${r.refunded ? '' : sign(r.pnl || 0)}">${r.refunded ? t('devuelto') : money(r.pnl || 0, { plus: true })}</td>
          ${closed ? '' : `<td class="r hide-sm muted">${r.status === 'closed' ? t('esperando resultado') : r.closes ? dateShort(r.closes) : t('sin fecha de cierre')}</td>`}</tr>`).join('')}</tbody></table></div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">${t('Dónde están tus fichas')}</span><h1 class="page-title">${t('Tu portafolio.')}</h1></div></div>
        <div class="stats pfo-tiles"><div class="stat"><small>${t('Todo lo que tienes')}</small><b class="num" title="${moneyFull(D.total)}">${money(D.total)}</b></div>
          <div class="stat"><small>${t('Cuenta semanal')}</small><b class="num" title="${moneyFull(D.weekly.total)}">${money(D.weekly.total)}</b></div>
          <div class="stat"><small>${t('Cuenta acumulada')}</small><b class="num" title="${moneyFull(D.accumulated.total)}">${money(D.accumulated.total)}</b></div></div>
        <div class="pfo-grid">
          ${accountCard('weekly', t('Tus fichas semanales'), t('Las fichas de esta semana'), D.weekly, `${t('Vuelven a tu cantidad semanal cada lunes.')} <a href="#/weekly">${t('La Semana')}</a> · <a href="#/games">${t('Casino')}</a> · <a href="#/">${t('Mercados')}</a>`)}
          ${accountCard('accumulated', t('Tus fichas acumuladas'), t('Lo que conservas'), D.accumulated, `${t('Aquí llegan los premios semanales.')} <a href="#/store">${t('Tienda')}</a> · <a href="#/exchange">${t('Bolsa')}</a> · <a href="#/statement">${t('Estado de cuenta')}</a>`)}
        </div>
        <div class="section-head" style="margin-top:44px"><div><span class="kicker">${t('En la Bolsa')}</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">${t('Tus acciones')}</h2></div></div>
        ${stocksBlock()}
        <div class="section-head" style="margin-top:44px"><div><span class="kicker">${t('Pagado con la cuenta semanal')}</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">${t('Mercados donde apostaste')}</h2></div></div>
        ${pollsBlock()}
        <p class="muted" style="margin:26px 2px 0;font-size:13px;max-width:72ch">${t('Las apuestas abiertas y las acciones valen lo que podrías obtener por ellas ahora mismo, no lo que pagaste. Las fichas de práctica nunca cuentan aquí.')}</p></div>`;
    };
    draw();

    const reload = async () => { try { const next = await get('/api/portfolio/overview'); if (dead) return; D = next; draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', (e) => {
      const tb = e.target.closest('#ptabs button');
      if (tb) { tab = tb.dataset.t; remember('portfolio', { tab }); draw(); return; }
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
