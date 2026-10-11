import { get, post } from '../api.js';
import { S, setUser, go } from '../state.js';
import { esc, money, moneyFull, vol, num, cents, pct, pctOf, ago, dateLong, thumb, avatar, circleMark, roll, ICON, debounce, parseAmount, floorCents } from '../util.js';
import { toast, modal, confirmBox, copyText } from '../ui.js';
import { drawChart, RANGES, COLORS } from './chart.js';
import { isYesNo, slipNo, emptyState } from './components.js';
import { whoseIn } from './whosin.js';
import { editedTag, exitBanner, openEditPoll, openHistory, withdrawFlow } from './polledit.js';
import { isBookmarked, toggleBookmark } from '../bookmarks.js';

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
    const tokenLabel = () => (M.binary ? M.outcomes[st.outcome].name : `${M.outcomes[st.outcome].name} · ${st.side === 'yes' ? 'Yes' : 'No'}`);
    const sideLabel = () => (M.binary ? M.outcomes[st.outcome].name : (st.side === 'yes' ? 'Yes' : 'No'));
    const isOpen = () => M.status === 'open';

    // ----------------------------------------------------------------- main column
    function drawMain() {
      const O = M.outcomes;
      const multi = !M.binary;
      const leader = [...O.keys()].sort((a, b) => O[b].yes - O[a].yes);
      const series = multi ? leader.slice(0, 5).map((i, k) => ({ idx: i, name: O[i].name, color: COLORS[k] })) : [{ idx: 0, name: O[0].name, color: COLORS[0] }];
      const statusTag = M.status === 'resolved' ? `<span class="tag res">Settled · ${esc(O[M.winner].name)} won</span>`
        : M.status === 'cancelled' ? '<span class="tag bad">Cancelled · refunded</span>'
          : M.status === 'closed' ? '<span class="tag bad">Betting closed · waiting on the result</span>' : '';
      const first = O[0];
      main.innerHTML = `<div class="mp-top">
        <div class="crumbs">${M.circle ? `<a href="#/circle/${M.circle.id}">${circleMark(M.circle, 15)} ${esc(M.circle.name)}</a>` : `<span class="crumb-site">${ICON.globe} Public bet</span>`} <span>//</span> <span>${esc(M.category)}</span> ${statusTag} ${editedTag(M)}</div>${exitBanner(M)}
        <div class="mp-head" style="margin-top:12px">${thumb(M, true)}<div class="grow"><h1 class="mp-title">${esc(M.question)}</h1>
            <div class="sub-meta">${M.closesAt ? `${M.status === 'open' ? 'Ends' : 'Ended'} ${dateLong(M.closesAt)}` : 'No end date'} · proposed by <a href="#/u/${esc(M.creator.username)}" style="color:var(--text);font-weight:600">${esc(M.creator.username)}</a></div></div>
          ${M.canEdit ? `<button class="btn btn-secondary btn-sm" id="edit-poll" title="Change the closing time or the rules">${ICON.pencil} Edit poll</button>` : ''}
          <button class="icon-btn" id="share" title="Copy link">${ICON.link}</button>
          <button class="icon-btn ${isBookmarked(M.id) ? 'on' : ''}" id="bmk" title="Bookmark" aria-label="Bookmark">${isBookmarked(M.id) ? ICON.bookmarkOn : ICON.bookmark}</button></div>
        <div class="chart-panel">${multi ? `<div class="legend">${series.map((s) => `<span style="color:${s.color}"><i style="background:${s.color}"></i>${esc(s.name)} ${pct(O[s.idx].yes)}</span>`).join('')}</div>`
          : `<div><span class="bigchance num"><span id="bigval"></span><small>${isYesNo(M) ? 'chance of yes' : esc(first.name)}</small></span></div>`}
        <div class="chart-wrap" id="chart"></div>
        <div class="metaline">
          <span class="num"><b style="color:var(--text)">${vol(M.volume)}</b> Vol.</span>
          <span>${M.traders} trader${M.traders === 1 ? '' : 's'}</span>
          <div class="ranges">${Object.keys(RANGES).map((r) => `<button data-r="${r}" class="${st.range === r ? 'active' : ''}">${r}</button>`).join('')}</div>
        </div></div>
        ${multi ? `<div class="otable">${leader.map((i) => `
          <div class="orow-big ${st.outcome === i ? 'sel' : ''}" data-o="${i}">
            <div class="nm">${esc(O[i].name)}</div><div class="big num">${pctOf(O[i])}</div>
            ${isOpen() ? `<button class="buybtn y" data-buy="${i}:yes">Yes ${cents(O[i].yes)}</button><button class="buybtn n" data-buy="${i}:no">No ${cents(O[i].no)}</button>` : `<span></span><span>${M.winner === i ? '<span class="tag good">Winner</span>' : ''}</span>`}
          </div>`).join('')}</div>` : ''}
        </div><div class="mp-bottom">
        <div class="rules-h"><span>Rules${M.edited ? ` · version ${M.version}` : ''}</span>${M.edited ? '<button class="linkish" id="hist2">See what changed</button>' : ''}</div><p class="rules" style="margin:0">${M.description ? esc(M.description) : `No fine print. Whoever proposed this${M.circle ? ', or the circle owner,' : ''} calls it. Argue about it in the comments.`}</p>
        ${manageBox()}
        <div class="tabs" id="info-tabs">
          ${[['holders', `Who's in (${M.holders.length})`], ['comments', `Comments (${M.commentList.length})`], ['activity', 'Activity']].map(([k, l]) => `<button data-t="${k}" class="${st.info === k ? 'active' : ''}">${l}</button>`).join('')}
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
      return `<div class="manage"><b>You run this one.</b>
        <p class="muted" style="margin:6px 0 14px">${M.circle ? 'You proposed it (or own the circle), so you make the call.' : 'You proposed it, so you make the call. Everyone on the site is trusting you.'} Winners get paid the second you do.</p>
        <div class="row" style="flex-wrap:wrap"><button class="btn btn-secondary" id="edit-poll2">${ICON.pencil} Edit the date or rules</button><button class="btn btn-primary" id="resolve">Call it</button><button class="btn btn-danger" id="cancel">Cancel and refund everyone</button></div></div>`;
    }

    function drawInfo() {
      const box = main.querySelector('#info');
      if (st.info === 'comments') {
        box.innerHTML = `<form id="cform" class="row" style="align-items:flex-start;margin-bottom:8px">${avatar(S.user.username, 36)}
          <div class="grow"><textarea class="input" id="ctext" maxlength="300" placeholder="Say something. Preferably wrong." style="min-height:44px;height:44px"></textarea></div>
          <button class="btn btn-primary" style="height:44px">Post</button></form>
          ${M.commentList.length ? M.commentList.map((c) => `<div class="cmt">${avatar(c.user.username, 32)}<div><b>${esc(c.user.username)}</b><small>${ago(c.t)}</small><p>${esc(c.text)}</p></div></div>`).join('')
            : '<p class="quiet">No comments. Somebody talk trash.</p>'}`;
        box.querySelector('#cform').addEventListener('submit', async (e) => {
          e.preventDefault();
          const t = box.querySelector('#ctext').value.trim(); if (!t) return;
          try { M = (await post(`/api/markets/${id}/comments`, { text: t })).market; drawMain(); } catch (ex) { toast(ex.message, 'err'); }
        });
      } else if (st.info === 'holders') {
        box.innerHTML = whoseIn(M);
      } else {
        box.innerHTML = M.activity.length ? M.activity.map((a) => `<div class="list-row">${avatar(a.user.username, 28)}
          <div class="grow"><b>${esc(a.user.username)}</b> ${a.kind === 'buy' ? 'bought' : 'sold'} <b>${esc(a.label)}</b> at ${cents(a.price)}
          <span class="muted"> · ${moneyFull(a.amount)}</span></div><span class="muted">${ago(a.t)}</span></div>`).join('')
          : '<p class="quiet">No trades yet. The tape is blank.</p>';
      }
    }

    // ----------------------------------------------------------------- trade panel
    function drawTrade() {
      const O = M.outcomes;
      const o = O[st.outcome];
      const focused = document.activeElement?.id === 'amt';
      const caret = focused ? document.activeElement.selectionStart : null;
      const header = `<div class="slip-title"><span>Bet slip</span><span>${slipNo(M)}</span></div>
        <div class="trade-head">${thumb(M)}<div><div class="q">${esc(M.question.length > 70 ? M.question.slice(0, 68) + '…' : M.question)}</div>
        <div class="s ${st.side === 'yes' && (M.binary ? st.outcome === 0 : true) ? 'up' : 'down'}">${esc(tokenLabel())}</div></div></div>`;

      if (M.status !== 'open') {
        const mine = (M.myPositions || []);
        trade.innerHTML = `${header}${emptyState({ tight: true, art: M.status === 'resolved' ? 'flag' : M.status === 'cancelled' ? 'paper' : 'scale', tone: M.status === 'resolved' ? 'lime' : 'cream',
          kicker: M.status === 'resolved' ? 'Settled' : M.status === 'cancelled' ? 'Cancelled' : 'Betting closed',
          title: M.status === 'resolved' ? `${esc(O[M.winner].name)} won.` : M.status === 'cancelled' ? 'Called off.' : 'Hands off.',
          text: M.status === 'closed' ? 'Time is up. Waiting on whoever runs this to call it.' : M.status === 'cancelled' ? 'Everybody got their money back. Nobody learned anything.' : 'Winning shares paid $1 each. Losers paid for the lesson.' })}
          ${mine.length ? `<div class="posbox"><h4>Your positions</h4>${mine.map(posRow).join('')}</div>` : ''}`;
        return;
      }
      if (!M.isMember) {
        trade.innerHTML = `${header}${emptyState({ tight: true, art: 'chip', tone: 'verm', kicker: 'Members only', title: 'Not in the circle.', text: `You can't bet on <b>${esc(M.circle.name)}</b> from the cheap seats.`, actions: '<button class="btn btn-primary" id="join">Take a seat</button>' })}`;
        trade.querySelector('#join').addEventListener('click', async () => {
          try { await post(`/api/circles/${M.circle.id}/join`, {}); M = (await get(`/api/markets/${id}`)).market; drawAll(); toast('You have a seat.', 'ok'); } catch (ex) { toast(ex.message, 'err'); }
        });
        return;
      }

      const buy = st.tab === 'buy';
      const pos = tokenPos();
      const price = tokenPrice();
      const optBtns = M.binary
        ? O.map((x, i) => `<button class="opt ${i === 0 ? 'y' : 'n'} ${st.outcome === i ? 'sel' : ''}" data-opt="${i}:yes">${esc(x.name)} ${cents(x.yes)}</button>`).join('')
        : `<button class="opt y ${st.side === 'yes' ? 'sel' : ''}" data-opt="${st.outcome}:yes">Yes ${cents(o.yes)}</button><button class="opt n ${st.side === 'no' ? 'sel' : ''}" data-opt="${st.outcome}:no">No ${cents(o.no)}</button>`;      // html: seguro (st.outcome es un índice numérico)
      const amt = parseAmount(st.amt);
      const q = st.quote;
      let warn = st.quoteErr, canGo = false;
      if (buy) {
        if (st.amt && !(amt >= S.minBet - 1e-9)) warn = warn || `Minimum bet is ${money(S.minBet)}`;
        else if (amt > S.user.balance + 1e-9) warn = 'Not enough funds';
        canGo = amt >= S.minBet - 1e-9 && amt <= S.user.balance + 1e-9 && !!q && !st.quoteErr;
      } else {
        const held = pos ? pos.shares : 0;
        if (amt > held * (1 + 1e-9) + 1e-9) warn = `You only hold ${num(held, 4)} shares`;
        canGo = amt > 0 && !!pos && amt <= held * (1 + 1e-9) + 1e-9 && !!q && !st.quoteErr;
      }
      const fs = Math.max(22, 42 - Math.max(0, (st.amt || '').length - 6) * 2.6);
      const chance = (x) => `${pct(x.priceBefore)} → ${pct(x.priceAfter)}`;
      const summary = !q ? '' : buy
        ? `<div class="r"><span>You pay</span><i></i><b>${money(q.amount)}</b></div>
           <div class="r"><span>Shares you get</span><i></i><b>${num(q.shares)}</b></div>
           <div class="r"><span>Avg price</span><i></i><b>${cents(q.avgPrice)}</b></div>
           <div class="r"><span>Chance of ${esc(sideLabel())}</span><i></i><b>${chance(q)}</b></div>
           <div class="r win"><span>To win</span><i></i><b>${money(q.payout)}</b><em>+${num(q.returnPct, 1)}%</em></div>`
        : `<div class="r"><span>Shares you sell</span><i></i><b>${num(q.shares)}</b></div>
           <div class="r"><span>Avg price</span><i></i><b>${cents(q.avgPrice)}</b></div>
           <div class="r"><span>Chance of ${esc(sideLabel())}</span><i></i><b>${chance(q)}</b></div>
           <div class="r win"><span>You get</span><i></i><b>${money(q.amount)}</b></div>`;

      trade.innerHTML = `${header}
        <div class="trade-tabs"><button data-tab="buy" class="${buy ? 'active' : ''}">Buy</button><button data-tab="sell" class="${!buy ? 'active' : ''}">Sell</button></div>
        <div class="opt-btns">${optBtns}</div>
        <div class="amt"><label for="amt">${buy ? 'Stake' : 'Shares'}</label>
          <div class="amt-input ${st.amt ? 'has' : ''}" style="font-size:${fs}px">${buy ? '<span>$</span>' : ''}<input id="amt" inputmode="decimal" autocomplete="off" placeholder="${buy ? '0' : '0'}" value="${esc(st.amt)}"></div></div>
        <div class="quick">${buy
          ? ['1', '10', '100', '1000'].map((v) => `<button data-add="${v}">+$${Number(v).toLocaleString()}</button>`).join('') + '<button data-max="1">Max</button>'
          : ['25', '50', '75'].map((v) => `<button data-pct="${v}">${v}%</button>`).join('') + '<button data-max="1">Max</button>'}</div>
        ${warn ? `<div class="error-text" style="margin:-4px 0 10px;text-align:right">${esc(warn)} ${warn === 'Not enough funds' ? '<a href="#" id="addf" style="text-decoration:underline;font-weight:600">Add funds</a>' : ''}</div>` : ''}
        <div class="summary">${summary}</div>
        <button class="btn btn-lg btn-block ${buy ? (st.side === 'yes' && (!M.binary || st.outcome === 0) ? 'btn-yes' : 'btn-no') : 'btn-primary'}" id="go" ${canGo && !st.busy ? '' : 'disabled'}>
          ${st.busy ? 'Working…' : buy ? `Review ${esc(sideLabel())} bet` : `Review sale of ${esc(sideLabel())}`}</button>
        <div class="balance-line">Weekly account <b title="${moneyFull(S.user.balance)}">${money(S.user.balance)}</b>${buy ? ` · min ${money(S.minBet)}, no cap` : ''}</div>
        ${(M.myPositions || []).filter((p) => !p.settled).length ? `<div class="posbox"><h4>Your positions</h4>${(M.myPositions || []).filter((p) => !p.settled).map(posRow).join('')}</div>` : ''}`;

      const inp = trade.querySelector('#amt');
      if (focused) { inp.focus(); try { inp.setSelectionRange(caret, caret); } catch { /* ignore */ } }
    }

    function posRow(p) {
      const pnl = p.pnl || 0;
      return `<div class="p"><div><b class="${p.side === 'yes' ? 'up' : 'down'}">${esc(p.label)}</b><div class="muted">${num(p.shares)} shares · avg ${cents(p.avgPrice)}${p.underOldRules ? ` <span class="tag" title="You bet before the rules or closing time changed">bet under version ${p.version}</span>` : ''}</div></div>
        <div style="text-align:right"><b class="num">${money(p.value ?? 0)}</b><div class="${pnl >= 0 ? 'up' : 'down'} num">${p.refunded ? 'refunded' : money(pnl, { plus: true })}</div></div></div>`;
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
      } catch (ex) { if (seq !== qSeq || dead) return; st.quote = null; st.quoteErr = ex.message === 'Not enough funds' ? '' : ex.message; }
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
      const t = e.target.closest('button,a'); if (!t) return;
      if (t.id === 'addf') { e.preventDefault(); document.getElementById('btn-deposit').click(); return; }
      if (t.dataset.tab) { st.tab = t.dataset.tab; st.amt = ''; st.quote = null; st.quoteErr = ''; drawTrade(); return; }
      if (t.dataset.opt) { const [o, s] = t.dataset.opt.split(':'); st.outcome = +o; st.side = s; drawAll(); requote(); return; }
      if (t.dataset.add) { st.amt = String(Math.round(((parseAmount(st.amt) || 0) + Number(t.dataset.add)) * 100) / 100); drawTrade(); requote(); return; }
      if (t.dataset.pct) { const p = tokenPos(); if (p) { st.amt = String(Math.floor(p.shares * Number(t.dataset.pct) / 100 * 1e6) / 1e6); drawTrade(); requote(); } return; }
      if (t.dataset.max) {
        if (st.tab === 'buy') st.amt = String(floorCents(S.user.balance)); else { const p = tokenPos(); st.amt = p ? String(p.shares) : ''; }
        drawTrade(); requote(); return;
      }
      if (t.id === 'go') await review();
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
      const sheet = modal(`<span class="lbl">${buy ? 'Check your bet' : 'Check your cash out'}</span><h2>${esc(tokenLabel())}</h2>
        <div class="summary cf" id="cf"><div class="spinner"></div></div>
        <div class="error-text" id="cf-err" style="min-height:20px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Back</button><button type="button" class="btn btn-primary" id="cf-ok" disabled>${buy ? 'Confirm bet' : 'Confirm sale'}</button></div>`);
      const box = sheet.el.querySelector('#cf'), errEl = sheet.el.querySelector('#cf-err'), ok = sheet.el.querySelector('#cf-ok');
      let q = null, sending = false;
      const row = (label, value, cls = '') => `<div class="r ${cls}"><span>${esc(label)}</span><i></i><b>${value}</b></div>`;
      const paint = () => {
        if (!q) { box.innerHTML = ''; ok.disabled = true; return; }
        const others = M.outcomes.map((o, i) => `<span>${esc(o.name)} <b>${q.pctAfter[i]}%</b></span>`).join('');
        box.innerHTML = (buy
          ? row('You pay', money(q.amount)) + row('Shares you get', num(q.shares)) + row('Average price', cents(q.avgPrice))
          : row('You receive', money(q.amount), 'win') + row('Shares you sell', num(q.shares)) + row('Average price', cents(q.avgPrice)))
          + row(`Chance of ${esc(sideLabel())}`, `${pct(q.priceBefore)} → ${pct(q.priceAfter)}`)
          + (buy ? row('If it wins you collect', `${money(q.payout)} <em class="up">+${num(q.returnPct, 1)}%</em>`)
            : row('Gain or loss on these shares', `<span class="${q.pnl >= 0 ? 'up' : 'down'}">${money(q.pnl, { plus: true })}</span>`) + row('Shares left', num(q.heldAfter)))
          + `<div class="cf-odds"><span class="lbl">Odds after this trade</span><div>${others}</div></div>`;
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
        sending = true; st.busy = true; ok.disabled = true; ok.textContent = 'Working…'; errEl.textContent = '';
        const send = { ...body, requestId: rid };
        if (buy) send.minShares = q.shares * 0.995; else send.minAmount = Math.floor(q.amount * 0.995 * 100) / 100;      // up to half a percent worse is fine, more is not
        try {
          const d = await post(`/api/markets/${id}/trade`, send);
          setUser(d.user); M = d.market;
          toast(buy ? `Slip printed: ${num(d.trade.shares)} shares of ${sideLabel()} for ${money(d.trade.amount)}` : `Cashed out ${money(d.trade.amount)}`, 'ok');
          st.amt = ''; st.quote = null; st.quoteErr = '';
          if (st.tab === 'sell' && !tokenPos()) st.tab = 'buy';
          sheet.close(); st.busy = false; drawAll();
          return;
        } catch (ex) {
          if (ex.status === 409) { await refresh(); errEl.textContent = 'The price moved while you were looking. These are the new numbers. Check them and confirm again.'; }
          else errEl.textContent = ex.message;
          if (ex.status !== 409 && /closed|no longer open|funds|hold/i.test(ex.message)) { q = null; paint(); get(`/api/markets/${id}`).then((r) => { M = r.market; drawAll(); }).catch(() => {}); }
        }
        sending = false; st.busy = false; ok.textContent = buy ? 'Confirm bet' : 'Confirm sale'; ok.disabled = !q;
      });
    }

    main.addEventListener('click', async (e) => {
      const t = e.target.closest('button, .orow-big'); if (!t) return;
      if (t.id === 'share') { copyText(location.href.split('?')[0]); return; }
      if (t.id === 'bmk') { const on = toggleBookmark(M.id); t.classList.toggle('on', on); t.innerHTML = on ? ICON.bookmarkOn : ICON.bookmark; return; }
      if (t.dataset.r) { st.range = t.dataset.r; drawMain(); return; }
      if (t.dataset.t) { st.info = t.dataset.t; main.querySelectorAll('#info-tabs button').forEach((b) => b.classList.toggle('active', b === t)); drawInfo(); return; }
      if (t.dataset.buy) { const [o, s] = t.dataset.buy.split(':'); st.outcome = +o; st.side = s; st.tab = 'buy'; drawAll(); requote(); trade.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); return; }
      if (t.classList.contains('orow-big')) { st.outcome = +t.dataset.o; drawAll(); return; }
      if (t.id === 'edit-poll' || t.id === 'edit-poll2') return openEditPoll(M, (market) => { M = market; drawAll(); });
      if (t.id === 'hist' || t.id === 'hist2') return openHistory(M);
      if (t.dataset.withdraw) return withdrawFlow(M, t.dataset.withdraw, (market) => { M = market; drawAll(); });
      if (t.id === 'resolve') return openResolve();
      if (t.id === 'cancel') {
        if (await confirmBox({ title: 'Call it off?', text: 'Every bet is refunded in full and the market closes. No take-backs.', confirm: 'Cancel and refund', danger: true })) {
          try { const d = await post(`/api/markets/${id}/cancel`); setUser(d.user); M = d.market; drawAll(); toast('Called off. Everybody got their money back.', 'ok'); } catch (ex) { toast(ex.message, 'err'); }
        }
      }
    });

    function openResolve() {
      const mm = modal(`<span class="lbl">The verdict</span><h2>Who won?</h2><p class="lede">Pick the winner. Winners get $1 a share, instantly. Losers get a story.</p>
        <div class="stack" style="gap:8px">${M.outcomes.map((o, i) => `<button class="btn btn-outline btn-block" data-w="${i}" style="justify-content:space-between"><span>${esc(o.name)}</span><span class="muted">${pct(o.yes)}</span></button>`).join('')}</div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>Not yet</button></div>`);
      mm.el.querySelectorAll('[data-w]').forEach((b) => b.addEventListener('click', async () => {
        const name = M.outcomes[+b.dataset.w].name;
        if (!(await confirmBox({ title: `Call it for "${name}"?`, text: 'This pays everybody out and can\'t be undone.', confirm: 'Call it' }))) return;
        try { const d = await post(`/api/markets/${id}/resolve`, { outcome: +b.dataset.w }); setUser(d.user); M = d.market; mm.close(); drawAll(); toast(`Settled: ${name} won`, 'ok'); } catch (ex) { toast(ex.message, 'err'); mm.close(); }
      }));
    }

    const drawAll = () => { drawMain(); drawTrade(); };
    drawAll();
    get(`/api/markets?circle=${M.circle ? M.circle.id : 'site'}&status=open&sort=trending`).then((d) => {
      const rel = d.markets.filter((m) => m.id !== M.id).slice(0, 5);
      const box = root.querySelector('#related'); if (!box || dead || !rel.length) return;
      box.innerHTML = `<h4>${M.circle ? `Also on the board in ${esc(M.circle.name)}` : 'More public bets'}</h4>` + rel.map((m) => {
        const lead = m.outcomes.reduce((a, b) => (b.yes > a.yes ? b : a));
        return `<a class="rel-row" href="#/market/${m.id}">${thumb(m)}<span class="t">${esc(m.question)}</span><span class="p">${pct(lead.yes)}<small>${esc(lead.name)}</small></span></a>`;
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
