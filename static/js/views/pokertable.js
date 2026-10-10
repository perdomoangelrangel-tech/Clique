import { get, post } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, debounce, ICON, avatar } from '../util.js';
import { modal, toast, copyText } from '../ui.js';
import { suitSvg } from '../art.js';
import { burst } from '../games/common.js';
import { emptyState } from './components.js';
import { amt, field, blindsText, moneyTag } from './pokerfmt.js';

const DEFAULTS = {
  fake: { bigBlind: '20', smallBlind: '10', stack: '1000', rebuy: true },
  real: { bigBlind: '1', smallBlind: '0.5', stack: '100', rebuy: false },
};
const TURN_LABELS = { 0: 'No clock', 15: '15 seconds', 30: '30 seconds', 45: '45 seconds', 60: '1 minute', 90: '90 seconds', 120: '2 minutes' };
const UP_LABELS = { 0: 'Never', 5: 'Every 5 hands', 10: 'Every 10 hands', 15: 'Every 15 hands', 20: 'Every 20 hands' };

/** "Ts" -> a paper card. "back" -> the striped back. size: 'l' (your hand), 'm' (board), 'r' (a revealed hand), 's' (a back). */
const card = (c, size = 's', fresh = false) => {
  const cls = `pk-pc ${size} ${fresh ? 'deal' : ''}`;
  if (!c || c === 'back') return `<div class="pc down ${cls}"><div class="pc-in"><div class="pc-front"></div><div class="pc-back"><span></span></div></div></div>`;
  const r = c[0] === 'T' ? '10' : c[0], su = c[1].toUpperCase(), red = su === 'H' || su === 'D';
  return `<div class="pc ${red ? 'red' : ''} ${cls}"><div class="pc-in"><div class="pc-front"><span class="tl">${r}${suitSvg(su, 18)}</span><span class="mid">${suitSvg(su, 40)}</span><span class="br">${r}${suitSvg(su, 18)}</span></div><div class="pc-back"><span></span></div></div></div>`;
};
const LAST = { check: 'Check', call: 'Call', bet: 'Bet', raise: 'Raise' };

