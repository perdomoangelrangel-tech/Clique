import { get, post } from '../api.js';
import { S, setUser, go } from '../state.js';
import { esc, money, moneyFull, vol, num, cents, pct, pctOf, ago, dateLong, thumb, avatar, circleMark, roll, ICON, debounce, parseAmount, floorCents, catName, sideName, slipLabel } from '../util.js';
import { toast, modal, confirmBox, copyText } from '../ui.js';
import { drawChart, RANGES, COLORS } from './chart.js';
import { isYesNo, slipNo, emptyState } from './components.js';
import { whoseIn } from './whosin.js';
import { editedTag, exitBanner, openEditPoll, openHistory, withdrawFlow } from './polledit.js';
import { isBookmarked, toggleBookmark } from '../bookmarks.js';
import { t, th, tp, CHIP_SIGN } from '../i18n.js';

export default {
  async mount(root, [id], query) {
    let M = (await get(`/api/markets/${id}`)).market;
    const st = {
      outcome: Math.max(0, Math.min(M.outcomes.length - 1, parseInt(query.get('o') || '0', 10) || 0)),
      side: query.get('s') === 'no' ? 'no' : 'yes',
      tab: 'buy', range: 'ALL', info: 'holders', amt: '', quote: null, quoteErr: '', busy: false,
    };
    if (M.binary) st.side = 'yes';
    let dead = false, qSeq = 0;

    root.innerHTML = `<div class="page"><div class="mp">
      <div class="mp-main" id="mp-main"></div>
      <aside><div class="side-sticky"><div class="trade paper" id="trade"></div><div class="related" id="related"></div></div></aside></div></div>`;
    const main = root.querySelector('#mp-main'), trade = root.querySelector('#trade');

    // ----------------------------------------------------------------- helpers
    const tokenPos = () => (M.myPositions || []).find((p) => !p.settled && p.outcome === st.outcome && p.side === st.side);
    const tokenPrice = () => { const o = M.outcomes[st.outcome]; return st.side === 'yes' ? o.yes : o.no; };
    const oName = (i) => sideName(M.outcomes[i].name, M.binary);       // "Sí"/"No" on a yes/no market, else the name a person wrote
    const tokenLabel = () => (M.binary ? oName(st.outcome) : `${M.outcomes[st.outcome].name} · ${st.side === 'yes' ? t('Sí') : t('No')}`);
    const sideLabel = () => (M.binary ? oName(st.outcome) : (st.side === 'yes' ? t('Sí') : t('No')));
    const NO_FUNDS = 'Not enough funds';                                // i18n: no (the server's words for it, until it sends a code)
    const isOpen = () => M.status === 'open';

    // ----------------------------------------------------------------- main column
    function drawMain() {
      const O = M.outcomes;
      const multi = !M.binary;
      const leader = [...O.keys()].sort((a, b) => O[b].yes - O[a].yes);
      const series = multi ? leader.slice(0, 5).map((i, k) => ({ idx: i, name: O[i].name, color: COLORS[k] })) : [{ idx: 0, name: oName(0), color: COLORS[0] }];
      const statusTag = M.status === 'resolved' ? `<span class="tag res">${th('Resuelto · ganó {opcion}', { opcion: oName(M.winner) })}</span>`
        : M.status === 'cancelled' ? `<span class="tag bad">${t('Cancelado · se devolvió todo')}</span>`
          : M.status === 'closed' ? `<span class="tag bad">${t('Apuestas cerradas · esperando el resultado')}</span>` : '';
      const first = O[0];
      main.innerHTML = `<div class="mp-top">
        <div class="crumbs">${M.circle ? `<a href="#/circle/${M.circle.id}">${circleMark(M.circle, 15)} ${esc(M.circle.name)}</a>` : `<span class="crumb-site">${ICON.globe} ${t('Apuesta pública')}</span>`} <span>//</span> <span>${esc(catName(M.category))}</span> ${statusTag} ${editedTag(M)}</div>${exitBanner(M)}
        <div class="mp-head" style="margin-top:12px">${thumb(M, true)}<div class="grow"><h1 class="mp-title">${esc(M.question)}</h1>
            <div class="sub-meta">${M.closesAt ? (M.status === 'open' ? t('Cierra el {fecha}', { fecha: dateLong(M.closesAt) }) : t('Cerró el {fecha}', { fecha: dateLong(M.closesAt) })) : t('Sin fecha de cierre')} · ${t('la propuso')} <a href="#/u/${esc(M.creator.username)}" style="color:var(--text);font-weight:600">${esc(M.creator.username)}</a></div></div>
          ${M.canEdit ? `<button class="btn btn-secondary btn-sm" id="edit-poll" title="${esc(t('Cambiar la fecha de cierre o las reglas'))}">${ICON.pencil} ${t('Editar')}</button>` : ''}
          <button class="icon-btn" id="share" title="${esc(t('Copiar enlace'))}">${ICON.link}</button>
          <button class="icon-btn ${isBookmarked(M.id) ? 'on' : ''}" id="bmk" title="${esc(t('Guardar boleto'))}" aria-label="${esc(t('Guardar boleto'))}">${isBookmarked(M.id) ? ICON.bookmarkOn : ICON.bookmark}</button></div>
        <div class="chart-panel">${multi ? `<div class="legend">${series.map((s) => `<span style="color:${s.color}"><i style="background:${s.color}"></i>${esc(s.name)} ${pct(O[s.idx].yes)}</span>`).join('')}</div>`
          : `<div><span class="bigchance num"><span id="bigval"></span><small>${isYesNo(M) ? t('probabilidad de sí') : esc(first.name)}</small></span></div>`}
        <div class="chart-wrap" id="chart"></div>
        <div class="metaline">
          <span class="num"><b style="color:var(--text)">${vol(M.volume)}</b> ${t('Vol.')}</span>
          <span>${tp(M.traders, '{n} apostador', '{n} apostadores')}</span>
          <div class="ranges">${Object.keys(RANGES).map((r) => `<button data-r="${r}" class="${st.range === r ? 'active' : ''}">${r === 'ALL' ? t('TODO') : r}</button>`).join('')}</div>
        </div></div>
        ${multi ? `<div class="otable">${leader.map((i) => `
          <div class="orow-big ${st.outcome === i ? 'sel' : ''}" data-o="${i}">
            <div class="nm">${esc(O[i].name)}</div><div class="big num">${pctOf(O[i])}</div>
            ${isOpen() ? `<button class="buybtn y" data-buy="${i}:yes">${t('Sí')} ${cents(O[i].yes)}</button><button class="buybtn n" data-buy="${i}:no">${t('No')} ${cents(O[i].no)}</button>` : `<span></span><span>${M.winner === i ? `<span class="tag good">${t('Ganó')}</span>` : ''}</span>`}
          </div>`).join('')}</div>` : ''}
        </div><div class="mp-bottom">
        <div class="rules-h"><span>${M.edited ? t('Reglas · versión {n}', { n: M.version }) : t('Reglas')}</span>${M.edited ? `<button class="linkish" id="hist2">${t('Ver qué cambió')}</button>` : ''}</div><p class="rules" style="margin:0">${M.description ? esc(M.description) : M.circle ? t('Sin letra chiquita. Quien la propuso, o el dueño del círculo, decide el resultado. Discútanlo en los comentarios.') : t('Sin letra chiquita. Quien la propuso decide el resultado. Discútanlo en los comentarios.')}</p>
        ${manageBox()}
        <div class="tabs" id="info-tabs">
          ${[['holders', t('Quién entró ({n})', { n: M.holders.length })], ['comments', t('Comentarios ({n})', { n: M.commentList.length })], ['activity', t('Movimientos')]].map(([k, l]) => `<button data-t="${k}" class="${st.info === k ? 'active' : ''}">${esc(l)}</button>`).join('')}
        </div>
        <div id="info"></div></div>`;
      const bv = main.querySelector('#bigval');
      if (bv) { if (st.lastPct !== undefined) bv.dataset.v = st.lastPct; roll(bv, pctOf(first)); st.lastPct = pctOf(first); }
      const chartHost = main.querySelector('#chart');
      drawChart(chartHost, M.history, series, st.range, M.status === 'resolved' || M.status === 'cancelled' ? M.resolvedAt : undefined);
      drawInfo();
    }

    function manageBox() {
      if (!M.canManage) return '';
      return `<div class="manage"><b>${t('Esta la manejas tú.')}</b>
        <p class="muted" style="margin:6px 0 14px">${M.circle ? t('La propusiste (o el círculo es tuyo), así que tú decides el resultado.') : t('La propusiste, así que tú decides el resultado. Todo el sitio confía en ti.')} ${t('A los ganadores se les paga en cuanto decidas.')}</p>
        <div class="row" style="flex-wrap:wrap"><button class="btn btn-secondary" id="edit-poll2">${ICON.pencil} ${t('Editar la fecha o las reglas')}</button><button class="btn btn-primary" id="resolve">${t('Decidir')}</button><button class="btn btn-danger" id="cancel">${t('Cancelar y devolver a todos')}</button></div></div>`;
    }

    function drawInfo() {
      const box = main.querySelector('#info');
      if (st.info === 'comments') {
        box.innerHTML = `<form id="cform" class="row" style="align-items:flex-start;margin-bottom:8px">${avatar(S.user.username, 36)}
          <div class="grow"><textarea class="input" id="ctext" maxlength="300" placeholder="${esc(t('Di algo. De preferencia, equivocado.'))}" style="min-height:44px;height:44px"></textarea></div>
          <button class="btn btn-primary" style="height:44px">${t('Publicar')}</button></form>
          ${M.commentList.length ? M.commentList.map((c) => `<div class="cmt">${avatar(c.user.username, 32)}<div><b>${esc(c.user.username)}</b><small>${ago(c.t)}</small><p>${esc(c.text)}</p></div></div>`).join('')
            : `<p class="quiet">${t('Sin comentarios. Que alguien eche bronca.')}</p>`}`;
        box.querySelector('#cform').addEventListener('submit', async (e) => {
          e.preventDefault();
          const text = box.querySelector('#ctext').value.trim(); if (!text) return;
          try { M = (await post(`/api/markets/${id}/comments`, { text })).market; drawMain(); } catch (ex) { toast(ex.message, 'err'); }
        });
      } else if (st.info === 'holders') {
        box.innerHTML = whoseIn(M);
      } else {
        box.innerHTML = M.activity.length ? M.activity.map((a) => `<div class="list-row">${avatar(a.user.username, 28)}
          <div class="grow">${a.kind === 'buy' ? th('<b>{nombre}</b> compró <b>{opcion}</b> a {precio}', { nombre: a.user.username, opcion: slipLabel(a.label), precio: cents(a.price) }) : th('<b>{nombre}</b> vendió <b>{opcion}</b> a {precio}', { nombre: a.user.username, opcion: slipLabel(a.label), precio: cents(a.price) })}
          <span class="muted"> · ${moneyFull(a.amount)}</span></div><span class="muted">${ago(a.t)}</span></div>`).join('')
          : `<p class="quiet">${t('Todavía no hay movimientos. La cinta está en blanco.')}</p>`;
      }
    }

    // ----------------------------------------------------------------- trade panel
    function drawTrade() {
      const O = M.outcomes;
      const o = O[st.outcome];
      const focused = document.activeElement?.id === 'amt';
      const caret = focused ? document.activeElement.selectionStart : null;
      const header = `<div class="slip-title"><span>${t('Boleto de apuesta')}</span><span>${slipNo(M)}</span></div>
        <div class="trade-head">${thumb(M)}<div><div class="q">${esc(M.question.length > 70 ? M.question.slice(0, 68) + '…' : M.question)}</div>
        <div class="s ${st.side === 'yes' && (M.binary ? st.outcome === 0 : true) ? 'up' : 'down'}">${esc(tokenLabel())}</div></div></div>`;

      if (M.status !== 'open') {
        const mine = (M.myPositions || []);
        trade.innerHTML = `${header}${emptyState({ tight: true, art: M.status === 'resolved' ? 'flag' : M.status === 'cancelled' ? 'paper' : 'scale', tone: M.status === 'resolved' ? 'lime' : 'cream',
          kicker: M.status === 'resolved' ? t('Resuelto') : M.status === 'cancelled' ? t('Cancelado') : t('Apuestas cerradas'),
          title: M.status === 'resolved' ? th('Ganó {opcion}.', { opcion: oName(M.winner) }) : M.status === 'cancelled' ? esc(t('Se canceló.')) : esc(t('Ya no se vale.')),
          text: esc(M.status === 'closed' ? t('Se acabó el tiempo. Falta que quien la maneja decida el resultado.') : M.status === 'cancelled' ? t('A todos les devolvieron sus fichas. Nadie aprendió nada.') : t('Cada acción ganadora pagó {uno}. Los perdedores pagaron la lección.', { uno: money(1, { noCents: true }) })) })}
          ${mine.length ? `<div class="posbox"><h4>${t('Tus posiciones')}</h4>${mine.map(posRow).join('')}</div>` : ''}`;
        return;
      }
      if (!M.isMember) {
        trade.innerHTML = `${header}${emptyState({ tight: true, art: 'chip', tone: 'verm', kicker: t('Solo miembros'), title: esc(t('No estás en el círculo.')), text: th('No puedes apostar en <b>{circulo}</b> desde la tribuna.', { circulo: M.circle.name }), actions: `<button class="btn btn-primary" id="join">${t('Sentarme')}</button>` })}`;
        trade.querySelector('#join').addEventListener('click', async () => {
          try { await post(`/api/circles/${M.circle.id}/join`, {}); M = (await get(`/api/markets/${id}`)).market; drawAll(); toast(t('Ya tienes lugar.'), 'ok'); } catch (ex) { toast(ex.message, 'err'); }
        });
        return;
      }

      const buy = st.tab === 'buy';
      const pos = tokenPos();
      const price = tokenPrice();
      const optBtns = M.binary
        ? O.map((x, i) => `<button class="opt ${i === 0 ? 'y' : 'n'} ${st.outcome === i ? 'sel' : ''}" data-opt="${i}:yes">${esc(oName(i))} ${cents(x.yes)}</button>`).join('')
        : `<button class="opt y ${st.side === 'yes' ? 'sel' : ''}" data-opt="${st.outcome}:yes">${t('Sí')} ${cents(o.yes)}</button><button class="opt n ${st.side === 'no' ? 'sel' : ''}" data-opt="${st.outcome}:no">${t('No')} ${cents(o.no)}</button>`;      // html: seguro (st.outcome es un índice numérico)
      const amt = parseAmount(st.amt);
      const q = st.quote;
      let warn = st.quoteErr, canGo = false;
      if (buy) {
        if (st.amt && !(amt >= S.minBet - 1e-9)) warn = warn || t('La apuesta mínima es {cantidad}', { cantidad: money(S.minBet) });
        else if (amt > S.user.balance + 1e-9) warn = NO_FUNDS;
        canGo = amt >= S.minBet - 1e-9 && amt <= S.user.balance + 1e-9 && !!q && !st.quoteErr;
      } else {
        const held = pos ? pos.shares : 0;
        if (amt > held * (1 + 1e-9) + 1e-9) warn = t('Solo tienes {n} acciones', { n: num(held, 4) });
        canGo = amt > 0 && !!pos && amt <= held * (1 + 1e-9) + 1e-9 && !!q && !st.quoteErr;
      }
      const fs = Math.max(22, 42 - Math.max(0, (st.amt || '').length - 6) * 2.6);
      const chance = (x) => `${pct(x.priceBefore)} → ${pct(x.priceAfter)}`;
      const summary = !q ? '' : buy
        ? `<div class="r"><span>${t('Pagas')}</span><i></i><b>${money(q.amount)}</b></div>
           <div class="r"><span>${t('Acciones que recibes')}</span><i></i><b>${num(q.shares)}</b></div>
           <div class="r"><span>${t('Precio promedio')}</span><i></i><b>${cents(q.avgPrice)}</b></div>
           <div class="r"><span>${th('Probabilidad de {opcion}', { opcion: sideLabel() })}</span><i></i><b>${chance(q)}</b></div>
           <div class="r win"><span>${t('Para ganar')}</span><i></i><b>${money(q.payout)}</b><em>+${num(q.returnPct, 1)}%</em></div>`
        : `<div class="r"><span>${t('Acciones que vendes')}</span><i></i><b>${num(q.shares)}</b></div>
           <div class="r"><span>${t('Precio promedio')}</span><i></i><b>${cents(q.avgPrice)}</b></div>
           <div class="r"><span>${th('Probabilidad de {opcion}', { opcion: sideLabel() })}</span><i></i><b>${chance(q)}</b></div>
           <div class="r win"><span>${t('Recibes')}</span><i></i><b>${money(q.amount)}</b></div>`;

      trade.innerHTML = `${header}
        <div class="trade-tabs"><button data-tab="buy" class="${buy ? 'active' : ''}">${t('Comprar')}</button><button data-tab="sell" class="${!buy ? 'active' : ''}">${t('Vender')}</button></div>
        <div class="opt-btns">${optBtns}</div>
        <div class="amt"><label for="amt">${buy ? t('Apuesta') : t('Acciones')}</label>
          <div class="amt-input ${st.amt ? 'has' : ''}" style="font-size:${fs}px">${buy ? `<span>${CHIP_SIGN}</span>` : ''}<input id="amt" inputmode="decimal" autocomplete="off" placeholder="${buy ? '0' : '0'}" value="${esc(st.amt)}"></div></div>
        <div class="quick">${buy
          ? ['1', '10', '100', '1000'].map((v) => `<button data-add="${v}">+${money(Number(v), { noCents: true })}</button>`).join('') + `<button data-max="1">${t('Máx.')}</button>`
          : ['25', '50', '75'].map((v) => `<button data-pct="${v}">${v}%</button>`).join('') + `<button data-max="1">${t('Máx.')}</button>`}</div>
        ${warn ? `<div class="error-text" style="margin:-4px 0 10px;text-align:right">${esc(warn === NO_FUNDS ? t('No te alcanzan las fichas.') : warn)} ${warn === NO_FUNDS ? `<a href="#" id="addf" style="text-decoration:underline;font-weight:600">${t('Agregar fichas')}</a>` : ''}</div>` : ''}
        <div class="summary">${summary}</div>
        <button class="btn btn-lg btn-block ${buy ? (st.side === 'yes' && (!M.binary || st.outcome === 0) ? 'btn-yes' : 'btn-no') : 'btn-primary'}" id="go" ${canGo && !st.busy ? '' : 'disabled'}>
          ${st.busy ? t('Un momento…') : buy ? th('Revisar apuesta a {opcion}', { opcion: sideLabel() }) : th('Revisar venta de {opcion}', { opcion: sideLabel() })}</button>
        <div class="balance-line">${t('Cuenta semanal')} <b title="${moneyFull(S.user.balance)}">${money(S.user.balance)}</b>${buy ? ` · ${t('mín. {cantidad}, sin tope', { cantidad: money(S.minBet) })}` : ''}</div>
        ${(M.myPositions || []).filter((p) => !p.settled).length ? `<div class="posbox"><h4>${t('Tus posiciones')}</h4>${(M.myPositions || []).filter((p) => !p.settled).map(posRow).join('')}</div>` : ''}`;

      const inp = trade.querySelector('#amt');
      if (focused) { inp.focus(); try { inp.setSelectionRange(caret, caret); } catch { /* ignore */ } }
    }

    function posRow(p) {
      const pnl = p.pnl || 0;
      return `<div class="p"><div><b class="${p.side === 'yes' ? 'up' : 'down'}">${esc(slipLabel(p.label))}</b><div class="muted">${t('{n} acciones · prom. {precio}', { n: num(p.shares), precio: cents(p.avgPrice) })}${p.underOldRules ? ` <span class="tag" title="${esc(t('Apostaste antes de que cambiaran las reglas o la fecha de cierre'))}">${t('apuesta con la versión {n}', { n: p.version })}</span>` : ''}</div></div>
        <div style="text-align:right"><b class="num">${money(p.value ?? 0)}</b><div class="${pnl >= 0 ? 'up' : 'down'} num">${p.refunded ? t('devuelto') : money(pnl, { plus: true })}</div></div></div>`;
    }

    // ----------------------------------------------------------------- quotes
    const fetchQuote = debounce(async () => {
      const amt = parseAmount(st.amt);
      const seq = ++qSeq;
      if (!(amt > 0)) { st.quote = null; st.quoteErr = ''; drawTrade(); return; }
      const body = { outcome: st.outcome, side: st.side, action: st.tab };
      if (st.tab === 'buy') body.amount = amt; else body.shares = amt;
      try {
        const d = await post(`/api/markets/${id}/quote`, body);
        if (seq !== qSeq || dead) return;
        st.quote = d.quote; st.quoteErr = '';
      } catch (ex) { if (seq !== qSeq || dead) return; st.quote = null; st.quoteErr = ex.message === NO_FUNDS ? '' : ex.message; }
      drawTrade();
    }, 140);
    const requote = () => { st.quote = null; fetchQuote(); };

    // ----------------------------------------------------------------- events
    trade.addEventListener('input', (e) => {
      if (e.target.id !== 'amt') return;
      let v = e.target.value.replace(/[^\d.,]/g, '').replace(/,/g, '');
      const parts = v.split('.'); if (parts.length > 2) v = parts[0] + '.' + parts.slice(1).join('');
      if (st.tab === 'buy' && v.includes('.')) { const [a, b] = v.split('.'); v = a + '.' + b.slice(0, 2); }
      st.amt = v; e.target.value = v;
      const fs = Math.max(22, 42 - Math.max(0, v.length - 6) * 2.6);
      e.target.parentElement.style.fontSize = fs + 'px'; e.target.parentElement.classList.toggle('has', !!v);
      requote();
    });
    trade.addEventListener('click', async (e) => {
      const btn = e.target.closest('button,a'); if (!btn) return;
      if (btn.id === 'addf') { e.preventDefault(); document.getElementById('btn-deposit').click(); return; }
      if (btn.dataset.tab) { st.tab = btn.dataset.tab; st.amt = ''; st.quote = null; st.quoteErr = ''; drawTrade(); return; }
      if (btn.dataset.opt) { const [o, s] = btn.dataset.opt.split(':'); st.outcome = +o; st.side = s; drawAll(); requote(); return; }
      if (btn.dataset.add) { st.amt = String(Math.round(((parseAmount(st.amt) || 0) + Number(btn.dataset.add)) * 100) / 100); drawTrade(); requote(); return; }
      if (btn.dataset.pct) { const p = tokenPos(); if (p) { st.amt = String(Math.floor(p.shares * Number(btn.dataset.pct) / 100 * 1e6) / 1e6); drawTrade(); requote(); } return; }
      if (btn.dataset.max) {
        if (st.tab === 'buy') st.amt = String(floorCents(S.user.balance)); else { const p = tokenPos(); st.amt = p ? String(p.shares) : ''; }
        drawTrade(); requote(); return;
      }
      if (btn.id === 'go') await review();
    });
    trade.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.id === 'amt') { e.preventDefault(); trade.querySelector('#go')?.click(); } });

    /** The last look before anything happens: what the trade costs or pays, how many shares, the average price and where
     *  the odds end up. The server prices it again at the moment of confirming and refuses if it got worse than this. */
    const requestId = () => (window.crypto && crypto.randomUUID ? crypto.randomUUID() : `r${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`);
    async function review() {
      const amt = parseAmount(st.amt); if (!(amt > 0) || st.busy) return;
      const buy = st.tab === 'buy';
      const body = { outcome: st.outcome, side: st.side, action: st.tab };
      if (buy) body.amount = amt; else body.shares = st.quote && Math.abs(st.quote.shares - amt) < 1e-6 ? st.quote.shares : amt;
      const rid = requestId();                                  // one id per confirmation: a double click or a retry cannot trade twice
      const sheet = modal(`<span class="lbl">${buy ? t('Revisa tu apuesta') : t('Revisa tu venta')}</span><h2>${esc(tokenLabel())}</h2>
        <div class="summary cf" id="cf"><div class="spinner"></div></div>
        <div class="error-text" id="cf-err" style="min-height:20px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Atrás')}</button><button type="button" class="btn btn-primary" id="cf-ok" disabled>${buy ? t('Confirmar apuesta') : t('Confirmar venta')}</button></div>`);
      const box = sheet.el.querySelector('#cf'), errEl = sheet.el.querySelector('#cf-err'), ok = sheet.el.querySelector('#cf-ok');
      let q = null, sending = false;
      const row = (label, value, cls = '') => `<div class="r ${cls}"><span>${esc(label)}</span><i></i><b>${value}</b></div>`;
      const paint = () => {
        if (!q) { box.innerHTML = ''; ok.disabled = true; return; }
        const others = M.outcomes.map((o, i) => `<span>${esc(oName(i))} <b>${Number(q.pctAfter[i])}%</b></span>`).join('');
        box.innerHTML = (buy
          ? row(t('Pagas'), money(q.amount)) + row(t('Acciones que recibes'), num(q.shares)) + row(t('Precio promedio'), cents(q.avgPrice))
          : row(t('Recibes'), money(q.amount), 'win') + row(t('Acciones que vendes'), num(q.shares)) + row(t('Precio promedio'), cents(q.avgPrice)))
          + row(t('Probabilidad de {opcion}', { opcion: sideLabel() }), `${pct(q.priceBefore)} → ${pct(q.priceAfter)}`)
          + (buy ? row(t('Si gana, cobras'), `${money(q.payout)} <em class="up">+${num(q.returnPct, 1)}%</em>`)
            : row(t('Ganancia o pérdida en estas acciones'), `<span class="${q.pnl >= 0 ? 'up' : 'down'}">${money(q.pnl, { plus: true })}</span>`) + row(t('Acciones que te quedan'), num(q.heldAfter)))
          + `<div class="cf-odds"><span class="lbl">${t('Probabilidades después de esta jugada')}</span><div>${others}</div></div>`;
        ok.disabled = sending;
      };
      const refresh = async () => {
        try { q = (await post(`/api/markets/${id}/quote`, body)).quote; errEl.textContent = ''; }
        catch (ex) { q = null; errEl.textContent = ex.message; }
        paint();
      };
      await refresh();
      ok.addEventListener('click', async () => {
        if (sending || !q) return;
        sending = true; st.busy = true; ok.disabled = true; ok.textContent = t('Un momento…'); errEl.textContent = '';
        const send = { ...body, requestId: rid };
        if (buy) send.minShares = q.shares * 0.995; else send.minAmount = Math.floor(q.amount * 0.995 * 100) / 100;      // up to half a percent worse is fine, more is not
        try {
          const d = await post(`/api/markets/${id}/trade`, send);
          setUser(d.user); M = d.market;
          toast(buy ? t('Boleto impreso: {n} acciones de {opcion} por {cantidad}', { n: num(d.trade.shares), opcion: sideLabel(), cantidad: money(d.trade.amount) }) : t('Vendiste por {cantidad}', { cantidad: money(d.trade.amount) }), 'ok');
          st.amt = ''; st.quote = null; st.quoteErr = '';
          if (st.tab === 'sell' && !tokenPos()) st.tab = 'buy';
          sheet.close(); st.busy = false; drawAll();
          return;
        } catch (ex) {
          if (ex.status === 409) { await refresh(); errEl.textContent = t('El precio se movió mientras mirabas. Estos son los números nuevos. Revísalos y confirma otra vez.'); }
          else errEl.textContent = ex.message;
          if (ex.status !== 409 && /closed|no longer open|funds|hold/i.test(ex.message)) { q = null; paint(); get(`/api/markets/${id}`).then((r) => { M = r.market; drawAll(); }).catch(() => {}); }      // (the server's words, until it sends codes)
        }
        sending = false; st.busy = false; ok.textContent = buy ? t('Confirmar apuesta') : t('Confirmar venta'); ok.disabled = !q;
      });
    }

    main.addEventListener('click', async (e) => {
      const btn = e.target.closest('button, .orow-big'); if (!btn) return;
      if (btn.id === 'share') { copyText(location.href.split('?')[0]); return; }
      if (btn.id === 'bmk') { const on = toggleBookmark(M.id); btn.classList.toggle('on', on); btn.innerHTML = on ? ICON.bookmarkOn : ICON.bookmark; return; }
      if (btn.dataset.r) { st.range = btn.dataset.r; drawMain(); return; }
      if (btn.dataset.t) { st.info = btn.dataset.t; main.querySelectorAll('#info-tabs button').forEach((b) => b.classList.toggle('active', b === btn)); drawInfo(); return; }
      if (btn.dataset.buy) { const [o, s] = btn.dataset.buy.split(':'); st.outcome = +o; st.side = s; st.tab = 'buy'; drawAll(); requote(); trade.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); return; }
      if (btn.classList.contains('orow-big')) { st.outcome = +btn.dataset.o; drawAll(); return; }
      if (btn.id === 'edit-poll' || btn.id === 'edit-poll2') return openEditPoll(M, (market) => { M = market; drawAll(); });
      if (btn.id === 'hist' || btn.id === 'hist2') return openHistory(M);
      if (btn.dataset.withdraw) return withdrawFlow(M, btn.dataset.withdraw, (market) => { M = market; drawAll(); });
      if (btn.id === 'resolve') return openResolve();
      if (btn.id === 'cancel') {
        if (await confirmBox({ title: t('¿Cancelarla?'), text: t('Se devuelve completa cada apuesta y el mercado se cierra. No hay vuelta atrás.'), confirm: t('Cancelar y devolver'), danger: true })) {
          try { const d = await post(`/api/markets/${id}/cancel`); setUser(d.user); M = d.market; drawAll(); toast(t('Cancelada. A todos les devolvieron sus fichas.'), 'ok'); } catch (ex) { toast(ex.message, 'err'); }
        }
      }
    });

    function openResolve() {
      const mm = modal(`<span class="lbl">${t('El veredicto')}</span><h2>${t('¿Quién ganó?')}</h2><p class="lede">${t('Elige al ganador. Cada acción ganadora cobra {uno} al instante. Los perdedores se quedan con la anécdota.', { uno: money(1, { noCents: true }) })}</p>
        <div class="stack" style="gap:8px">${M.outcomes.map((o, i) => `<button class="btn btn-outline btn-block" data-w="${i}" style="justify-content:space-between"><span>${esc(oName(i))}</span><span class="muted">${pct(o.yes)}</span></button>`).join('')}</div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Todavía no')}</button></div>`);
      mm.el.querySelectorAll('[data-w]').forEach((b) => b.addEventListener('click', async () => {
        const name = oName(+b.dataset.w);
        if (!(await confirmBox({ title: t('¿Decidir a favor de «{opcion}»?', { opcion: name }), text: t('Esto le paga a todos y no se puede deshacer.'), confirm: t('Decidir') }))) return;
        try { const d = await post(`/api/markets/${id}/resolve`, { outcome: +b.dataset.w }); setUser(d.user); M = d.market; mm.close(); drawAll(); toast(t('Resuelto: ganó {opcion}', { opcion: name }), 'ok'); } catch (ex) { toast(ex.message, 'err'); mm.close(); }
      }));
    }

    const drawAll = () => { drawMain(); drawTrade(); };
    drawAll();
    get(`/api/markets?circle=${M.circle ? M.circle.id : 'site'}&status=open&sort=trending`).then((d) => {
      const rel = d.markets.filter((m) => m.id !== M.id).slice(0, 5);
      const box = root.querySelector('#related'); if (!box || dead || !rel.length) return;
      box.innerHTML = `<h4>${M.circle ? th('También en la pizarra de {circulo}', { circulo: M.circle.name }) : t('Más apuestas públicas')}</h4>` + rel.map((m) => {
        const lead = m.outcomes.reduce((a, b) => (b.yes > a.yes ? b : a));
        return `<a class="rel-row" href="#/market/${m.id}">${thumb(m)}<span class="t">${esc(m.question)}</span><span class="p">${pct(lead.yes)}<small>${esc(sideName(lead.name, m.binary))}</small></span></a>`;
      }).join('');
    }).catch(() => {});
    if (query.get('o') !== null) trade.scrollIntoView?.({ block: 'nearest' });

    const resize = debounce(() => { if (!dead) drawMain(); }, 200);
    window.addEventListener('resize', resize);
    const clock = setInterval(() => { if (M.status === 'open' && M.closesAt && M.closesAt <= Date.now()) refetch(); }, 5000);

    async function refetch() {
      try { const d = await get(`/api/markets/${id}`); if (dead) return; M = d.market; drawAll(); if (st.amt) fetchQuote(); } catch { /* ignore */ }
    }
    return {
      onEvent(ev) { if (ev.type === 'market' && ev.id === id) refetch(); },
      unmount() { dead = true; clearInterval(clock); window.removeEventListener('resize', resize); },
    };
  },
};
