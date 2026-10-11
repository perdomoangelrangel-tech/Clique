import { get, post } from '../api.js';
import { S } from '../state.js';
import { esc, avatar, ICON, debounce, circleMark } from '../util.js';
import { loadDraft, saveDraft, clearDraft } from '../viewstate.js';
import { toast, modal, confirmBox } from '../ui.js';
import { social, setUnread, refreshBadgesSoon } from '../social.js';
import { presenceAvatar, activityText } from './friends.js';
import { t, th, tp, intlLocale } from '../i18n.js';

const hm = (ts) => new Date(ts).toLocaleTimeString(intlLocale(), { hour: 'numeric', minute: '2-digit' });
const sameDay = (a, b) => new Date(a).toDateString() === new Date(b).toDateString();
function dayLabel(ts) {
  const now = Date.now();
  if (sameDay(ts, now)) return t('Hoy');
  if (sameDay(ts, now - 86400000)) return t('Ayer');
  return new Date(ts).toLocaleDateString(intlLocale(), { weekday: 'long', month: 'short', day: 'numeric' });
}
const shortDay = (ts) => new Date(ts).toLocaleDateString(intlLocale(), { month: 'short', day: 'numeric' });
const stamp = (ts) => (sameDay(ts, Date.now()) ? hm(ts) : shortDay(ts));
const lines = (text) => esc(text).replace(/\n/g, '<br>');