export default {
  async mount(root, [id]) {
    let V = null, skew = 0, dead = false, busy = false;
    let draft = null, draftRev = -1, lastStatus = null, raiseTo = null, burstKey = '', wasIn = false;
    let wasMyTurn = false, raiseOpen = false, pre = null, preBet = 0, preKey = '', lastBarKey = null, logOpen = false;
    const seen = new Set();

    root.innerHTML = `<div class="page pk-page"><div id="pk-head"></div><div id="pk-main"></div></div>`;
    const $ = (s) => root.querySelector(s);
    const now = () => Date.now() + skew;
    const scale = () => (V ? V.scale : 1);
    const A = (n) => amt(n, scale());

    // ------------------------------------------------------------------ loading
    async function load(first = false) {
      try {
        const d = await get(`/api/poker/tables/${id}`);
        if (dead) return;
        if (d.user) setUser(d.user);
        take(d.table);
      } catch (ex) {
        if (dead) return;
        if (ex.status === 404) { V = null; render(); return; }
        if (first) { toast(ex.message, 'err'); go('#/poker'); }
      }
    }
    function take(table) {
      if (table && V && table.v < V.v && table.id === V.id) return;           // an older answer arrived late
      V = table;
      if (V) { skew = V.serverNow - Date.now(); if (V.mySeat != null) wasIn = true; }
      render();
    }
    const reload = debounce(() => load(), 60);

    async function call(path, body = {}, okMsg) {
      if (busy) return null;
      busy = true;
      try {
        const d = await post(`/api/poker/tables/${id}/${path}`, body);
        if (d.user) setUser(d.user);
        take(d.table);
        if (okMsg) toast(okMsg, 'ok');
        busy = false;
        return d;
      } catch (ex) { busy = false; toast(ex.message, 'err'); load(); return null; }
    }

    // ------------------------------------------------------------------ pieces
    const me = () => (V && V.mySeat != null ? V.seats[V.mySeat] : null);
    const seatedCount = () => V.seats.filter(Boolean).length;
    const iAmHost = () => V && V.isHost;

    function head() {
      const s = V.settings, m = me();
      return `<div class="pk-head ${V.status === 'playing' ? 'compact' : ''}"><div><span class="kicker">Poker // ${V.visibility === 'private' ? 'private table' : 'public table'}</span>
          <h1>${esc(V.name)}</h1>
          <div class="pk-tags">${moneyTag(s.money)}<span class="tag">${V.visibility === 'private' ? `${ICON.lock} Code only` : `${ICON.globe} Public`}</span>
            <span class="tag">Blinds <b class="num">${blindsText(V.blinds.sb, V.blinds.bb, V.scale)}</b></span>${V.status === 'playing' ? `<span class="tag">Hand <b class="num">${V.handNo}</b></span>` : ''}
            ${V.ending ? '<span class="tag bad">Ending after this hand</span>' : ''}</div></div>
        <div class="pk-head-btns">${V.code ? `<button class="btn btn-secondary btn-sm" id="pk-copy" title="Copy the table code">Code <b class="num">${V.code}</b> ${ICON.copy}</button>` : ''}
          ${V.status === 'playing' && iAmHost() && !V.ending ? '<button class="btn btn-secondary btn-sm" id="pk-end">End game</button>' : ''}
          ${m ? `<button class="btn btn-danger btn-sm" id="pk-leave">Leave table</button>` : '<a class="btn btn-secondary btn-sm" href="#/poker">All tables</a>'}</div></div>`;
    }

    // ------------------------------------------------------------------ setup phase
    function seatRows() {
      const accepted = V.seats.filter((s) => s && V.votes[s.userId] === true).length;
      const rows = V.seats.map((s, i) => {
        if (!s) return `<div class="pk-row vacant"><span class="pk-chair">${i + 1}</span><span>Empty chair</span></div>`;
        const v = V.votes[s.userId];
        const chip = v === true ? '<span class="pk-vote yes">Ready</span>' : v === false ? '<span class="pk-vote no">Declined</span>' : '<span class="pk-vote wait">Thinking</span>';
        return `<div class="pk-row ${s.isMe ? 'me' : ''}"><span class="pk-chair">${avatar(s.name, 30)}</span><div class="grow"><b>${esc(s.name)}</b>${s.isHost ? ' <span class="tag">Host</span>' : ''}${s.isMe ? ' <span class="tag">You</span>' : ''}</div>${chip}
          ${iAmHost() && !s.isMe ? `<button class="icon-btn" data-kick="${s.userId}" title="Remove ${esc(s.name)}" aria-label="Remove ${esc(s.name)}">${ICON.x}</button>` : ''}</div>`;
      }).join('');
      const watch = V.mySeat == null ? `<div class="pk-watch"><span>You are watching.</span><button class="btn btn-primary btn-sm" id="pk-sit">Sit down</button></div>` : '';
      return `<div class="pk-panel-head"><div><span class="kicker">The table</span><h2>Who is sitting</h2></div><span class="num pk-count">${seatedCount()} / ${V.settings.maxSeats}</span></div>${watch}
        <div class="pk-rows">${rows}</div>
        <p class="pk-note">${accepted} of ${seatedCount()} have accepted the settings. The host can start when it is everyone.</p>`;
    }

    function draftFromSettings() {
      const s = V.settings, sc = V.scale;
      draft = { money: s.money, bigBlind: field(s.bigBlind, sc), smallBlind: field(s.smallBlind, sc), stack: field(s.stack, sc),
        maxSeats: s.maxSeats, turnSeconds: s.turnSeconds, rebuy: s.rebuy, blindsUp: s.blindsUp };
      draftRev = V.settingsRev;
    }
    const draftPayload = () => ({ money: draft.money, bigBlind: Number(draft.bigBlind), smallBlind: Number(draft.smallBlind), stack: Number(draft.stack),
      maxSeats: Number(draft.maxSeats), turnSeconds: Number(draft.turnSeconds), rebuy: !!draft.rebuy, blindsUp: Number(draft.blindsUp) });
    const dirty = () => {
      if (!draft) return false;
      const s = V.settings, sc = V.scale;
      return draft.money !== s.money || Number(draft.bigBlind) !== s.bigBlind / sc || Number(draft.smallBlind) !== s.smallBlind / sc || Number(draft.stack) !== s.stack / sc
        || Number(draft.maxSeats) !== s.maxSeats || Number(draft.turnSeconds) !== s.turnSeconds || !!draft.rebuy !== s.rebuy || Number(draft.blindsUp) !== s.blindsUp;
    };

    function settingsHost() {
      const real = draft.money === 'real', turns = real ? [15, 30, 45, 60, 90, 120] : [0, 15, 30, 45, 60, 90, 120];
      const opt = (arr, cur, labels) => arr.map((v) => `<option value="${v}" ${Number(cur) === v ? 'selected' : ''}>${labels[v] ?? v}</option>`).join('');
      return `<div class="pk-panel-head"><div><span class="kicker">You are the host</span><h2>Table settings</h2></div></div>
        <div class="field"><label>Money</label><div class="seg stretch" id="pk-money"><button type="button" data-m="fake" class="${!real ? 'active' : ''}">Fake chips</button><button type="button" data-m="real" class="${real ? 'active' : ''}">Real cash</button></div>
          <small>${real ? 'Everyone buys in from their real cash balance. It comes back when they leave. Everyone has to accept first.' : 'Pretend chips, free to lose. Your real money is never touched.'}</small></div>
        <div class="pk-fields">
          <div class="field"><label for="pk-bb">Big blind ${real ? '($)' : '(chips)'}</label><input class="input num" id="pk-bb" data-k="bigBlind" inputmode="decimal" value="${esc(draft.bigBlind)}"></div>
          <div class="field"><label for="pk-sb">Small blind</label><input class="input num" id="pk-sb" data-k="smallBlind" inputmode="decimal" value="${esc(draft.smallBlind)}"></div>
          <div class="field"><label for="pk-stack">${real ? 'Buy-in ($)' : 'Starting chips'}</label><input class="input num" id="pk-stack" data-k="stack" inputmode="decimal" value="${esc(draft.stack)}"></div>
          <div class="field"><label for="pk-seats-sel">Seats</label><select class="select" id="pk-seats-sel" data-k="maxSeats">${opt([2, 3, 4, 5, 6, 7, 8, 9], draft.maxSeats, {})}</select></div>
          <div class="field"><label for="pk-turn">Turn clock</label><select class="select" id="pk-turn" data-k="turnSeconds">${opt(turns, draft.turnSeconds, TURN_LABELS)}</select></div>
          <div class="field"><label for="pk-up">Blinds double</label><select class="select" id="pk-up" data-k="blindsUp">${opt([0, 5, 10, 15, 20], draft.blindsUp, UP_LABELS)}</select></div></div>
        <label class="pk-check"><input type="checkbox" id="pk-rebuy" ${draft.rebuy ? 'checked' : ''}><span>Allow rebuys when you go broke</span></label>
        <div class="pk-save"><span class="${dirty() ? 'dirty' : ''}">${dirty() ? 'Unsaved changes. Saving asks everyone to accept again.' : 'Saved.'}</span><button class="btn btn-primary" id="pk-save" ${dirty() ? '' : 'disabled'}>Save settings</button></div>
        <div class="error-text" id="pk-set-err"></div>`;
    }
    function settingsView() {
      const s = V.settings, sc = V.scale, real = s.money === 'real';
      return `<div class="pk-panel-head"><div><span class="kicker">Proposed by ${esc(V.hostName)}</span><h2>Table settings</h2></div></div>
        <dl class="pk-dl"><div><dt>Money</dt><dd>${real ? '<b>Real cash</b> from your balance' : '<b>Fake chips</b>, nothing real'}</dd></div>
          <div><dt>Blinds</dt><dd class="num">${blindsText(s.smallBlind, s.bigBlind, sc)}</dd></div>
          <div><dt>${real ? 'Buy-in' : 'Starting chips'}</dt><dd class="num">${amt(s.stack, sc)}</dd></div>
          <div><dt>Seats</dt><dd class="num">${s.maxSeats}</dd></div><div><dt>Turn clock</dt><dd>${TURN_LABELS[s.turnSeconds]}</dd></div>
          <div><dt>Blinds double</dt><dd>${UP_LABELS[s.blindsUp]}</dd></div><div><dt>Rebuys</dt><dd>${s.rebuy ? 'Allowed' : 'Off'}</dd></div></dl>
        ${real ? `<p class="pk-warn">${ICON.warn} This is real money. If you accept, ${amt(s.stack, sc)} leaves your cash when the host starts and comes back when you leave.</p>` : ''}`;
    }

    function voteBar() {
      const m = me(), s = V.settings, real = s.money === 'real';
      const players = V.seats.filter(Boolean);
      const waiting = players.filter((p) => V.votes[p.userId] !== true).map((p) => p.name);
      const cash = S.user ? S.user.balance : 0, short = real && m && cash + 1e-9 < s.stack / 100;
      if (!m) return '<p class="pk-note">Sit down to vote on the settings.</p>';
      const mine = V.votes[m.userId];
      const voteBtns = iAmHost() ? '' : `<div class="pk-vote-btns"><button class="btn ${mine === true ? 'btn-primary' : 'btn-secondary'}" id="pk-yes" ${short ? 'disabled' : ''}>${mine === true ? 'Accepted' : real ? `Accept: I'm in for ${A(s.stack)}` : 'Accept'}</button>
        <button class="btn ${mine === false ? 'btn-danger' : 'btn-secondary'}" id="pk-no">${mine === false ? 'Declined' : 'Decline'}</button></div>`;
      const startBtn = iAmHost() ? `<button class="btn btn-primary btn-lg" id="pk-start" ${players.length >= 2 && !waiting.length ? '' : 'disabled'}>Start the game</button>` : '';
      const hint = iAmHost()
        ? (players.length < 2 ? 'You need at least two players.' : waiting.length ? `Waiting for: ${waiting.map(esc).join(', ')}.` : 'Everyone is ready.')
        : (mine === true ? 'You are in. Waiting for the host to start.' : 'The host picked these settings. You have to accept before the game starts.');
      return `<div class="pk-startbar"><div class="pk-hint"><b>${hint}</b>${short ? `<br><span class="pk-warn-inline">You only have ${amt(Math.round(cash * 100), 100)} in cash. The buy-in is ${A(s.stack)}.</span>` : ''}${real && iAmHost() ? `<br><span class="pk-muted">Your cash: ${amt(Math.round(cash * 100), 100)}</span>` : ''}</div>${voteBtns}${startBtn}</div>`;
    }

    function renderSetup(rebuild) {
      if (rebuild) {
        $('#pk-main').innerHTML = `<div class="pk-setup"><section class="card-box pk-panel" id="pk-seatbox"></section><section class="card-box paper pk-panel" id="pk-setbox"></section></div><div id="pk-vote"></div>`;
      }
      $('#pk-seatbox').innerHTML = seatRows();
      if (iAmHost()) {
        if (draft === null || draftRev !== V.settingsRev) draftFromSettings();
        if (rebuild || !$('#pk-bb')) $('#pk-setbox').innerHTML = settingsHost();
        else refreshSaveBar();
      } else { draft = null; $('#pk-setbox').innerHTML = settingsView(); }
      $('#pk-vote').innerHTML = voteBar();
    }
    function refreshSaveBar() {
      const bar = $('.pk-save'); if (!bar) return;
      bar.querySelector('span').className = dirty() ? 'dirty' : '';
      bar.querySelector('span').textContent = dirty() ? 'Unsaved changes. Saving asks everyone to accept again.' : 'Saved.';
      bar.querySelector('button').disabled = !dirty();
    }

    // ------------------------------------------------------------------ the table
    const TALL = () => window.matchMedia('(max-width: 720px)').matches;       // phones get a tall table (the same width poker.css switches at)
    const cyOf = () => (TALL() ? 46 : 49);
    function positions() {
      const n = V.settings.maxSeats, base = V.mySeat != null ? V.mySeat : 0, tall = TALL();
      const rx = tall ? 38 : 46, ry = tall ? 39 : 38, e = 2.4;       // e > 2 squares the ellipse off, like a racetrack
      const sg = (v) => Math.sign(v) * Math.abs(v) ** (2 / e);
      return Array.from({ length: n }, (_, i) => {
        const th = (90 + (i - base) * (360 / n)) * Math.PI / 180;
        return { x: 50 + rx * sg(Math.cos(th)), y: cyOf() + ry * sg(Math.sin(th)) };
      });
    }
    function betSpot(i, p) {
      const tall = TALL();
      if (i === V.mySeat) return { x: 50 + (tall ? 27 : 15), y: tall ? 66 : 68 };       // beside your own cards
      const k = tall ? 0.62 : 0.56;
      return { x: 50 + (p.x - 50) * k, y: cyOf() + (p.y - cyOf()) * k };
    }

    function seatHtml(s, i, p, h, res, won) {
      const style = `left:${p.x}%;top:${p.y}%`;
      if (!s) return `<div class="pk-seat vacant" style="${style}"><span class="pk-avwrap"><span class="pk-av"></span></span></div>`;
      const st = s.busted ? 'busted' : s.status;
      const acting = !!h && h.toAct === i && h.street !== 'ended';
      let tag = '', tagCls = '';
      if (s.busted) { tag = 'Busted'; tagCls = 'fold'; }
      else if (s.leaving) { tag = 'Leaving'; tagCls = 'fold'; }
      else if (!res && st === 'folded') { tag = 'Fold'; tagCls = 'fold'; }
      else if (!res && st === 'allin') { tag = 'All in'; tagCls = 'allin'; }
      else if (!res && s.last) { tag = LAST[s.last]; tagCls = s.last; }
      else if (V.status === 'playing' && (!h || st === 'out')) { tag = 'Next hand'; tagCls = 'wait'; }
      const w = won.get(i), handName = res && res.hands && res.hands[String(i)];
      const cards = s.cards, side = p.x < 50 || Math.abs(p.x - 50) < 10 ? 'r' : 'l';
      const deal = (size) => cards.map((c, k) => { const key = `${h ? h.no : 0}-s${i}-${k}-${c === 'back' ? 'b' : 'f'}`; const fresh = !seen.has(key); seen.add(key); return card(c, size, fresh && c !== 'back'); }).join('');
      let cardsHtml = '';
      if (cards && s.isMe) {
        const mine = h && h.mine;
        cardsHtml = `<div class="pk-hero">${deal('l')}</div>${mine ? `<div class="pk-hand"><b>${esc(mine.name)}</b>${mine.draws.length ? `<i>${esc(mine.draws.join(' · '))}</i>` : ''}</div>` : ''}`;
      } else if (cards) cardsHtml = `<div class="pk-backs ${side}">${deal(cards[0] === 'back' ? 's' : 'r')}</div>`;
      const toks = (h && h.button === i ? '<span class="pk-tok d" title="Dealer button">D</span>' : '')
        + (h && h.street !== 'ended' && h.sb === i ? '<span class="pk-tok">SB</span>' : '') + (h && h.street !== 'ended' && h.bb === i ? '<span class="pk-tok">BB</span>' : '');
      const ring = acting ? '<svg class="pk-ring" viewBox="0 0 100 100" aria-hidden="true"><circle class="trk" cx="50" cy="50" r="47"/><circle class="arc" cx="50" cy="50" r="47" pathLength="100"/></svg>' : '';
      return `<div class="pk-seat ${s.isMe ? 'hero' : ''} ${st} ${acting ? 'acting' : ''} ${w ? 'win' : ''}" style="${style}">
        <div class="pk-avwrap">${ring}<span class="pk-av">${avatar(s.name, 64)}</span>${cardsHtml}
          ${toks ? `<span class="pk-toks">${toks}</span>` : ''}
          ${w ? `<span class="pk-badge win num">+${A(w)}</span>` : tag ? `<span class="pk-badge ${tagCls}">${tag}</span>` : ''}</div>
        <div class="pk-plate"><b class="pk-name">${esc(s.name)}</b><span class="pk-stack num">${A(s.stack)}</span></div>
        ${handName && !s.isMe && cards && cards[0] !== 'back' ? `<span class="pk-handname">${esc(handName)}</span>` : ''}</div>`;
    }

    function felt() {
      const h = V.hand, pos = positions(), res = h && h.result, real = V.settings.money === 'real';
      const won = new Map();
      if (res) res.pots.forEach((p) => { if (!p.returned) p.winners.forEach((w) => won.set(w.seat, (won.get(w.seat) || 0) + w.amount)); });
      const board = h ? h.board : [];
      const boardHtml = Array.from({ length: 5 }, (_, i) => {
        if (!board[i]) return '<div class="pk-slot"></div>';
        const k = `${h.no}-b${i}`; const fresh = !seen.has(k); seen.add(k);
        return card(board[i], 'm', fresh);
      }).join('');
      const betHtml = V.seats.map((s, i) => {
        if (!s || !s.bet || res) return '';
        const b = betSpot(i, pos[i]);
        return `<span class="pk-bet num" style="left:${b.x}%;top:${b.y}%"><i></i>${A(s.bet)}</span>`;
      }).join('');
      const potHtml = h && !res && h.pot > 0 ? `<div class="pk-pot" title="Everything in the middle, including this round's bets"><i></i><b class="num">${A(h.pot)}</b></div>` : '';
      const centre = !h ? `<div class="pk-wait">${seatedCount() < 2 ? 'Waiting for another player.' : 'Dealing the next hand...'}</div>` : res ? resultBox(res) : '';
      return `<div class="pk-table ${real ? 'real' : ''}"><span class="pk-mark">Clique Poker</span></div><div class="pk-board">${boardHtml}</div>${potHtml}${centre}${betHtml}${V.seats.map((s, i) => seatHtml(s, i, pos[i], h, res, won)).join('')}`;
    }

    function resultBox(res) {
      const lines = res.pots.map((p) => p.winners.map((w) => {
        const s = V.seats[w.seat]; const who = s ? s.name : 'Somebody';
        if (p.returned) return `<div class="pk-res-line dim">${esc(who)} gets ${A(w.amount)} back</div>`;
        return `<div class="pk-res-line"><b>${esc(who)}</b> wins <b class="num">${A(w.amount)}</b>${w.hand ? ` <span>${esc(w.hand)}</span>` : res.reason === 'fold' ? ' <span>everyone else folded</span>' : ''}</div>`;
      }).join('')).join('');
      return `<div class="pk-result">${lines}</div>`;
    }

    // ------------------------------------------------------------------ the buttons
    const toCallNow = () => { const m = me(), h = V.hand; return m && h ? Math.max(0, Math.min(h.currentBet - m.bet, m.stack)) : 0; };

    function actionBar() {
      const h = V.hand, m = me();
      if (!m) {
        const free = V.seats.some((s) => !s);
        return `<div class="pk-bar quiet">${free ? `<span>You are watching this table.</span><button class="btn btn-primary" id="pk-sit">Sit down</button>` : '<span>You are watching. The table is full.</span>'}</div>`;
      }
      if (m.busted) return `<div class="pk-bar quiet"><span>You are out of chips.</span>${V.settings.rebuy ? `<button class="btn btn-primary" id="pk-rebuy">Rebuy for ${A(V.settings.stack)}</button>` : ''}</div>`;
      if (!h) return '<div class="pk-bar quiet"><span>Waiting for the next hand.</span></div>';
      if (h.street === 'ended') return '<div class="pk-bar quiet"><span id="pk-next-bar">Next hand coming up.</span></div>';
      if (m.leaving) return '<div class="pk-bar quiet"><span>You are leaving after this hand.</span></div>';
      if (m.status === 'folded') return '<div class="pk-bar quiet"><span>You folded. Watch them sweat.</span></div>';
      if (m.status === 'out') return '<div class="pk-bar quiet"><span>You are dealt in from the next hand.</span></div>';
      const a = h.actions;
      if (!a) {
        const who = h.toAct != null && V.seats[h.toAct] ? V.seats[h.toAct].name : null;
        if (h.runout || m.status !== 'in') return `<div class="pk-bar quiet"><span>${h.runout ? 'All in. Here comes the board.' : who ? `Waiting for <b>${esc(who)}</b>.` : 'Waiting...'}</span></div>`;
        const tc = toCallNow();                                    // pick your move before your turn comes
        return `<div class="pk-bar pre"><div class="pk-prehint">${who ? `Waiting for <b>${esc(who)}</b>.` : 'Waiting...'} Pick your move in advance:</div>
          <div class="pk-btnrow"><button class="pk-btn ${pre === 'cf' ? 'on' : ''}" data-pre="cf">Check / Fold</button>
            <button class="pk-btn ${pre === 'cc' ? 'on' : ''}" data-pre="cc">${tc > 0 ? `Call <b class="num">${A(tc)}</b>` : 'Check'}<small>just this bet</small></button>
            <button class="pk-btn ${pre === 'ca' ? 'on' : ''}" data-pre="ca">Call any<small>whatever it costs</small></button></div></div>`;
      }
      const mySeat = V.seats[V.mySeat], cb = a.currentBet, potAfter = h.pot + a.toCall;
      const clamp = (v) => Math.max(a.minRaiseTo, Math.min(a.maxRaiseTo, Math.round(v)));
      if (raiseTo === null || raiseTo < a.minRaiseTo || raiseTo > a.maxRaiseTo) raiseTo = a.minRaiseTo;
      const allInCall = a.toCall >= mySeat.stack;
      const callBtn = a.canCheck ? '<button class="pk-btn go" data-a="check">Check</button>' : `<button class="pk-btn go" data-a="call">Call <b class="num">${A(a.toCall)}</b>${allInCall ? '<small>all in</small>' : ''}</button>`;
      const verb = cb === 0 ? 'Bet' : 'Raise';
      const onlyAllIn = a.canRaise && a.minRaiseTo >= a.maxRaiseTo;
      let raiseBtn = '', panel = '';
      if (a.canRaise) {
        if (onlyAllIn) raiseBtn = `<button class="pk-btn raise confirm" data-a="allin">All in <b class="num">${A(a.maxRaiseTo)}</b></button>`;
        else if (!raiseOpen) raiseBtn = `<button class="pk-btn raise" data-open-raise>${verb}...</button>`;
        else {
          raiseBtn = `<button class="pk-btn raise confirm" id="pk-raise">${verb === 'Bet' ? 'Bet' : 'Raise to'} <b class="num" id="pk-raise-amt">${A(raiseTo)}</b></button>`;
          panel = `<div class="pk-rpanel"><div class="pk-quick"><button data-q="${a.minRaiseTo}">Min</button><button data-q="${clamp(cb + 0.5 * potAfter)}">½ pot</button><button data-q="${clamp(cb + 0.75 * potAfter)}">¾ pot</button><button data-q="${clamp(cb + potAfter)}">Pot</button><button data-q="${a.maxRaiseTo}">All in</button></div>
            <div class="pk-rrow"><button class="pk-step" data-step="-1" aria-label="Less">−</button><input type="range" class="gm-range" id="pk-slide" min="${a.minRaiseTo}" max="${a.maxRaiseTo}" step="1" value="${raiseTo}" aria-label="Raise amount"><button class="pk-step" data-step="1" aria-label="More">+</button>
              <input class="input num" id="pk-amt" inputmode="decimal" value="${field(raiseTo, V.scale)}" aria-label="Raise to"></div>
            <button class="pk-cancel" data-close-raise>Never mind</button></div>`;
        }
      }
      return `<div class="pk-bar turn"><div class="pk-turnhead"><span class="lbl">Your turn</span><span class="pk-time num" id="pk-time"></span></div>${panel}
        <div class="pk-btnrow"><button class="pk-btn fold" data-a="fold">Fold</button>${callBtn}${raiseBtn}</div></div>`;
    }
    const barKey = () => {
      const m = me(), h = V.hand;
      return JSON.stringify([m && [m.status, m.busted, m.leaving, m.stack, m.bet], h && [h.no, h.street, h.toAct, h.runout, h.actions, h.pot, h.currentBet, h.nextAt ? 1 : 0], V.mySeat, raiseOpen, pre, V.seats.some((x) => !x)]);
    };
    function refreshBar() { $('#pk-bar').innerHTML = actionBar(); lastBarKey = barKey(); $('#pk-bar').classList.toggle('stick', !!$('#pk-bar .turn, #pk-bar .pre')); tickClock(); }

    /** Your move was picked in advance: play it the moment the action reaches you. */
    function runPre() {
      const a = V.hand && V.hand.actions;
      if (!pre || !a || busy) return;
      const p = pre; pre = null;
      if (p === 'cc' && a.currentBet !== preBet) { toast('The bet changed, so it is up to you.', 'ok'); refreshBar(); return; }
      call('action', { action: p === 'cf' ? (a.canCheck ? 'check' : 'fold') : (a.canCheck ? 'check' : 'call') });
    }

    function logBox() {
      const lines = V.log.slice(logOpen ? -14 : -3).reverse();
      return `<div class="pk-log-head"><span class="lbl">The action</span><button class="pk-link" id="pk-log-toggle">${logOpen ? 'Show less' : 'Show more'}</button></div>${lines.length ? lines.map((l, i) => `<div class="pk-logline ${i === 0 ? 'new' : ''}">${esc(l)}</div>`).join('') : '<div class="pk-logline">Nothing yet.</div>'}`;
    }

    function renderPlaying(rebuild) {
      if (seen.size > 600) seen.clear();
      if (rebuild) { $('#pk-main').innerHTML = `<div class="pk-play"><div class="pk-felt" id="pk-felt"></div><div id="pk-bar"></div><div class="pk-log" id="pk-log"></div></div>`; lastBarKey = null; }
      const h = V.hand, pk = h ? `${h.no}-${h.street}` : '';
      if (pk !== preKey) { preKey = pk; pre = null; raiseOpen = false; raiseTo = null; }       // a new street or hand: start fresh
      if (!(h && h.actions)) raiseOpen = false;
      $('#pk-felt').innerHTML = felt();
      if (rebuild || barKey() !== lastBarKey) refreshBar();            // leave the raise slider alone while nothing changed
      $('#pk-log').innerHTML = logBox();
      const res = h && h.result;
      if (res) {
        const key = `${h.no}`;
        if (burstKey !== key) {
          burstKey = key;
          const mine = V.mySeat != null && res.pots.some((p) => !p.returned && p.winners.some((w) => w.seat === V.mySeat));
          if (mine) { const el = $('#pk-felt'); const r = el.getBoundingClientRect(); burst(el, r.width / 2, r.height * 0.5, { count: 60, power: 330, colors: ['#C6F432', '#EFE6D2', '#FF4B2B'] }); }
        }
      }
      tickClock();
      runPre();
      const mineNow = !!(h && h.actions);
      if (mineNow && !wasMyTurn) bringIntoView();
      wasMyTurn = mineNow;
    }
    /** The action is on you: make sure your seat and your buttons are both on screen. */
    function bringIntoView() {
      const f = $('#pk-felt'), b = $('#pk-bar'); if (!f || !b) return;
      const over = f.getBoundingClientRect().bottom - (window.innerHeight - b.offsetHeight - 22);
      if (over > 0) window.scrollBy({ top: over, behavior: 'smooth' });
    }

    // ------------------------------------------------------------------ clock
    function tickClock() {
      if (!V || !V.hand) return;
      const h = V.hand;
      const left = h.deadline ? Math.max(0, h.deadline - now()) : null;
      const total = V.settings.turnSeconds * 1000;
      const t = $('#pk-time');
      if (t) t.textContent = left == null ? 'no clock' : `${Math.ceil(left / 1000)}s`;
      const arc = root.querySelector('.pk-seat.acting .pk-ring .arc');
      if (arc) {
        const frac = left == null || !total ? 1 : Math.max(0, Math.min(1, left / total));
        arc.style.strokeDashoffset = String(100 * (1 - frac));
        arc.classList.toggle('low', frac < 0.25);
      }
      if (t && left != null) t.classList.toggle('low', left < 8000);
      const nx = h.nextAt && h.street === 'ended' ? Math.max(0, Math.ceil((h.nextAt - now()) / 1000)) : null;
      const n1 = $('#pk-next'), n2 = $('#pk-next-bar');
      if (n1) n1.textContent = nx == null ? '' : `Next hand in ${nx}s`;
      if (n2) n2.textContent = nx == null ? 'Next hand coming up.' : `Next hand in ${nx}s`;
    }

    // ------------------------------------------------------------------ render
    function render() {
      if (dead) return;
      if (!V) {
        $('#pk-head').innerHTML = '';
        $('#pk-main').innerHTML = emptyState(wasIn
          ? { art: 'poker', tone: 'verm', kicker: 'Out of the game', title: 'You are not at this table any more.', text: 'You left, the host removed you, or you sat out too many turns in a row. Real money went back to your cash.', actions: '<a class="btn btn-primary" href="#/poker">Back to the poker room</a>' }
          : { art: 'poker', tone: 'verm', kicker: 'Table closed', title: 'That table is gone.', text: 'Everybody left, or the host sent them home. Real money went back to cash.', actions: '<a class="btn btn-primary" href="#/poker">Back to the poker room</a>' });
        lastStatus = null;
        return;
      }
      $('#pk-head').innerHTML = head();
      const rebuild = lastStatus !== V.status || !$('#pk-main').firstElementChild || $('#pk-main').firstElementChild.classList.contains('empty');
      lastStatus = V.status;
      if (V.status === 'setup') renderSetup(rebuild || !$('#pk-seatbox')); else renderPlaying(rebuild || !$('#pk-felt'));
    }

    // ------------------------------------------------------------------ events
    root.addEventListener('click', async (e) => {
      const t = e.target;
      if (t.closest('#pk-copy')) { copyText(V.code); return; }
      if (t.closest('#pk-sit')) {
        const real = V.settings.money === 'real' && V.status === 'playing';
        if (real) {
          const ok = await new Promise((res) => {
            const m = modal(`<span class="lbl">Real cash</span><h2>Buy in for ${A(V.settings.stack)}?</h2><p class="lede">It comes out of your cash now and comes back when you leave.</p><div class="modal-actions"><button class="btn btn-secondary" data-no>Never mind</button><button class="btn btn-primary" data-yes>Buy in</button></div>`);
            m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); res(true); });
            m.el.querySelector('[data-no]').addEventListener('click', () => { m.close(); res(false); });
          });
          if (!ok) return;
        }
        if (busy) return; busy = true;
        try { const d = await post('/api/poker/join', { id, confirm: real }); if (d.user) setUser(d.user); take(d.table); } catch (ex) { toast(ex.message, 'err'); }
        busy = false; return;
      }
      if (t.closest('#pk-leave')) {
        const inHand = V.hand && V.hand.street !== 'ended' && me() && (me().status === 'in' || me().status === 'allin');
        const go2 = async () => { const d = await call('leave', {}); if (d && d.left) go('#/poker'); else if (d) toast('You will leave when this hand ends.', 'ok'); };
        if (inHand) {
          const m = modal(`<span class="lbl">Mid-hand</span><h2>Leave now?</h2><p class="lede">You fold this hand and leave when it ends. ${V.settings.money === 'real' ? 'Your stack goes back to your cash.' : ''}</p><div class="modal-actions"><button class="btn btn-secondary" data-close>Stay</button><button class="btn btn-danger" data-yes>Fold and leave</button></div>`);
          m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); go2(); });
        } else go2();
        return;
      }
      if (t.closest('#pk-end')) {
        const m = modal(`<span class="lbl">Host</span><h2>End the game?</h2><p class="lede">After this hand everybody cashes out and the table goes back to the settings. ${V.settings.money === 'real' ? 'Real money returns to each player\'s cash.' : ''}</p><div class="modal-actions"><button class="btn btn-secondary" data-close>Keep playing</button><button class="btn btn-danger" data-yes>End the game</button></div>`);
        m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); call('end', {}, 'The game ends after this hand.'); });
        return;
      }
      const kick = t.closest('[data-kick]'); if (kick) { call('kick', { userId: kick.dataset.kick }); return; }
      if (t.closest('#pk-yes')) { call('vote', { accept: true }); return; }
      if (t.closest('#pk-no')) { call('vote', { accept: false }); return; }
      if (t.closest('#pk-start')) { call('start', {}); return; }
      if (t.closest('#pk-rebuy')) { call('rebuy', {}, 'Rebought.'); return; }
      if (t.closest('#pk-save')) {
        const err = $('#pk-set-err'); if (err) err.textContent = '';
        const d = await call('settings', draftPayload(), null);
        if (!d && err) { try { await load(); } catch { /* ignore */ } }
        return;
      }
      const mbtn = t.closest('#pk-money [data-m]');
      if (mbtn && draft) {
        const m = mbtn.dataset.m; if (m === draft.money) return;
        draft.money = m; Object.assign(draft, DEFAULTS[m]);
        if (m === 'real' && Number(draft.turnSeconds) === 0) draft.turnSeconds = 45;
        $('#pk-setbox').innerHTML = settingsHost(); return;
      }
      const act = t.closest('[data-a]');
      if (act) { raiseOpen = false; pre = null; call('action', { action: act.dataset.a }); return; }
      if (t.closest('[data-open-raise]')) { raiseOpen = true; refreshBar(); bringIntoView(); return; }
      if (t.closest('[data-close-raise]')) { raiseOpen = false; refreshBar(); return; }
      const pr = t.closest('[data-pre]');
      if (pr) { const k = pr.dataset.pre; pre = pre === k ? null : k; preBet = V.hand ? V.hand.currentBet : 0; refreshBar(); return; }
      const q = t.closest('[data-q]');
      if (q) { setRaise(Number(q.dataset.q)); return; }
      const step = t.closest('[data-step]');
      if (step) { const a = V.hand && V.hand.actions; if (a) setRaise((raiseTo === null ? a.minRaiseTo : raiseTo) + Number(step.dataset.step) * V.blinds.bb); return; }
      if (t.closest('#pk-log-toggle')) { logOpen = !logOpen; $('#pk-log').innerHTML = logBox(); return; }
      if (t.closest('#pk-raise')) {
        const a = V.hand && V.hand.actions; if (!a) return;
        const to = raiseTo; raiseTo = null; raiseOpen = false;
        call('action', { action: to >= a.maxRaiseTo ? 'allin' : 'raise', amount: to });
      }
    });
    function setRaise(units) {
      const a = V.hand && V.hand.actions; if (!a) return;
      raiseTo = Math.max(a.minRaiseTo, Math.min(a.maxRaiseTo, Math.round(units)));
      const s = $('#pk-slide'), i = $('#pk-amt'), l = $('#pk-raise-amt');
      if (s) s.value = raiseTo; if (i) i.value = field(raiseTo, V.scale); if (l) l.textContent = A(raiseTo);
    }
    root.addEventListener('input', (e) => {
      const el = e.target;
      if (el.id === 'pk-slide') { setRaise(Number(el.value)); return; }
      if (el.id === 'pk-amt') {
        const v = parseFloat(el.value); const a = V.hand && V.hand.actions; if (!a || !Number.isFinite(v)) return;
        raiseTo = Math.max(a.minRaiseTo, Math.min(a.maxRaiseTo, Math.round(v * V.scale)));
        const s = $('#pk-slide'), l = $('#pk-raise-amt'); if (s) s.value = raiseTo; if (l) l.textContent = A(raiseTo); return;
      }
      if (draft && el.dataset && el.dataset.k) { draft[el.dataset.k] = el.value; refreshSaveBar(); }
    });
    root.addEventListener('change', (e) => {
      const el = e.target;
      if (el.id === 'pk-rebuy' && draft) { draft.rebuy = el.checked; refreshSaveBar(); return; }
      if (el.id === 'pk-amt') setRaise(Math.round((parseFloat(el.value) || 0) * V.scale));
      if (draft && el.dataset && el.dataset.k) { draft[el.dataset.k] = el.value; refreshSaveBar(); }
    });

    await load(true);
    const clock = setInterval(tickClock, 250);
    const poll = setInterval(() => { if (!document.hidden && V) load(); }, 4000);
    const onResize = debounce(() => { if (V && V.status === 'playing') render(); }, 150);
    window.addEventListener('resize', onResize);
    return {
      onEvent(ev) { if (ev.type === 'poker' && ev.id === id) reload(); },
      unmount() { dead = true; clearInterval(clock); clearInterval(poll); window.removeEventListener('resize', onResize); },
    };
  },
};
