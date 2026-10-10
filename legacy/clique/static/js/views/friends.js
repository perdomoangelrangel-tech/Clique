import { get, post } from '../api.js';
import { go } from '../state.js';
import { esc, avatar, ago, debounce, ICON } from '../util.js';
import { toast, confirmBox } from '../ui.js';
import { emptyState } from './components.js';
import { refreshBadgesSoon } from '../social.js';

/** Somebody's avatar with a little light on it: lime = here, grey ring = tab in the background, dark = gone. */
export const presenceAvatar = (f, size = 44) => `<span class="pres-av ${f.online ? (f.away ? 'away' : 'on') : 'off'}">${avatar(f.username, size)}<i class="pres-dot" aria-hidden="true"></i></span>`;
export const activityText = (f) => (f.online ? (f.away ? 'Away' : f.where || 'Online') : f.seen ? `Last seen ${ago(f.seen)}` : 'Offline');

export default {
  async mount(root) {
    let V = null, dead = false, busy = false, suggest = [];
    root.innerHTML = `<div class="page fr-page"><div id="fr-body"><div class="spinner"></div></div></div>`;
    const $ = (s) => root.querySelector(s);

    async function load() {
      try { V = await get('/api/friends'); } catch (ex) { if (!dead) $('#fr-body').innerHTML = `<p class="muted">${esc(ex.message)}</p>`; return; }
      if (!dead) render();
    }
    const reload = debounce(load, 250);

    const row = (f) => `<div class="fr-row ${f.online ? 'is-on' : ''}" data-id="${f.id}">
      ${presenceAvatar(f)}
      <div class="fr-who"><a class="fr-name" href="#/u/${esc(f.username)}">${esc(f.username)}</a>
        <span class="fr-act ${f.online && !f.away ? 'live' : ''}">${esc(activityText(f))}</span>
        <span class="fr-tags">${f.circles.slice(0, 2).map((c) => `<span class="tag">${ICON.users} ${esc(c)}</span>`).join('')}${f.circles.length > 2 ? `<span class="tag">+${f.circles.length - 2}</span>` : ''}${f.added ? '<span class="tag res">Friend</span>' : ''}</span></div>
      <div class="fr-btns"><button class="btn btn-secondary btn-sm" data-msg="${f.id}">${ICON.chat} Message</button>
        ${f.added ? `<button class="icon-btn" data-remove="${f.id}" data-name="${esc(f.username)}" title="Remove ${esc(f.username)}" aria-label="Remove ${esc(f.username)}">${ICON.x}</button>` : ''}</div></div>`;

    const simple = (u, buttons) => `<div class="fr-row slim" data-id="${u.id}">${avatar(u.username, 36)}<div class="fr-who"><span class="fr-name">${esc(u.username)}</span></div><div class="fr-btns">${buttons}</div></div>`;

    function render() {
      const on = V.friends.filter((f) => f.online), off = V.friends.filter((f) => !f.online);
      const keep = { q: $('#fr-q') ? $('#fr-q').value : '', focus: document.activeElement && document.activeElement.id === 'fr-q' };
      $('#fr-body').innerHTML = `
        <div class="fr-head"><div><span class="kicker">The crowd</span><h1>Friends</h1>
          <div class="fr-count"><span class="tag ${V.online ? 'res' : ''}"><i class="pres-dot inline ${V.online ? 'on' : 'off'}"></i> ${V.online} online</span><span class="tag">${V.friends.length} friend${V.friends.length === 1 ? '' : 's'}</span></div></div>
          <label class="fr-hide" title="Friends see you as offline and can't tell what you are doing"><input type="checkbox" id="fr-hide" ${V.hide ? 'checked' : ''}><span>Appear offline</span></label></div>
        <div class="fr-grid">
          <div class="fr-main">
            ${V.incoming.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">Wants to be friends</span><span class="num muted">${V.incoming.length}</span></div>
              ${V.incoming.map((u) => simple(u, `<button class="btn btn-primary btn-sm" data-accept="${u.id}">Accept</button><button class="btn btn-secondary btn-sm" data-decline="${u.id}">Not now</button>`)).join('')}</section>` : ''}
            <section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">Online now</span><span class="num muted">${on.length}</span></div>
              ${on.length ? on.map(row).join('') : '<p class="fr-none">Nobody is around right now.</p>'}</section>
            ${off.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">Offline</span><span class="num muted">${off.length}</span></div>${off.map(row).join('')}</section>` : ''}
            ${V.friends.length ? '' : emptyState({ art: 'crown', tone: 'lime', kicker: 'No friends yet', title: 'It is quiet in here.', text: 'Everybody you share a circle with shows up here by themselves. Or add somebody by username.', actions: '<a class="btn btn-primary" href="#/circles">Find a circle</a>' })}
          </div>
          <aside class="fr-side">
            <section class="card-box paper fr-panel fr-add"><span class="kicker">Add a friend</span>
              <form id="fr-form" autocomplete="off"><div class="field"><label for="fr-q">Username</label>
                <div class="fr-addrow"><input class="input" id="fr-q" maxlength="20" placeholder="start typing a name" autocomplete="off" value="${esc(keep.q)}"><button class="btn btn-primary">Ask</button></div></div></form>
              <div class="fr-suggest" id="fr-suggest">${suggest.map((u) => `<div class="fr-sug"><span>${avatar(u.username, 28)} ${esc(u.username)}</span><button class="btn btn-secondary btn-sm" data-ask="${esc(u.username)}">Add</button></div>`).join('')}</div>
              <small>People in your circles are already your friends. Everyone else has to say yes first.</small></section>
            ${V.outgoing.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">Waiting for an answer</span></div>
              ${V.outgoing.map((u) => simple(u, `<button class="btn btn-secondary btn-sm" data-cancel="${u.id}">Cancel</button>`)).join('')}</section>` : ''}
          </aside>
        </div>`;
      if (keep.focus) { const q = $('#fr-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    }

    async function act(path, body, okMsg) {
      if (busy) return null; busy = true;
      try { V = { ...V, ...(await post(path, body)) }; if (okMsg) toast(okMsg(V), 'ok'); render(); refreshBadgesSoon(); return V; }
      catch (ex) { toast(ex.message, 'err'); return null; } finally { busy = false; }
    }

    const search = debounce(async () => {
      const q = ($('#fr-q') || {}).value || '';
      if (q.trim().length < 2) { suggest = []; const box = $('#fr-suggest'); if (box) box.innerHTML = ''; return; }
      try { suggest = (await get('/api/friends/search?q=' + encodeURIComponent(q.trim()))).users; } catch { suggest = []; }
      const box = $('#fr-suggest');
      if (box) box.innerHTML = suggest.map((u) => `<div class="fr-sug"><span>${avatar(u.username, 28)} ${esc(u.username)}</span><button class="btn btn-secondary btn-sm" data-ask="${esc(u.username)}">Add</button></div>`).join('');
    }, 220);

    root.addEventListener('input', (e) => { if (e.target.id === 'fr-q') search(); });
    root.addEventListener('change', (e) => { if (e.target.id === 'fr-hide') act('/api/friends/hide', { hide: e.target.checked }, () => (e.target.checked ? 'You look offline to everyone now.' : 'Friends can see you again.')); });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'fr-form') return;
      e.preventDefault();
      const name = $('#fr-q').value.trim(); if (!name) return;
      const d = await act('/api/friends/request', { username: name }, (v) => (v.outcome === 'friends' ? `You and ${name} are friends.` : `Asked ${name}. They have to say yes.`));
      if (d) { suggest = []; $('#fr-q').value = ''; const box = $('#fr-suggest'); if (box) box.innerHTML = ''; }
    });
    root.addEventListener('click', async (e) => {
      const t = e.target;
      const ask = t.closest('[data-ask]'); if (ask) { const n = ask.dataset.ask; await act('/api/friends/request', { username: n }, (v) => (v.outcome === 'friends' ? `You and ${n} are friends.` : `Asked ${n}. They have to say yes.`)); suggest = suggest.filter((u) => u.username !== n); render(); return; }
      const acc = t.closest('[data-accept]'); if (acc) { act('/api/friends/accept', { userId: acc.dataset.accept }, () => 'You are friends now.'); return; }
      const dec = t.closest('[data-decline]'); if (dec) { act('/api/friends/decline', { userId: dec.dataset.decline }); return; }
      const can = t.closest('[data-cancel]'); if (can) { act('/api/friends/cancel', { userId: can.dataset.cancel }); return; }
      const rem = t.closest('[data-remove]');
      if (rem) {
        if (await confirmBox({ title: `Remove ${rem.dataset.name}?`, text: 'You stop being friends. If you share a circle you will still see each other here.', confirm: 'Remove', danger: true })) act('/api/friends/remove', { userId: rem.dataset.remove });
        return;
      }
      const msg = t.closest('[data-msg]');
      if (msg) { try { const d = await post('/api/chats/dm', { userId: msg.dataset.msg }); go('#/chat/' + d.chat.id); } catch (ex) { toast(ex.message, 'err'); } }
    });

    await load();
    const poll = setInterval(() => { if (!document.hidden) load(); }, 20000);          // "last seen 5m ago" ages, and a missed event heals
    return { onEvent(ev) { if (ev.type === 'friends' || ev.type === 'presence') reload(); }, unmount() { dead = true; clearInterval(poll); } };
  },
};