export default {
  async mount(root, [wanted]) {
    let list = [], cur = null, msgs = [], more = false, currentId = null, openSeq = 0, sending = false, dead = false;
    let friendMap = new Map(), receiptsOn = true, rcpt = { under: new Map(), dm: null };
    const wide = () => window.matchMedia('(min-width: 821px)').matches;

    root.innerHTML = `<div class="page ch-page"><div class="ch" id="ch">
      <aside class="ch-list" id="ch-list"></aside>
      <section class="ch-main" id="ch-main"></section></div></div>`;
    const $ = (s) => root.querySelector(s);

    // ------------------------------------------------------------------ the list on the left
    function listIcon(c) {
      if (c.kind === 'global') return `<span class="ch-ico globe">${ICON.globe}</span>`;
      if (c.kind === 'circle') return `<span class="ch-ico">${circleMark({ emoji: c.emoji, name: c.name, id: c.circleId }, 42)}</span>`;
      if (c.kind === 'dm') return `<span class="ch-ico">${presenceAvatar({ username: c.name, ...(friendMap.get(c.with) || {}) }, 42)}</span>`;
      return `<span class="ch-ico group">${ICON.users}</span>`;
    }
    function renderList() {
      const el = $('#ch-list'); if (!el) return;
      el.innerHTML = `<div class="ch-list-head"><h2>${t('Chats')}</h2><span class="ch-list-btns"><button class="icon-btn" id="ch-settings" title="${esc(t('Ajustes del chat'))}" aria-label="${esc(t('Ajustes del chat'))}">${ICON.gear}</button><button class="btn btn-primary btn-sm" id="ch-new">${ICON.plus} ${t('Nuevo')}</button></span></div>
        <div class="ch-items">${list.map((c) => `<button class="ch-item ${c.id === currentId ? 'on' : ''}" data-id="${c.id}">${listIcon(c)}
          <span class="ch-txt"><b class="ellipsis">${esc(c.name)}</b><small class="ellipsis">${c.last ? `${c.last.name && c.kind !== 'dm' ? esc(c.last.name) + ': ' : ''}${esc(c.last.x)}` : c.kind === 'global' ? t('Saluda a todo el sitio') : t('Todavía no hay mensajes')}</small></span>
          <span class="ch-side">${c.last ? `<time>${stamp(c.last.t)}</time>` : ''}${c.unread && c.id !== currentId ? `<i class="ch-badge">${c.unread > 99 ? '99+' : c.unread}</i>` : ''}</span></button>`).join('')}</div>`;
    }
    async function loadList() {
      try { const d = await get('/api/chats'); list = d.chats; receiptsOn = d.receipts; } catch { return; }
      if (dead) return;
      if (currentId && !list.some((c) => c.id === currentId) && cur) list = [{ id: cur.id, kind: cur.kind, name: cur.name, unread: 0, t: Date.now(), last: null, with: cur.with, emoji: cur.emoji, circleId: cur.circleId }, ...list];   // a brand new direct chat
      renderList();
    }
    const loadListSoon = debounce(loadList, 350);
    async function loadFriends() {
      try { friendMap = new Map((await get('/api/friends')).friends.map((f) => [f.id, f])); } catch { return; }
      if (dead) return;
      renderList(); if (cur) renderHead();
    }
    const loadFriendsSoon = debounce(loadFriends, 400);

    // ------------------------------------------------------------------ the conversation on the right
    function renderHead() {
      const el = $('#ch-head'); if (!el) return;
      let sub = '';
      if (cur.kind === 'global') sub = t('Todos en Clique');
      else if (cur.kind === 'circle') sub = `${tp(Number(cur.members), '{n} miembro', '{n} miembros')} · <a href="#/circle/${esc(cur.circleId)}">${t('abrir el círculo')}</a>`;
      else if (cur.kind === 'group') sub = tp(Number(cur.members), '{n} persona', '{n} personas');
      else { const f = friendMap.get(cur.with); sub = f ? esc(activityText(f)) : t('Ya no son amigos'); }
      const icon = cur.kind === 'global' ? `<span class="ch-ico globe">${ICON.globe}</span>` : cur.kind === 'circle' ? circleMark({ emoji: cur.emoji, name: cur.name, id: cur.circleId }, 40)
        : cur.kind === 'dm' ? presenceAvatar({ username: cur.name, ...(friendMap.get(cur.with) || {}) }, 40) : `<span class="ch-ico group">${ICON.users}</span>`;
      el.innerHTML = `<button class="icon-btn ch-back" id="ch-back" aria-label="${esc(t('Volver a los chats'))}">${ICON.chevL}</button>${icon}
        <div class="ch-title"><h2 class="ellipsis">${cur.kind === 'dm' ? `<a href="#/u/${esc(cur.name)}">${esc(cur.name)}</a>` : esc(cur.name)}</h2><small class="${cur.kind === 'dm' && friendMap.get(cur.with)?.online ? 'live' : ''}">${sub}</small></div>
        ${cur.kind === 'group' ? `<button class="btn btn-secondary btn-sm" id="ch-group">${ICON.users} ${t('Grupo')}</button>` : ''}`;
    }
    // ---- read receipts: "Seen" under your last message in a private chat, little faces under the last message each person read elsewhere
    const seenAt = (ts) => (sameDay(ts, Date.now()) ? hm(ts) : shortDay(ts) + ' ' + hm(ts));
    function computeReceipts() {
      const out = { under: new Map(), dm: null };
      if (!cur || cur.receipts === false || cur.kind === 'global') return out;
      const real = msgs.filter((m) => !m.sys);
      if (cur.kind === 'dm') {
        const mine = [...real].reverse().find((m) => m.u === S.user.id);
        if (mine) { const r = (cur.readers || []).find((x) => x.n >= mine.n); out.dm = { n: mine.n, seen: r ? r.t : null }; }
        return out;
      }
      for (const r of cur.readers || []) {
        const target = [...real].reverse().find((m) => m.n <= r.n && m.u !== r.id);
        if (!target) continue;
        if (!out.under.has(target.n)) out.under.set(target.n, []);
        out.under.get(target.n).push(r);
      }
      return out;
    }
    function receiptHtml(m) {
      if (rcpt.dm && rcpt.dm.n === m.n) return `<div class="msg-seen ${rcpt.dm.seen ? 'on' : ''}">${rcpt.dm.seen ? esc(t('Visto {cuando}', { cuando: seenAt(rcpt.dm.seen) })) : t('Enviado')}</div>`;
      const who = rcpt.under.get(m.n);
      if (!who) return '';
      const names = who.map((r) => r.username).join(', ');
      return `<div class="msg-seenby" title="${esc(t('Lo vio {nombres}', { nombres: names }))}" aria-label="${esc(t('Lo vio {nombres}', { nombres: names }))}">${who.slice(0, 5).map((r) => `<span title="${esc(r.username)} · ${esc(seenAt(r.t))}">${avatar(r.username, 16)}</span>`).join('')}${who.length > 5 ? `<em>+${who.length - 5}</em>` : ''}</div>`;
    }
    function msgHtml(m, prev) {
      if (m.sys) return `<div class="msg-sys" data-n="${m.n}">${esc(m.x)}</div>`;
      const mine = m.u === S.user.id;
      const grouped = prev && !prev.sys && prev.u === m.u && m.t - prev.t < 300000 && sameDay(prev.t, m.t);
      const moderator = cur.kind === 'circle' && (S.myCircles.find((c) => c.id === cur.circleId) || {}).isOwner;
      return `<div class="msg ${mine ? 'mine' : 'theirs'} ${grouped ? 'cont' : ''}" data-n="${m.n}">
        ${mine ? '' : `<span class="msg-av" ${grouped ? '' : `data-person="${m.u}" data-pname="${esc(m.name)}" title="${esc(m.name)}"`}>${grouped ? '' : avatar(m.name, 32)}</span>`}
        <div class="msg-body">${!mine && !grouped && cur.kind !== 'dm' ? `<div class="msg-name" data-person="${m.u}" data-pname="${esc(m.name)}">${esc(m.name)}</div>` : ''}
          <div class="msg-bubble">${lines(m.x)}<time title="${esc(new Date(m.t).toLocaleString(intlLocale()))}">${hm(m.t)}</time>${mine || moderator ? `<button class="msg-del" data-del="${m.n}" title="${esc(t('Borrar este mensaje'))}" aria-label="${esc(t('Borrar este mensaje'))}">${ICON.x}</button>` : ''}</div>${receiptHtml(m)}</div></div>`;
    }
    function renderMsgs() {
      const el = $('#ch-msgs'); if (!el) return;
      let html = more ? `<button class="ch-earlier" id="ch-earlier">${t('Cargar mensajes anteriores')}</button>` : '';
      rcpt = computeReceipts();
      msgs.forEach((m, i) => {
        const prev = msgs[i - 1];
        if (!prev || !sameDay(prev.t, m.t)) html += `<div class="msg-day"><span>${dayLabel(m.t)}</span></div>`;
        html += msgHtml(m, prev && sameDay(prev.t, m.t) ? prev : null);
      });
      if (!msgs.length) html += `<div class="ch-quiet">${cur.kind === 'global' ? t('Nadie ha dicho nada todavía. Sé el primero.') : t('Todavía no hay mensajes. Di algo.')}</div>`;
      el.innerHTML = html;
    }
    const nearBottom = () => { const el = $('#ch-msgs'); return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 140; };
    const toBottom = () => { const el = $('#ch-msgs'); if (el) el.scrollTop = el.scrollHeight; };

    function renderMain() {
      $('#ch').classList.toggle('open', !!currentId);
      const main = $('#ch-main');
      if (!cur) { main.innerHTML = `<div class="ch-empty"><span class="ch-ico globe">${ICON.chat}</span><h3>${t('Elige un chat')}</h3><p class="muted">${t('Habla con todo el sitio, con un círculo o en privado con tus amigos.')}</p></div>`; return; }
      main.innerHTML = `<div class="ch-head" id="ch-head"></div><div class="ch-msgs" id="ch-msgs" aria-live="polite"></div>
        ${cur.canSend ? `<form class="ch-send" id="ch-form"><textarea id="ch-in" rows="1" maxlength="500" placeholder="${esc(t('Mensaje para {nombre}', { nombre: cur.name }))}" aria-label="${esc(t('Mensaje'))}"></textarea><button class="btn btn-primary" id="ch-go" disabled>${t('Enviar')}</button></form>`
          : `<div class="ch-ro">${t('Ya no son amigos, así que este chat es solo para leer. <a href="#/friends">Agrégalo otra vez</a> para seguir hablando.')}</div>`}`;
      renderHead(); renderMsgs(); toBottom();
    }

    async function open(id, push = true) {
      const seq = ++openSeq;
      currentId = id; social.openChat = id;
      if (push && location.hash !== '#/chat/' + id) history.pushState(null, '', '#/chat/' + id);
      $('#ch').classList.add('open'); renderList();
      try {
        const d = await get('/api/chats/' + id);
        if (seq !== openSeq || dead) return;
        cur = d.chat; msgs = d.messages; more = d.more;
      } catch (ex) {
        if (seq !== openSeq || dead) return;
        cur = null; msgs = []; currentId = null; social.openChat = null;
        $('#ch').classList.remove('open');
        $('#ch-main').innerHTML = `<div class="ch-empty"><span class="ch-ico globe">${ICON.chat}</span><h3>${ex.status === 404 ? t('Ese chat no está disponible.') : t('No se pudo abrir.')}</h3><p class="muted">${esc(ex.message)}</p></div>`;
        return;
      }
      renderMain(); renderList(); markRead();
      const input = $('#ch-in');
      if (input) { const d = loadDraft('chat:' + currentId); if (d) { input.value = d; input.style.height = 'auto'; input.style.height = Math.min(140, input.scrollHeight) + 'px'; const g = $('#ch-go'); if (g) g.disabled = !d.trim(); } }      // what you were typing here
      if (input && wide()) input.focus();
    }

    const markRead = debounce(async () => {
      if (dead || document.hidden || !currentId || !msgs.length) return;
      const id = currentId;
      try { const d = await post(`/api/chats/${id}/read`, { upTo: msgs[msgs.length - 1].n }); setUnread(d.total); } catch { return; }
      const row = list.find((c) => c.id === id); if (row && row.unread) { row.unread = 0; renderList(); }
    }, 350);

    function addMsg(m) {
      if (msgs.some((x) => x.n === m.n)) return;
      const stick = nearBottom() || m.u === S.user.id;
      msgs.push(m); msgs.sort((a, b) => a.n - b.n);
      renderMsgs(); if (stick) toBottom();
    }

    async function refreshCurrent() {
      if (!currentId) return;
      const id = currentId, last = msgs.length ? msgs[msgs.length - 1].n : 0;
      try {
        const d = await get(`/api/chats/${id}?after=${last}`);
        if (dead || id !== currentId) return;
        cur = d.chat; receiptsOn = d.chat.receipts; d.messages.forEach(addMsg); renderHead(); renderMsgs();
        if (!!$('#ch-form') !== cur.canSend) renderMain();
      } catch (ex) {
        if (ex.status === 404 && id === currentId) { toast(t('Ya no estás en ese chat.'), ''); currentId = null; cur = null; social.openChat = null; history.replaceState(null, '', '#/chat'); renderMain(); }
      }
      loadListSoon();
    }

    async function send() {
      const input = $('#ch-in'); if (!input || sending) return;
      const text = input.value.trim(); if (!text) return;
      sending = true; $('#ch-go').disabled = true;
      try {
        const d = await post(`/api/chats/${currentId}/send`, { text });
        input.value = ''; input.style.height = ''; clearDraft('chat:' + currentId);
        addMsg(d.message); markRead(); loadListSoon();
      } catch (ex) { toast(ex.message, 'err'); }
      sending = false; const go2 = $('#ch-go'); if (go2) go2.disabled = !(($('#ch-in') || {}).value || '').trim();
      if ($('#ch-in')) $('#ch-in').focus();
    }

    // ------------------------------------------------------------------ new chat, group settings
    async function newChat() {
      let friends = [];
      try { friends = (await get('/api/friends')).friends; } catch (ex) { toast(ex.message, 'err'); return; }
      const m = modal(`<span class="lbl">${t('Empieza a platicar')}</span><h2>${t('Chat nuevo')}</h2><p class="lede">${t('Elige a un amigo para escribirle, o a dos o más para hacer un grupo.')}</p>
        ${friends.length ? `<input class="input" id="nc-q" placeholder="${esc(t('Busca entre tus amigos'))}" autocomplete="off"><div class="nc-list" id="nc-list">${friends.map((f) => `<label class="nc-row" data-name="${esc(f.username.toLowerCase())}"><input type="checkbox" value="${f.id}"><span>${presenceAvatar(f, 32)}</span><b>${esc(f.username)}</b><small>${esc(activityText(f))}</small></label>`).join('')}</div>
          <div class="field hidden" id="nc-name-f"><label for="nc-name">${t('Nombre del grupo')} <span class="muted" style="font-weight:400">${t('(opcional)')}</span></label><input class="input" id="nc-name" maxlength="40" placeholder="${esc(t('Noche de póker'))}"></div>`
          : `<p class="fr-none">${t('Todavía no tienes amigos con quién hablar. <a href="#/friends" id="nc-link">Agrega algunos</a>, o únete a un círculo: todos ahí son tus amigos.')}</p>`}
        <div class="error-text" id="nc-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn btn-primary" id="nc-go" disabled>${t('Empezar')}</button></div>`);
      const picked = () => [...m.el.querySelectorAll('#nc-list input:checked')].map((i) => i.value);
      const sync = () => {
        const n = picked().length, b = m.el.querySelector('#nc-go');
        b.disabled = n === 0; b.textContent = n < 2 ? t('Empezar chat') : t('Hacer grupo ({n})', { n: n + 1 });
        const nf = m.el.querySelector('#nc-name-f'); if (nf) nf.classList.toggle('hidden', n < 2);
      };
      m.el.addEventListener('change', sync);
      const q = m.el.querySelector('#nc-q');
      if (q) q.addEventListener('input', () => m.el.querySelectorAll('.nc-row').forEach((r) => r.classList.toggle('hidden', !r.dataset.name.includes(q.value.trim().toLowerCase()))));
      const link = m.el.querySelector('#nc-link'); if (link) link.addEventListener('click', () => m.close());
      m.el.querySelector('#nc-go').addEventListener('click', async (e) => {
        const ids = picked(), err = m.el.querySelector('#nc-err'); e.target.disabled = true; err.textContent = '';
        try {
          const d = ids.length === 1 ? await post('/api/chats/dm', { userId: ids[0] }) : await post('/api/chats/group', { name: (m.el.querySelector('#nc-name') || {}).value || '', members: ids });
          m.close(); await open(d.chat.id); loadListSoon();
        } catch (ex) { err.textContent = ex.message; e.target.disabled = false; }
      });
    }

    function chatSettings() {
      const m = modal(`<span class="lbl">${t('Ajustes del chat')}</span><h2>${t('Avisos de leído')}</h2>
        <p class="lede">${t('Deja que vean cuándo leíste sus mensajes: <b>Visto</b> en los chats privados y caritas en grupos y círculos. Funciona en los dos sentidos: si lo apagas, tú tampoco ves los de los demás.')}</p>
        <label class="rr-switch"><input type="checkbox" id="rr-on" ${receiptsOn ? 'checked' : ''}><span>${t('Avisos de leído')}</span></label>
        <div class="error-text" id="rr-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Listo')}</button></div>`);
      m.el.querySelector('#rr-on').addEventListener('change', async (e) => {
        const box = e.target; box.disabled = true;
        try { const d = await post('/api/chats/receipts', { on: box.checked }); receiptsOn = d.receipts; if (cur) { cur.receipts = d.receipts; await refreshCurrent(); renderMsgs(); } toast(d.receipts ? t('Los avisos de leído están prendidos.') : t('Los avisos de leído están apagados. Tampoco vas a ver los de los demás.'), 'ok'); }
        catch (ex) { box.checked = !box.checked; m.el.querySelector('#rr-err').textContent = ex.message; }
        box.disabled = false;
      });
    }

    async function groupSettings() {
      let friends = [];
      try { friends = (await get('/api/friends')).friends.filter((f) => !cur.people.some((p) => p.id === f.id)); } catch { /* the member list still works */ }
      const boss = cur.canManage;
      const m = modal(`<span class="lbl">${t('Grupo')}</span><h2>${esc(cur.name)}</h2>
        <div class="gi-list">${cur.people.map((p) => `<div class="gi-row">${avatar(p.username, 32)}<b>${esc(p.username)}${p.id === S.user.id ? ' ' + esc(t('(tú)')) : ''}</b>${p.id === cur.owner ? `<span class="tag res">${t('Anfitrión')}</span>` : ''}
          ${boss && p.id !== S.user.id ? `<button class="icon-btn" data-rm="${p.id}" title="${esc(t('Quitar a {nombre}', { nombre: p.username }))}" aria-label="${esc(t('Quitar a {nombre}', { nombre: p.username }))}">${ICON.x}</button>` : ''}</div>`).join('')}</div>
        ${boss ? `<div class="field"><label for="gi-name">${t('Cambiar nombre')}</label><div class="fr-addrow"><input class="input" id="gi-name" maxlength="40" value="${esc(cur.name)}"><button type="button" class="btn btn-secondary" id="gi-rename">${t('Guardar')}</button></div></div>
          ${friends.length ? `<div class="field"><label>${t('Agregar amigos')}</label><div class="nc-list">${friends.map((f) => `<label class="nc-row"><input type="checkbox" value="${f.id}"><span>${avatar(f.username, 28)}</span><b>${esc(f.username)}</b></label>`).join('')}</div><button type="button" class="btn btn-secondary" id="gi-add" style="margin-top:8px">${t('Agregarlos')}</button></div>` : ''}` : ''}
        <div class="error-text" id="gi-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-danger" id="gi-leave">${t('Salirme del grupo')}</button><button type="button" class="btn btn-secondary" data-close>${t('Listo')}</button></div>`);
      const run = async (fn) => { try { await fn(); m.close(); await refreshCurrent(); } catch (ex) { m.el.querySelector('#gi-err').textContent = ex.message; } };
      m.el.addEventListener('click', (e) => {
        const rm = e.target.closest('[data-rm]'); if (rm) return run(() => post(`/api/chats/${cur.id}/members`, { remove: rm.dataset.rm }));
        if (e.target.closest('#gi-rename')) return run(() => post(`/api/chats/${cur.id}/rename`, { name: m.el.querySelector('#gi-name').value }));
        if (e.target.closest('#gi-add')) return run(() => post(`/api/chats/${cur.id}/members`, { add: [...m.el.querySelectorAll('.nc-list input:checked')].map((i) => i.value) }));
        if (e.target.closest('#gi-leave')) {
          m.close();
          confirmBox({ title: t('¿Salirte de este grupo?'), text: t('Dejas de recibir sus mensajes. Alguien tiene que agregarte otra vez para volver a entrar.'), confirm: t('Salirme'), danger: true }).then(async (yes) => {
            if (!yes) return;
            try { await post(`/api/chats/${cur.id}/leave`, {}); currentId = null; cur = null; social.openChat = null; history.replaceState(null, '', '#/chat'); renderMain(); renderList(); loadList(); } catch (ex) { toast(ex.message, 'err'); }
          });
        }
      });
    }

    /** Tap somebody's name: see how you stand with them and add them, message them or look at their profile. */
    async function personCard(id, name) {
      if (id === S.user.id) return;
      let v; try { v = await get('/api/friends'); } catch (ex) { toast(ex.message, 'err'); return; }
      const friend = v.friends.find((f) => f.id === id), incoming = v.incoming.some((u) => u.id === id), outgoing = v.outgoing.some((u) => u.id === id);
      const m = modal(`<div class="pc-top">${friend ? presenceAvatar(friend, 56) : avatar(name, 56)}<div><h2>${esc(name)}</h2><small>${friend ? esc(activityText(friend)) : incoming ? t('Quiere ser tu amigo') : outgoing ? t('Le pediste. Esperando el sí.') : t('Todavía no es tu amigo')}</small></div></div>
        <div class="error-text" id="pc-err" style="min-height:18px"></div>
        <div class="modal-actions" style="justify-content:flex-start"><a class="btn btn-secondary" href="#/u/${esc(name)}" id="pc-prof">${t('Perfil')}</a>
          ${friend ? `<button class="btn btn-primary" id="pc-msg">${t('Mensaje')}</button>` : incoming ? `<button class="btn btn-primary" id="pc-accept">${t('Aceptar solicitud')}</button>` : outgoing ? `<button class="btn btn-secondary" disabled>${t('Solicitud enviada')}</button>` : `<button class="btn btn-primary" id="pc-add">${t('Agregar amigo')}</button>`}</div>`);
      const run = (fn) => async (e) => { e.currentTarget.disabled = true; try { await fn(); } catch (ex) { m.el.querySelector('#pc-err').textContent = ex.message; e.target.disabled = false; } };
      const on = (sel, fn) => { const b = m.el.querySelector(sel); if (b) b.addEventListener('click', run(fn)); };
      on('#pc-msg', async () => { const d = await post('/api/chats/dm', { userId: id }); m.close(); open(d.chat.id); });
      on('#pc-add', async () => { const d = await post('/api/friends/request', { username: name }); m.close(); toast(d.outcome === 'friends' ? t('{nombre} y tú ya son amigos.', { nombre: name }) : t('Le pediste a {nombre}. Tiene que decir que sí.', { nombre: name }), 'ok'); refreshBadgesSoon(); });
      on('#pc-accept', async () => { await post('/api/friends/accept', { userId: id }); m.close(); toast(t('{nombre} y tú ya son amigos.', { nombre: name }), 'ok'); loadFriends(); refreshBadgesSoon(); });
      m.el.querySelector('#pc-prof').addEventListener('click', () => m.close());
    }

    // ------------------------------------------------------------------ events
    root.addEventListener('click', async (e) => {
      const tgt = e.target;
      const person = tgt.closest('[data-person]'); if (person) { personCard(person.dataset.person, person.dataset.pname); return; }
      const item = tgt.closest('.ch-item'); if (item) { open(item.dataset.id); return; }
      if (tgt.closest('#ch-new')) { newChat(); return; }
      if (tgt.closest('#ch-settings')) { chatSettings(); return; }
      if (tgt.closest('#ch-back')) { currentId = null; cur = null; social.openChat = null; history.pushState(null, '', '#/chat'); $('#ch').classList.remove('open'); renderList(); return; }
      if (tgt.closest('#ch-group')) { groupSettings(); return; }
      if (tgt.closest('#ch-earlier')) {
        const el = $('#ch-msgs'), before = msgs[0].n, h0 = el.scrollHeight;
        try { const d = await get(`/api/chats/${currentId}?before=${before}`); msgs = d.messages.concat(msgs); more = d.more; renderMsgs(); el.scrollTop = el.scrollHeight - h0; } catch (ex) { toast(ex.message, 'err'); }
        return;
      }
      const del = tgt.closest('[data-del]');
      if (del) { try { await post(`/api/chats/${currentId}/delete`, { n: Number(del.dataset.del) }); } catch (ex) { toast(ex.message, 'err'); } }
    });
    root.addEventListener('input', (e) => {
      if (e.target.id !== 'ch-in') return;
      e.target.style.height = 'auto'; e.target.style.height = Math.min(140, e.target.scrollHeight) + 'px';
      $('#ch-go').disabled = !e.target.value.trim();
      if (currentId) { if (e.target.value.trim()) saveDraft('chat:' + currentId, e.target.value); else clearDraft('chat:' + currentId); }
    });
    root.addEventListener('keydown', (e) => { if (e.target.id === 'ch-in' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    root.addEventListener('submit', (e) => { if (e.target.id === 'ch-form') { e.preventDefault(); send(); } });
    const onVisible = () => { if (!document.hidden) { markRead(); refreshCurrent(); } };
    document.addEventListener('visibilitychange', onVisible);

    // ------------------------------------------------------------------ go
    renderMain();
    await Promise.all([loadList(), loadFriends()]);
    if (wanted) await open(wanted, false);
    else if (wide()) {
      const first = list.find((c) => c.unread && c.kind !== 'global') || list.find((c) => c.id === 'global') || list[0];
      if (first) { history.replaceState(null, '', '#/chat/' + first.id); await open(first.id, false); }
    }
    const poll = setInterval(() => { if (!document.hidden) { loadFriends(); loadList(); } }, 30000);
    return {
      onEvent(ev) {
        if (ev.type === 'chat') {
          if (ev.id === currentId) {
            if (ev.del) { msgs = msgs.filter((m) => m.n !== ev.del); renderMsgs(); }
            else if (ev.msg) { addMsg(ev.msg); markRead(); }
          }
          loadListSoon();
        } else if (ev.type === 'seen') {
          if (ev.id === currentId && cur && cur.receipts !== false) {
            const mine = (cur.readers || []).find((r) => r.id === ev.u);
            if (mine) { mine.n = Math.max(mine.n, ev.n); mine.t = ev.t; } else (cur.readers = cur.readers || []).push({ id: ev.u, username: ev.name, n: ev.n, t: ev.t });
            const stick = nearBottom(); renderMsgs(); if (stick) toBottom();
          }
        } else if (ev.type === 'chats') { loadListSoon(); refreshCurrent(); refreshBadgesSoon(); }
        else if (ev.type === 'presence' || ev.type === 'friends') loadFriendsSoon();
      },
      unmount() { dead = true; social.openChat = null; clearInterval(poll); document.removeEventListener('visibilitychange', onVisible); },
    };
  },
};
