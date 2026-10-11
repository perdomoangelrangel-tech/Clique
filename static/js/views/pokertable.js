import { get, post } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, debounce, ICON, avatar } from '../util.js';
import { modal, toast, copyText } from '../ui.js';
import { suitSvg } from '../art.js';
import { burst } from '../games/common.js';
import { emptyState } from './components.js';
import { amt, field, blindsText, moneyTag } from './pokerfmt.js';
import { t, th, tp } from '../i18n.js';

const DEFAULTS = {
  fake: { bigBlind: '20', smallBlind: '10', stack: '1000', rebuy: true },
  real: { bigBlind: '1', smallBlind: '0.5', stack: '100', rebuy: false },
};
const TURN_LABELS = { 0: 'Sin reloj', 15: '15 segundos', 30: '30 segundos', 45: '45 segundos', 60: '1 minuto', 90: '90 segundos', 120: '2 minutos' };      // i18n: claves
const UP_LABELS = { 0: 'Nunca', 5: 'Cada 5 manos', 10: 'Cada 10 manos', 15: 'Cada 15 manos', 20: 'Cada 20 manos' };      // i18n: claves
const label = (labels, v) => (labels[v] ? t(labels[v]) : String(v));

/** "Ts" -> a paper card. "back" -> the striped back. size: 'l' (your hand), 'm' (board), 'r' (a revealed hand), 's' (a back). */
const card = (c, size = 's', fresh = false) => {
  const cls = `pk-pc ${size} ${fresh ? 'deal' : ''}`;
  if (!c || c === 'back') return `<div class="pc down ${cls}"><div class="pc-in"><div class="pc-front"></div><div class="pc-back"><span></span></div></div></div>`;
  const r = c[0] === 'T' ? '10' : c[0], su = c[1].toUpperCase(), red = su === 'H' || su === 'D';
  return `<div class="pc ${red ? 'red' : ''} ${cls}"><div class="pc-in"><div class="pc-front"><span class="tl">${r}${suitSvg(su, 18)}</span><span class="mid">${suitSvg(su, 40)}</span><span class="br">${r}${suitSvg(su, 18)}</span></div><div class="pc-back"><span></span></div></div></div>`;
};
const LAST = { check: 'Pasó', call: 'Igualó', bet: 'Apostó', raise: 'Subió' };      // i18n: claves

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
      return `<div class="pk-head ${V.status === 'playing' ? 'compact' : ''}"><div><span class="kicker">${V.visibility === 'private' ? t('Póker // mesa privada') : t('Póker // mesa pública')}</span>
          <h1>${esc(V.name)}</h1>
          <div class="pk-tags">${moneyTag(s.money)}<span class="tag">${V.visibility === 'private' ? `${ICON.lock} ${t('Solo con código')}` : `${ICON.globe} ${t('Pública')}`}</span>
            <span class="tag">${t('Ciegas')} <b class="num">${blindsText(V.blinds.sb, V.blinds.bb, V.scale)}</b></span>${V.status === 'playing' ? `<span class="tag">${t('Mano')} <b class="num">${V.handNo}</b></span>` : ''}
            ${V.ending ? `<span class="tag bad">${t('Termina después de esta mano')}</span>` : ''}</div></div>
        <div class="pk-head-btns">${V.code ? `<button class="btn btn-secondary btn-sm" id="pk-copy" title="${esc(t('Copiar el código de la mesa'))}">${t('Código')} <b class="num">${esc(V.code)}</b> ${ICON.copy}</button>` : ''}
          ${V.status === 'playing' && iAmHost() && !V.ending ? `<button class="btn btn-secondary btn-sm" id="pk-end">${t('Terminar el juego')}</button>` : ''}
          ${m ? `<button class="btn btn-danger btn-sm" id="pk-leave">${t('Levantarme')}</button>` : `<a class="btn btn-secondary btn-sm" href="#/poker">${t('Todas las mesas')}</a>`}</div></div>`;
    }

    // ------------------------------------------------------------------ setup phase
    function seatRows() {
      const accepted = V.seats.filter((s) => s && V.votes[s.userId] === true).length;
      const rows = V.seats.map((s, i) => {
        if (!s) return `<div class="pk-row vacant"><span class="pk-chair">${i + 1}</span><span>${t('Silla vacía')}</span></div>`;
        const v = V.votes[s.userId];
        const chip = v === true ? `<span class="pk-vote yes">${t('Listo')}</span>` : v === false ? `<span class="pk-vote no">${t('No aceptó')}</span>` : `<span class="pk-vote wait">${t('Pensándolo')}</span>`;
        return `<div class="pk-row ${s.isMe ? 'me' : ''}"><span class="pk-chair">${avatar(s.name, 30)}</span><div class="grow"><b>${esc(s.name)}</b>${s.isHost ? ` <span class="tag">${t('Anfitrión')}</span>` : ''}${s.isMe ? ` <span class="tag">${t('Tú')}</span>` : ''}</div>${chip}
          ${iAmHost() && !s.isMe ? `<button class="icon-btn" data-kick="${s.userId}" title="${esc(t('Sacar a {nombre}', { nombre: s.name }))}" aria-label="${esc(t('Sacar a {nombre}', { nombre: s.name }))}">${ICON.x}</button>` : ''}</div>`;
      }).join('');
      const watch = V.mySeat == null ? `<div class="pk-watch"><span>${t('Estás mirando.')}</span><button class="btn btn-primary btn-sm" id="pk-sit">${t('Sentarme')}</button></div>` : '';
      return `<div class="pk-panel-head"><div><span class="kicker">${t('La mesa')}</span><h2>${t('Quién está sentado')}</h2></div><span class="num pk-count">${seatedCount()} / ${V.settings.maxSeats}</span></div>${watch}
        <div class="pk-rows">${rows}</div>
        <p class="pk-note">${t('{n} de {total} aceptaron los ajustes. El anfitrión puede empezar cuando sean todos.', { n: accepted, total: seatedCount() })}</p>`;
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
      const opt = (arr, cur, labels) => arr.map((v) => `<option value="${v}" ${Number(cur) === v ? 'selected' : ''}>${esc(label(labels, v))}</option>`).join('');
      return `<div class="pk-panel-head"><div><span class="kicker">${t('Tú abriste la mesa')}</span><h2>${t('Ajustes de la mesa')}</h2></div></div>
        <div class="field"><label>${t('Fichas')}</label><div class="seg stretch" id="pk-money"><button type="button" data-m="fake" class="${!real ? 'active' : ''}">${t('Fichas de práctica')}</button><button type="button" data-m="real" class="${real ? 'active' : ''}">${t('Fichas de tu saldo')}</button></div>
          <small>${real ? t('Cada quien entra con fichas de su saldo semanal y le regresan al levantarse. Antes todos tienen que aceptar.') : t('Fichas de práctica, gratis para perder. Tu saldo nunca se toca.')}</small></div>
        <div class="pk-fields">
          <div class="field"><label for="pk-bb">${real ? t('Ciega grande ({signo})', { signo: '$' }) : t('Ciega grande (fichas)')}</label><input class="input num" id="pk-bb" data-k="bigBlind" inputmode="decimal" value="${esc(draft.bigBlind)}"></div>
          <div class="field"><label for="pk-sb">${t('Ciega chica')}</label><input class="input num" id="pk-sb" data-k="smallBlind" inputmode="decimal" value="${esc(draft.smallBlind)}"></div>
          <div class="field"><label for="pk-stack">${real ? t('Entrada ({signo})', { signo: '$' }) : t('Fichas iniciales')}</label><input class="input num" id="pk-stack" data-k="stack" inputmode="decimal" value="${esc(draft.stack)}"></div>
          <div class="field"><label for="pk-seats-sel">${t('Lugares')}</label><select class="select" id="pk-seats-sel" data-k="maxSeats">${opt([2, 3, 4, 5, 6, 7, 8, 9], draft.maxSeats, {})}</select></div>
          <div class="field"><label for="pk-turn">${t('Reloj por turno')}</label><select class="select" id="pk-turn" data-k="turnSeconds">${opt(turns, draft.turnSeconds, TURN_LABELS)}</select></div>
          <div class="field"><label for="pk-up">${t('Las ciegas se duplican')}</label><select class="select" id="pk-up" data-k="blindsUp">${opt([0, 5, 10, 15, 20], draft.blindsUp, UP_LABELS)}</select></div></div>
        <label class="pk-check"><input type="checkbox" id="pk-rebuy" ${draft.rebuy ? 'checked' : ''}><span>${t('Permitir volver a entrar cuando alguien se queda sin fichas')}</span></label>
        <div class="pk-save"><span class="${dirty() ? 'dirty' : ''}">${dirty() ? t('Cambios sin guardar. Al guardar, todos tienen que aceptar otra vez.') : t('Guardado.')}</span><button class="btn btn-primary" id="pk-save" ${dirty() ? '' : 'disabled'}>${t('Guardar ajustes')}</button></div>
        <div class="error-text" id="pk-set-err"></div>`;
    }
    function settingsView() {
      const s = V.settings, sc = V.scale, real = s.money === 'real';
      return `<div class="pk-panel-head"><div><span class="kicker">${th('Los propuso {nombre}', { nombre: V.hostName })}</span><h2>${t('Ajustes de la mesa')}</h2></div></div>
        <dl class="pk-dl"><div><dt>${t('Fichas')}</dt><dd>${real ? t('<b>De tu saldo</b> semanal') : t('<b>De práctica</b>, no cuentan')}</dd></div>
          <div><dt>${t('Ciegas')}</dt><dd class="num">${blindsText(s.smallBlind, s.bigBlind, sc)}</dd></div>
          <div><dt>${real ? t('Entrada') : t('Fichas iniciales')}</dt><dd class="num">${amt(s.stack, sc)}</dd></div>
          <div><dt>${t('Lugares')}</dt><dd class="num">${s.maxSeats}</dd></div><div><dt>${t('Reloj por turno')}</dt><dd>${esc(label(TURN_LABELS, s.turnSeconds))}</dd></div>
          <div><dt>${t('Las ciegas se duplican')}</dt><dd>${esc(label(UP_LABELS, s.blindsUp))}</dd></div><div><dt>${t('Volver a entrar')}</dt><dd>${s.rebuy ? t('Permitido') : t('No')}</dd></div></dl>
        ${real ? `<p class="pk-warn">${ICON.warn} ${t('Esta mesa usa fichas de tu saldo. Si aceptas, {cantidad} salen de tu cuenta cuando empiece el juego y regresan cuando te levantes.', { cantidad: amt(s.stack, sc) })}</p>` : ''}`;
    }

    function voteBar() {
      const m = me(), s = V.settings, real = s.money === 'real';
      const players = V.seats.filter(Boolean);
      const waiting = players.filter((p) => V.votes[p.userId] !== true).map((p) => p.name);
      const cash = S.user ? S.user.balance : 0, short = real && m && cash + 1e-9 < s.stack / 100;
      if (!m) return `<p class="pk-note">${t('Siéntate para votar los ajustes.')}</p>`;
      const mine = V.votes[m.userId];
      const voteBtns = iAmHost() ? '' : `<div class="pk-vote-btns"><button class="btn ${mine === true ? 'btn-primary' : 'btn-secondary'}" id="pk-yes" ${short ? 'disabled' : ''}>${mine === true ? t('Aceptado') : real ? t('Aceptar: entro con {cantidad}', { cantidad: A(s.stack) }) : t('Aceptar')}</button>
        <button class="btn ${mine === false ? 'btn-danger' : 'btn-secondary'}" id="pk-no">${mine === false ? t('No aceptado') : t('No acepto')}</button></div>`;
      const startBtn = iAmHost() ? `<button class="btn btn-primary btn-lg" id="pk-start" ${players.length >= 2 && !waiting.length ? '' : 'disabled'}>${t('Empezar el juego')}</button>` : '';
      const hint = iAmHost()
        ? (players.length < 2 ? esc(t('Necesitas al menos dos jugadores.')) : waiting.length ? th('Falta que acepten: {nombres}.', { nombres: waiting.join(', ') }) : esc(t('Todos están listos.')))
        : esc(mine === true ? t('Estás dentro. Esperando a que el anfitrión empiece.') : t('El anfitrión eligió estos ajustes. Tienes que aceptarlos antes de que empiece el juego.'));
      return `<div class="pk-startbar"><div class="pk-hint"><b>${hint}</b>${''/* html: seguro (hint se escapa al armarlo) */}${short ? `<br><span class="pk-warn-inline">${t('Solo tienes {saldo} en tu cuenta. La entrada es de {entrada}.', { saldo: amt(Math.round(cash * 100), 100), entrada: A(s.stack) })}</span>` : ''}${real && iAmHost() ? `<br><span class="pk-muted">${t('Tu saldo: {cantidad}', { cantidad: amt(Math.round(cash * 100), 100) })}</span>` : ''}</div>${voteBtns}${startBtn}</div>`;
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
      bar.querySelector('span').textContent = dirty() ? t('Cambios sin guardar. Al guardar, todos tienen que aceptar otra vez.') : t('Guardado.');
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
      if (s.busted) { tag = t('Sin fichas'); tagCls = 'fold'; }
      else if (s.leaving) { tag = t('Se va'); tagCls = 'fold'; }
      else if (!res && st === 'folded') { tag = t('Se retiró'); tagCls = 'fold'; }
      else if (!res && st === 'allin') { tag = t('Con todo'); tagCls = 'allin'; }
      else if (!res && s.last) { tag = LAST[s.last] ? t(LAST[s.last]) : s.last; tagCls = s.last; }
      else if (V.status === 'playing' && (!h || st === 'out')) { tag = t('Siguiente mano'); tagCls = 'wait'; }
      const w = won.get(i), handName = res && res.hands && res.hands[String(i)];
      const cards = s.cards, side = p.x < 50 || Math.abs(p.x - 50) < 10 ? 'r' : 'l';
      const deal = (size) => cards.map((c, k) => { const key = `${h ? h.no : 0}-s${i}-${k}-${c === 'back' ? 'b' : 'f'}`; const fresh = !seen.has(key); seen.add(key); return card(c, size, fresh && c !== 'back'); }).join('');
      let cardsHtml = '';
      if (cards && s.isMe) {
        const mine = h && h.mine;
        cardsHtml = `<div class="pk-hero">${deal('l')}</div>${mine ? `<div class="pk-hand"><b>${esc(mine.name)}</b>${mine.draws.length ? `<i>${esc(mine.draws.join(' · '))}</i>` : ''}</div>` : ''}`;
      } else if (cards) cardsHtml = `<div class="pk-backs ${side}">${deal(cards[0] === 'back' ? 's' : 'r')}</div>`;
      const toks = (h && h.button === i ? `<span class="pk-tok d" title="${esc(t('Botón del repartidor'))}">D</span>` : '')
        + (h && h.street !== 'ended' && h.sb === i ? '<span class="pk-tok">SB</span>' : '') + (h && h.street !== 'ended' && h.bb === i ? '<span class="pk-tok">BB</span>' : '');
      const ring = acting ? '<svg class="pk-ring" viewBox="0 0 100 100" aria-hidden="true"><circle class="trk" cx="50" cy="50" r="47"/><circle class="arc" cx="50" cy="50" r="47" pathLength="100"/></svg>' : '';
      return `<div class="pk-seat ${s.isMe ? 'hero' : ''} ${st} ${acting ? 'acting' : ''} ${w ? 'win' : ''}" style="${style}">
        <div class="pk-avwrap">${ring}<span class="pk-av">${avatar(s.name, 64)}</span>${cardsHtml}
          ${toks ? `<span class="pk-toks">${toks}</span>` : ''}
          ${w ? `<span class="pk-badge win num">+${A(w)}</span>` : tag ? `<span class="pk-badge ${tagCls}">${esc(tag)}</span>` : ''}</div>
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
      const potHtml = h && !res && h.pot > 0 ? `<div class="pk-pot" title="${esc(t('Todo lo que hay en medio, con las apuestas de esta ronda'))}"><i></i><b class="num">${A(h.pot)}</b></div>` : '';
      const centre = !h ? `<div class="pk-wait">${seatedCount() < 2 ? t('Esperando a otro jugador.') : t('Repartiendo la siguiente mano...')}</div>` : res ? resultBox(res) : '';
      return `<div class="pk-table ${real ? 'real' : ''}"><span class="pk-mark">${t('Póker Clique')}</span></div><div class="pk-board">${boardHtml}</div>${potHtml}${centre}${betHtml}${V.seats.map((s, i) => seatHtml(s, i, pos[i], h, res, won)).join('')}`;
    }

    function resultBox(res) {
      const lines = res.pots.map((p) => p.winners.map((w) => {
        const s = V.seats[w.seat]; const who = s ? s.name : t('Alguien');
        if (p.returned) return `<div class="pk-res-line dim">${th('A {nombre} le regresan {cantidad}', { nombre: who, cantidad: A(w.amount) })}</div>`;
        return `<div class="pk-res-line">${th('<b>{nombre}</b> gana <b class="num">{cantidad}</b>', { nombre: who, cantidad: A(w.amount) })}${w.hand ? ` <span>${esc(w.hand)}</span>` : res.reason === 'fold' ? ` <span>${t('todos los demás se retiraron')}</span>` : ''}</div>`;
      }).join('')).join('');
      return `<div class="pk-result">${lines}</div>`;
    }

    // ------------------------------------------------------------------ the buttons
    const toCallNow = () => { const m = me(), h = V.hand; return m && h ? Math.max(0, Math.min(h.currentBet - m.bet, m.stack)) : 0; };

    function actionBar() {
      const h = V.hand, m = me();
      if (!m) {
        const free = V.seats.some((s) => !s);
        return `<div class="pk-bar quiet">${free ? `<span>${t('Estás mirando esta mesa.')}</span><button class="btn btn-primary" id="pk-sit">${t('Sentarme')}</button>` : `<span>${t('Estás mirando. La mesa está llena.')}</span>`}</div>`;
      }
      if (m.busted) return `<div class="pk-bar quiet"><span>${t('Te quedaste sin fichas.')}</span>${V.settings.rebuy ? `<button class="btn btn-primary" id="pk-rebuy">${t('Volver a entrar con {cantidad}', { cantidad: A(V.settings.stack) })}</button>` : ''}</div>`;
      if (!h) return `<div class="pk-bar quiet"><span>${t('Esperando la siguiente mano.')}</span></div>`;
      if (h.street === 'ended') return `<div class="pk-bar quiet"><span id="pk-next-bar">${t('Ya viene la siguiente mano.')}</span></div>`;
      if (m.leaving) return `<div class="pk-bar quiet"><span>${t('Te levantas después de esta mano.')}</span></div>`;
      if (m.status === 'folded') return `<div class="pk-bar quiet"><span>${t('Te retiraste. Mira cómo sudan.')}</span></div>`;
      if (m.status === 'out') return `<div class="pk-bar quiet"><span>${t('Entras a partir de la siguiente mano.')}</span></div>`;
      const a = h.actions;
      if (!a) {
        const who = h.toAct != null && V.seats[h.toAct] ? V.seats[h.toAct].name : null;
        if (h.runout || m.status !== 'in') return `<div class="pk-bar quiet"><span>${h.runout ? t('Todos con todo. Ahí viene la mesa.') : who ? th('Esperando a <b>{nombre}</b>.', { nombre: who }) : t('Esperando...')}</span></div>`;
        const tc = toCallNow();                                    // pick your move before your turn comes
        return `<div class="pk-bar pre"><div class="pk-prehint">${who ? th('Esperando a <b>{nombre}</b>.', { nombre: who }) : t('Esperando...')} ${t('Elige tu jugada por adelantado:')}</div>
          <div class="pk-btnrow"><button class="pk-btn ${pre === 'cf' ? 'on' : ''}" data-pre="cf">${t('Pasar / Retirarme')}</button>
            <button class="pk-btn ${pre === 'cc' ? 'on' : ''}" data-pre="cc">${tc > 0 ? `${t('Igualar')} <b class="num">${A(tc)}</b>` : t('Pasar')}<small>${t('solo esta apuesta')}</small></button>
            <button class="pk-btn ${pre === 'ca' ? 'on' : ''}" data-pre="ca">${t('Igualar lo que sea')}<small>${t('cueste lo que cueste')}</small></button></div></div>`;
      }
      const mySeat = V.seats[V.mySeat], cb = a.currentBet, potAfter = h.pot + a.toCall;
      const clamp = (v) => Math.max(a.minRaiseTo, Math.min(a.maxRaiseTo, Math.round(v)));
      if (raiseTo === null || raiseTo < a.minRaiseTo || raiseTo > a.maxRaiseTo) raiseTo = a.minRaiseTo;
      const allInCall = a.toCall >= mySeat.stack;
      const callBtn = a.canCheck ? `<button class="pk-btn go" data-a="check">${t('Pasar')}</button>` : `<button class="pk-btn go" data-a="call">${t('Igualar')} <b class="num">${A(a.toCall)}</b>${allInCall ? `<small>${t('con todo')}</small>` : ''}</button>`;
      const isBet = cb === 0;
      const onlyAllIn = a.canRaise && a.minRaiseTo >= a.maxRaiseTo;
      let raiseBtn = '', panel = '';
      if (a.canRaise) {
        if (onlyAllIn) raiseBtn = `<button class="pk-btn raise confirm" data-a="allin">${t('Con todo')} <b class="num">${A(a.maxRaiseTo)}</b></button>`;
        else if (!raiseOpen) raiseBtn = `<button class="pk-btn raise" data-open-raise>${isBet ? t('Apostar...') : t('Subir...')}</button>`;
        else {
          raiseBtn = `<button class="pk-btn raise confirm" id="pk-raise">${isBet ? t('Apostar') : t('Subir a')} <b class="num" id="pk-raise-amt">${A(raiseTo)}</b></button>`;
          panel = `<div class="pk-rpanel"><div class="pk-quick"><button data-q="${a.minRaiseTo}">${t('Mín.')}</button><button data-q="${clamp(cb + 0.5 * potAfter)}">${t('½ bote')}</button><button data-q="${clamp(cb + 0.75 * potAfter)}">${t('¾ bote')}</button><button data-q="${clamp(cb + potAfter)}">${t('Bote')}</button><button data-q="${a.maxRaiseTo}">${t('Con todo')}</button></div>
            <div class="pk-rrow"><button class="pk-step" data-step="-1" aria-label="${esc(t('Menos'))}">−</button><input type="range" class="gm-range" id="pk-slide" min="${a.minRaiseTo}" max="${a.maxRaiseTo}" step="1" value="${raiseTo}" aria-label="${esc(t('Cantidad de la subida'))}"><button class="pk-step" data-step="1" aria-label="${esc(t('Más'))}">+</button>
              <input class="input num" id="pk-amt" inputmode="decimal" value="${field(raiseTo, V.scale)}" aria-label="${esc(t('Subir a'))}"></div>
            <button class="pk-cancel" data-close-raise>${t('Mejor no')}</button></div>`;
        }
      }
      return `<div class="pk-bar turn"><div class="pk-turnhead"><span class="lbl">${t('Tu turno')}</span><span class="pk-time num" id="pk-time"></span></div>${panel}
        <div class="pk-btnrow"><button class="pk-btn fold" data-a="fold">${t('Retirarme')}</button>${callBtn}${raiseBtn}</div></div>`;
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
      if (p === 'cc' && a.currentBet !== preBet) { toast(t('La apuesta cambió, así que te toca decidir.'), 'ok'); refreshBar(); return; }
      call('action', { action: p === 'cf' ? (a.canCheck ? 'check' : 'fold') : (a.canCheck ? 'check' : 'call') });
    }

    function logBox() {
      const lines = V.log.slice(logOpen ? -14 : -3).reverse();
      return `<div class="pk-log-head"><span class="lbl">${t('La acción')}</span><button class="pk-link" id="pk-log-toggle">${logOpen ? t('Ver menos') : t('Ver más')}</button></div>${lines.length ? lines.map((l, i) => `<div class="pk-logline ${i === 0 ? 'new' : ''}">${esc(l)}</div>`).join('') : `<div class="pk-logline">${t('Nada todavía.')}</div>`}`;
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
      const tm = $('#pk-time');
      if (tm) tm.textContent = left == null ? t('sin reloj') : t('{n} s', { n: Math.ceil(left / 1000) });
      const arc = root.querySelector('.pk-seat.acting .pk-ring .arc');
      if (arc) {
        const frac = left == null || !total ? 1 : Math.max(0, Math.min(1, left / total));
        arc.style.strokeDashoffset = String(100 * (1 - frac));
        arc.classList.toggle('low', frac < 0.25);
      }
      if (tm && left != null) tm.classList.toggle('low', left < 8000);
      const nx = h.nextAt && h.street === 'ended' ? Math.max(0, Math.ceil((h.nextAt - now()) / 1000)) : null;
      const n1 = $('#pk-next'), n2 = $('#pk-next-bar');
      if (n1) n1.textContent = nx == null ? '' : t('Siguiente mano en {n} s', { n: nx });
      if (n2) n2.textContent = nx == null ? t('Ya viene la siguiente mano.') : t('Siguiente mano en {n} s', { n: nx });
    }

    // ------------------------------------------------------------------ render
    function render() {
      if (dead) return;
      if (!V) {
        $('#pk-head').innerHTML = '';
        $('#pk-main').innerHTML = emptyState(wasIn
          ? { art: 'poker', tone: 'verm', kicker: t('Fuera del juego'), title: esc(t('Ya no estás en esta mesa.')), text: esc(t('Te levantaste, el anfitrión te sacó o te saltaste demasiados turnos seguidos. Las fichas de tu saldo regresaron a tu cuenta.')), actions: `<a class="btn btn-primary" href="#/poker">${t('Volver al salón de póker')}</a>` }
          : { art: 'poker', tone: 'verm', kicker: t('Mesa cerrada'), title: esc(t('Esa mesa ya no existe.')), text: esc(t('Todos se fueron, o el anfitrión los mandó a casa. Las fichas de cada saldo regresaron a su cuenta.')), actions: `<a class="btn btn-primary" href="#/poker">${t('Volver al salón de póker')}</a>` });
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
      const tg = e.target;
      if (tg.closest('#pk-copy')) { copyText(V.code); return; }
      if (tg.closest('#pk-sit')) {
        const real = V.settings.money === 'real' && V.status === 'playing';
        if (real) {
          const ok = await new Promise((res) => {
            const m = modal(`<span class="lbl">${t('Fichas de tu saldo')}</span><h2>${t('¿Entrar con {cantidad}?', { cantidad: A(V.settings.stack) })}</h2><p class="lede">${t('Sale de tu cuenta ahora y regresa cuando te levantes.')}</p><div class="modal-actions"><button class="btn btn-secondary" data-no>${t('Mejor no')}</button><button class="btn btn-primary" data-yes>${t('Entrar a la mesa')}</button></div>`);
            m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); res(true); });
            m.el.querySelector('[data-no]').addEventListener('click', () => { m.close(); res(false); });
          });
          if (!ok) return;
        }
        if (busy) return; busy = true;
        try { const d = await post('/api/poker/join', { id, confirm: real }); if (d.user) setUser(d.user); take(d.table); } catch (ex) { toast(ex.message, 'err'); }
        busy = false; return;
      }
      if (tg.closest('#pk-leave')) {
        const inHand = V.hand && V.hand.street !== 'ended' && me() && (me().status === 'in' || me().status === 'allin');
        const go2 = async () => { const d = await call('leave', {}); if (d && d.left) go('#/poker'); else if (d) toast(t('Te levantas cuando termine esta mano.'), 'ok'); };
        if (inHand) {
          const m = modal(`<span class="lbl">${t('A media mano')}</span><h2>${t('¿Levantarte ahora?')}</h2><p class="lede">${t('Te retiras de esta mano y te levantas cuando termine.')} ${V.settings.money === 'real' ? t('Tus fichas regresan a tu cuenta.') : ''}</p><div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Quedarme')}</button><button class="btn btn-danger" data-yes>${t('Retirarme y levantarme')}</button></div>`);
          m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); go2(); });
        } else go2();
        return;
      }
      if (tg.closest('#pk-end')) {
        const m = modal(`<span class="lbl">${t('Anfitrión')}</span><h2>${t('¿Terminar el juego?')}</h2><p class="lede">${t('Después de esta mano todos se llevan sus fichas y la mesa regresa a los ajustes.')} ${V.settings.money === 'real' ? t('Las fichas de cada saldo regresan a su cuenta.') : ''}</p><div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Seguir jugando')}</button><button class="btn btn-danger" data-yes>${t('Terminar el juego')}</button></div>`);
        m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); call('end', {}, t('El juego termina después de esta mano.')); });
        return;
      }
      const kick = tg.closest('[data-kick]'); if (kick) { call('kick', { userId: kick.dataset.kick }); return; }
      if (tg.closest('#pk-yes')) { call('vote', { accept: true }); return; }
      if (tg.closest('#pk-no')) { call('vote', { accept: false }); return; }
      if (tg.closest('#pk-start')) { call('start', {}); return; }
      if (tg.closest('#pk-rebuy')) { call('rebuy', {}, t('Volviste a entrar.')); return; }
      if (tg.closest('#pk-save')) {
        const err = $('#pk-set-err'); if (err) err.textContent = '';
        const d = await call('settings', draftPayload(), null);
        if (!d && err) { try { await load(); } catch { /* ignore */ } }
        return;
      }
      const mbtn = tg.closest('#pk-money [data-m]');
      if (mbtn && draft) {
        const m = mbtn.dataset.m; if (m === draft.money) return;
        draft.money = m; Object.assign(draft, DEFAULTS[m]);
        if (m === 'real' && Number(draft.turnSeconds) === 0) draft.turnSeconds = 45;
        $('#pk-setbox').innerHTML = settingsHost(); return;
      }
      const act = tg.closest('[data-a]');
      if (act) { raiseOpen = false; pre = null; call('action', { action: act.dataset.a }); return; }
      if (tg.closest('[data-open-raise]')) { raiseOpen = true; refreshBar(); bringIntoView(); return; }
      if (tg.closest('[data-close-raise]')) { raiseOpen = false; refreshBar(); return; }
      const pr = tg.closest('[data-pre]');
      if (pr) { const k = pr.dataset.pre; pre = pre === k ? null : k; preBet = V.hand ? V.hand.currentBet : 0; refreshBar(); return; }
      const q = tg.closest('[data-q]');
      if (q) { setRaise(Number(q.dataset.q)); return; }
      const step = tg.closest('[data-step]');
      if (step) { const a = V.hand && V.hand.actions; if (a) setRaise((raiseTo === null ? a.minRaiseTo : raiseTo) + Number(step.dataset.step) * V.blinds.bb); return; }
      if (tg.closest('#pk-log-toggle')) { logOpen = !logOpen; $('#pk-log').innerHTML = logBox(); return; }
      if (tg.closest('#pk-raise')) {
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
