import { get, post } from '../api.js';
import { S } from '../state.js';
import { esc, avatar, ICON, debounce, circleMark } from '../util.js';
import { loadDraft, saveDraft, clearDraft } from '../viewstate.js';
import { toast, modal, confirmBox } from '../ui.js';
import { social, setUnread, refreshBadgesSoon } from '../social.js';
import { presenceAvatar, activityText } from './friends.js';

const hm = (t) => new Date(t).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
const sameDay = (a, b) => new Date(a).toDateString() === new Date(b).toDateString();
function dayLabel(t) {
  const now = Date.now();
  if (sameDay(t, now)) return 'Today';
  if (sameDay(t, now - 86400000)) return 'Yesterday';
  return new Date(t).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
}
const stamp = (t) => (sameDay(t, Date.now()) ? hm(t) : new Date(t).toLocaleDateString([], { month: 'short', day: 'numeric' }));
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
      el.innerHTML = `<div class="ch-list-head"><h2>Chats</h2><span class="ch-list-btns"><button class="icon-btn" id="ch-settings" title="Chat settings" aria-label="Chat settings">${ICON.gear}</button><button class="btn btn-primary btn-sm" id="ch-new">${ICON.plus} New</button></span></div>
        <div class="ch-items">${list.map((c) => `<button class="ch-item ${c.id === currentId ? 'on' : ''}" data-id="${c.id}">${listIcon(c)}
          <span class="ch-txt"><b class="ellipsis">${esc(c.name)}</b><small class="ellipsis">${c.last ? `${c.last.name && c.kind !== 'dm' ? esc(c.last.name) + ': ' : ''}${esc(c.last.x)}` : c.kind === 'global' ? 'Say hi to the whole site' : 'No messages yet'}</small></span>
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
      if (cur.kind === 'global') sub = 'Everybody on Clique';
      else if (cur.kind === 'circle') sub = `${Number(cur.members)} members · <a href="#/circle/${esc(cur.circleId)}">open the circle</a>`;
      else if (cur.kind === 'group') sub = `${Number(cur.members)} people`;
      else { const f = friendMap.get(cur.with); sub = f ? esc(activityText(f)) : 'Not friends any more'; }
      const icon = cur.kind === 'global' ? `<span class="ch-ico globe">${ICON.globe}</span>` : cur.kind === 'circle' ? circleMark({ emoji: cur.emoji, name: cur.name, id: cur.circleId }, 40)
        : cur.kind === 'dm' ? presenceAvatar({ username: cur.name, ...(friendMap.get(cur.with) || {}) }, 40) : `<span class="ch-ico group">${ICON.users}</span>`;
      el.innerHTML = `<button class="icon-btn ch-back" id="ch-back" aria-label="Back to chats">${ICON.chevL}</button>${icon}
        <div class="ch-title"><h2 class="ellipsis">${cur.kind === 'dm' ? `<a href="#/u/${esc(cur.name)}">${esc(cur.name)}</a>` : esc(cur.name)}</h2><small class="${cur.kind === 'dm' && friendMap.get(cur.with)?.online ? 'live' : ''}">${sub}</small></div>
        ${cur.kind === 'group' ? `<button class="btn btn-secondary btn-sm" id="ch-group">${ICON.users} Group</button>` : ''}`;
    }
    // ---- read receipts: "Seen" under your last message in a private chat, little faces under the last message each person read elsewhere
    const seenAt = (t) => (sameDay(t, Date.now()) ? hm(t) : new Date(t).toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + hm(t));
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
      if (rcpt.dm && rcpt.dm.n === m.n) return `<div class="msg-seen ${rcpt.dm.seen ? 'on' : ''}">${rcpt.dm.seen ? 'Seen ' + esc(seenAt(rcpt.dm.seen)) : 'Sent'}</div>`;
      const who = rcpt.under.get(m.n);
      if (!who) return '';
      const names = who.map((r) => r.username).join(', ');
      return `<div class="msg-seenby" title="Seen by ${esc(names)}" aria-label="Seen by ${esc(names)}">${who.slice(0, 5).map((r) => `<span title="${esc(r.username)} · ${esc(seenAt(r.t))}">${avatar(r.username, 16)}</span>`).join('')}${who.length > 5 ? `<em>+${who.length - 5}</em>` : ''}</div>`;
    }
    function msgHtml(m, prev) {
      if (m.sys) return `<div class="msg-sys" data-n="${m.n}">${esc(m.x)}</div>`;
      const mine = m.u === S.user.id;
      const grouped = prev && !prev.sys && prev.u === m.u && m.t - prev.t < 300000 && sameDay(prev.t, m.t);
      const moderator = cur.kind === 'circle' && (S.myCircles.find((c) => c.id === cur.circleId) || {}).isOwner;
      return `<div class="msg ${mine ? 'mine' : 'theirs'} ${grouped ? 'cont' : ''}" data-n="${m.n}">
        ${mine ? '' : `<span class="msg-av" ${grouped ? '' : `data-person="${m.u}" data-pname="${esc(m.name)}" title="${esc(m.name)}"`}>${grouped ? '' : avatar(m.name, 32)}</span>`}
        <div class="msg-body">${!mine && !grouped && cur.kind !== 'dm' ? `<div class="msg-name" data-person="${m.u}" data-pname="${esc(m.name)}">${esc(m.name)}</div>` : ''}
          <div class="msg-bubble">${lines(m.x)}<time title="${esc(new Date(m.t).toLocaleString())}">${hm(m.t)}</time>${mine || moderator ? `<button class="msg-del" data-del="${m.n}" title="Delete this message" aria-label="Delete this message">${ICON.x}</button>` : ''}</div>${receiptHtml(m)}</div></div>`;
    }
    function renderMsgs() {
      const el = $('#ch-msgs'); if (!el) return;
      let html = more ? '<button class="ch-earlier" id="ch-earlier">Load earlier messages</button>' : '';
      rcpt = computeReceipts();
      msgs.forEach((m, i) => {
        const prev = msgs[i - 1];
        if (!prev || !sameDay(prev.t, m.t)) html += `<div class="msg-day"><span>${dayLabel(m.t)}</span></div>`;
        html += msgHtml(m, prev && sameDay(prev.t, m.t) ? prev : null);
      });
      if (!msgs.length) html += `<div class="ch-quiet">${cur.kind === 'global' ? 'Nobody has said anything yet. Be the first.' : 'No messages yet. Say something.'}</div>`;
      el.innerHTML = html;
    }
    const nearBottom = () => { const el = $('#ch-msgs'); return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 140; };
    const toBottom = () => { const el = $('#ch-msgs'); if (el) el.scrollTop = el.scrollHeight; };

    function renderMain() {
      $('#ch').classList.toggle('open', !!currentId);
      const main = $('#ch-main');
      if (!cur) { main.innerHTML = `<div class="ch-empty"><span class="ch-ico globe">${ICON.chat}</span><h3>Pick a chat</h3><p class="muted">Talk to the whole site, to a circle, or privately to your friends.</p></div>`; return; }
      main.innerHTML = `<div class="ch-head" id="ch-head"></div><div class="ch-msgs" id="ch-msgs" aria-live="polite"></div>
        ${cur.canSend ? `<form class="ch-send" id="ch-form"><textarea id="ch-in" rows="1" maxlength="500" placeholder="Message ${esc(cur.name)}" aria-label="Message"></textarea><button class="btn btn-primary" id="ch-go" disabled>Send</button></form>`
          : `<div class="ch-ro">You are not friends any more, so this chat is read-only. <a href="#/friends">Add them again</a> to keep talking.</div>`}`;
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
        $('#ch-main').innerHTML = `<div class="ch-empty"><span class="ch-ico globe">${ICON.chat}</span><h3>${ex.status === 404 ? 'That chat is not available.' : 'Could not open it.'}</h3><p class="muted">${esc(ex.message)}</p></div>`;
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
        if (ex.status === 404 && id === currentId) { toast('You are not in that chat any more.', ''); currentId = null; cur = null; social.openChat = null; history.replaceState(null, '', '#/chat'); renderMain(); }
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
      const m = modal(`<span class="lbl">Start talking</span><h2>New chat</h2><p class="lede">Pick one friend to message them, or two or more to make a group.</p>
        ${friends.length ? `<input class="input" id="nc-q" placeholder="Search your friends" autocomplete="off"><div class="nc-list" id="nc-list">${friends.map((f) => `<label class="nc-row" data-name="${esc(f.username.toLowerCase())}"><input type="checkbox" value="${f.id}"><span>${presenceAvatar(f, 32)}</span><b>${esc(f.username)}</b><small>${esc(activityText(f))}</small></label>`).join('')}</div>
          <div class="field hidden" id="nc-name-f"><label for="nc-name">Group name <span class="muted" style="font-weight:400">(optional)</span></label><input class="input" id="nc-name" maxlength="40" placeholder="Poker night"></div>`
          : `<p class="fr-none">You don't have friends to talk to yet. <a href="#/friends" id="nc-link">Add some</a>, or join a circle: everybody in it is your friend.</p>`}
        <div class="error-text" id="nc-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="nc-go" disabled>Start</button></div>`);
      const picked = () => [...m.el.querySelectorAll('#nc-list input:checked')].map((i) => i.value);
      const sync = () => {
        const n = picked().length, b = m.el.querySelector('#nc-go');
        b.disabled = n === 0; b.textContent = n < 2 ? 'Start chat' : `Start group (${n + 1})`;
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
      const m = modal(`<span class="lbl">Chat settings</span><h2>Read receipts</h2>
        <p class="lede">Let people see when you have read their messages: <b>Seen</b> in private chats, and little faces in groups and circles. It works both ways. If you turn it off, you stop seeing everybody else's too.</p>
        <label class="rr-switch"><input type="checkbox" id="rr-on" ${receiptsOn ? 'checked' : ''}><span>Read receipts</span></label>
        <div class="error-text" id="rr-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Done</button></div>`);
      m.el.querySelector('#rr-on').addEventListener('change', async (e) => {
        const box = e.target; box.disabled = true;
        try { const d = await post('/api/chats/receipts', { on: box.checked }); receiptsOn = d.receipts; if (cur) { cur.receipts = d.receipts; await refreshCurrent(); renderMsgs(); } toast(d.receipts ? 'Read receipts are on.' : 'Read receipts are off. You will not see others\' either.', 'ok'); }
        catch (ex) { box.checked = !box.checked; m.el.querySelector('#rr-err').textContent = ex.message; }
        box.disabled = false;
      });
    }

    async function groupSettings() {
      let friends = [];
      try { friends = (await get('/api/friends')).friends.filter((f) => !cur.people.some((p) => p.id === f.id)); } catch { /* the member list still works */ }
      const boss = cur.canManage;
      const m = modal(`<span class="lbl">Group</span><h2>${esc(cur.name)}</h2>
        <div class="gi-list">${cur.people.map((p) => `<div class="gi-row">${avatar(p.username, 32)}<b>${esc(p.username)}${p.id === S.user.id ? ' (you)' : ''}</b>${p.id === cur.owner ? '<span class="tag res">Host</span>' : ''}
          ${boss && p.id !== S.user.id ? `<button class="icon-btn" data-rm="${p.id}" title="Remove ${esc(p.username)}" aria-label="Remove ${esc(p.username)}">${ICON.x}</button>` : ''}</div>`).join('')}</div>
        ${boss ? `<div class="field"><label for="gi-name">Rename</label><div class="fr-addrow"><input class="input" id="gi-name" maxlength="40" value="${esc(cur.name)}"><button type="button" class="btn btn-secondary" id="gi-rename">Save</button></div></div>
          ${friends.length ? `<div class="field"><label>Add friends</label><div class="nc-list">${friends.map((f) => `<label class="nc-row"><input type="checkbox" value="${f.id}"><span>${avatar(f.username, 28)}</span><b>${esc(f.username)}</b></label>`).join('')}</div><button type="button" class="btn btn-secondary" id="gi-add" style="margin-top:8px">Add them</button></div>` : ''}` : ''}
        <div class="error-text" id="gi-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-danger" id="gi-leave">Leave group</button><button type="button" class="btn btn-secondary" data-close>Done</button></div>`);
      const run = async (fn) => { try { await fn(); m.close(); await refreshCurrent(); } catch (ex) { m.el.querySelector('#gi-err').textContent = ex.message; } };
      m.el.addEventListener('click', (e) => {
        const rm = e.target.closest('[data-rm]'); if (rm) return run(() => post(`/api/chats/${cur.id}/members`, { remove: rm.dataset.rm }));
        if (e.target.closest('#gi-rename')) return run(() => post(`/api/chats/${cur.id}/rename`, { name: m.el.querySelector('#gi-name').value }));
        if (e.target.closest('#gi-add')) return run(() => post(`/api/chats/${cur.id}/members`, { add: [...m.el.querySelectorAll('.nc-list input:checked')].map((i) => i.value) }));
        if (e.target.closest('#gi-leave')) {
          m.close();
          confirmBox({ title: 'Leave this group?', text: 'You stop getting its messages. Somebody has to add you back to come in again.', confirm: 'Leave', danger: true }).then(async (yes) => {
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
      const m = modal(`<div class="pc-top">${friend ? presenceAvatar(friend, 56) : avatar(name, 56)}<div><h2>${esc(name)}</h2><small>${friend ? esc(activityText(friend)) : incoming ? 'Wants to be your friend' : outgoing ? 'You asked. Waiting for a yes.' : 'Not your friend yet'}</small></div></div>
        <div class="error-text" id="pc-err" style="min-height:18px"></div>
        <div class="modal-actions" style="justify-content:flex-start"><a class="btn btn-secondary" href="#/u/${esc(name)}" id="pc-prof">Profile</a>
          ${friend ? '<button class="btn btn-primary" id="pc-msg">Message</button>' : incoming ? '<button class="btn btn-primary" id="pc-accept">Accept request</button>' : outgoing ? '<button class="btn btn-secondary" disabled>Request sent</button>' : '<button class="btn btn-primary" id="pc-add">Add friend</button>'}</div>`);
      const run = (fn) => async (e) => { e.currentTarget.disabled = true; try { await fn(); } catch (ex) { m.el.querySelector('#pc-err').textContent = ex.message; e.target.disabled = false; } };
      const on = (sel, fn) => { const b = m.el.querySelector(sel); if (b) b.addEventListener('click', run(fn)); };
      on('#pc-msg', async () => { const d = await post('/api/chats/dm', { userId: id }); m.close(); open(d.chat.id); });
      on('#pc-add', async () => { const d = await post('/api/friends/request', { username: name }); m.close(); toast(d.outcome === 'friends' ? `You and ${name} are friends.` : `Asked ${name}. They have to say yes.`, 'ok'); refreshBadgesSoon(); });
      on('#pc-accept', async () => { await post('/api/friends/accept', { userId: id }); m.close(); toast(`You and ${name} are friends now.`, 'ok'); loadFriends(); refreshBadgesSoon(); });
      m.el.querySelector('#pc-prof').addEventListener('click', () => m.close());
    }

    // ------------------------------------------------------------------ events
    root.addEventListener('click', async (e) => {
      const t = e.target;
      const person = t.closest('[data-person]'); if (person) { personCard(person.dataset.person, person.dataset.pname); return; }
      const item = t.closest('.ch-item'); if (item) { open(item.dataset.id); return; }
      if (t.closest('#ch-new')) { newChat(); return; }
      if (t.closest('#ch-settings')) { chatSettings(); return; }
      if (t.closest('#ch-back')) { currentId = null; cur = null; social.openChat = null; history.pushState(null, '', '#/chat'); $('#ch').classList.remove('open'); renderList(); return; }
      if (t.closest('#ch-group')) { groupSettings(); return; }
      if (t.closest('#ch-earlier')) {
        const el = $('#ch-msgs'), before = msgs[0].n, h0 = el.scrollHeight;
        try { const d = await get(`/api/chats/${currentId}?before=${before}`); msgs = d.messages.concat(msgs); more = d.more; renderMsgs(); el.scrollTop = el.scrollHeight - h0; } catch (ex) { toast(ex.message, 'err'); }
        return;
      }
      const del = t.closest('[data-del]');
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
