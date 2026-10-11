import { get, post } from '../api.js';
import { go } from '../state.js';
import { esc, avatar, ago, debounce, ICON } from '../util.js';
import { toast, confirmBox } from '../ui.js';
import { emptyState } from './components.js';
import { refreshBadgesSoon } from '../social.js';
import { t, th, tp } from '../i18n.js';

/** Somebody's avatar with a little light on it: lime = here, grey ring = tab in the background, dark = gone. */
export const presenceAvatar = (f, size = 44) => `<span class="pres-av ${f.online ? (f.away ? 'away' : 'on') : 'off'}">${avatar(f.username, size)}<i class="pres-dot" aria-hidden="true"></i></span>`;
export const activityText = (f) => (f.online ? (f.away ? t('Ausente') : f.where || t('En línea')) : f.seen ? t('Visto {hace}', { hace: ago(f.seen) }) : t('Desconectado'));

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
        <span class="fr-tags">${f.circles.slice(0, 2).map((c) => `<span class="tag">${ICON.users} ${esc(c)}</span>`).join('')}${f.circles.length > 2 ? `<span class="tag">+${f.circles.length - 2}</span>` : ''}${f.added ? `<span class="tag res">${t('Amigo')}</span>` : ''}</span></div>
      <div class="fr-btns"><button class="btn btn-secondary btn-sm" data-msg="${f.id}">${ICON.chat} ${t('Mensaje')}</button>
        ${f.added ? `<button class="icon-btn" data-remove="${f.id}" data-name="${esc(f.username)}" title="${esc(t('Quitar a {nombre}', { nombre: f.username }))}" aria-label="${esc(t('Quitar a {nombre}', { nombre: f.username }))}">${ICON.x}</button>` : ''}</div></div>`;

    const sugRow = (u) => `<div class="fr-sug"><span>${avatar(u.username, 28)} ${esc(u.username)}</span><button class="btn btn-secondary btn-sm" data-ask="${esc(u.username)}">${t('Agregar')}</button></div>`;
    const simple = (u, buttons) => `<div class="fr-row slim" data-id="${u.id}">${avatar(u.username, 36)}<div class="fr-who"><span class="fr-name">${esc(u.username)}</span></div><div class="fr-btns">${buttons}</div></div>`;

    function render() {
      const on = V.friends.filter((f) => f.online), off = V.friends.filter((f) => !f.online);
      const keep = { q: $('#fr-q') ? $('#fr-q').value : '', focus: document.activeElement && document.activeElement.id === 'fr-q' };
      $('#fr-body').innerHTML = `
        <div class="fr-head"><div><span class="kicker">${t('La banda')}</span><h1>${t('Amigos')}</h1>
          <div class="fr-count"><span class="tag ${V.online ? 'res' : ''}"><i class="pres-dot inline ${V.online ? 'on' : 'off'}"></i> ${t('{n} en línea', { n: V.online })}</span><span class="tag">${tp(V.friends.length, '{n} amigo', '{n} amigos')}</span></div></div>
          <label class="fr-hide" title="${esc(t('Tus amigos te ven desconectado y no saben qué estás haciendo'))}"><input type="checkbox" id="fr-hide" ${V.hide ? 'checked' : ''}><span>${t('Aparecer desconectado')}</span></label></div>
        <div class="fr-grid">
          <div class="fr-main">
            ${V.incoming.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">${t('Quieren ser tus amigos')}</span><span class="num muted">${V.incoming.length}</span></div>
              ${V.incoming.map((u) => simple(u, `<button class="btn btn-primary btn-sm" data-accept="${u.id}">${t('Aceptar')}</button><button class="btn btn-secondary btn-sm" data-decline="${u.id}">${t('Ahora no')}</button>`)).join('')}</section>` : ''}
            <section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">${t('En línea ahora')}</span><span class="num muted">${on.length}</span></div>
              ${on.length ? on.map(row).join('') : `<p class="fr-none">${t('No hay nadie por aquí ahorita.')}</p>`}</section>
            ${off.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">${t('Desconectados')}</span><span class="num muted">${off.length}</span></div>${off.map(row).join('')}</section>` : ''}
            ${V.friends.length ? '' : emptyState({ art: 'crown', tone: 'lime', kicker: t('Todavía sin amigos'), title: esc(t('Esto está muy tranquilo.')), text: esc(t('Todos con quienes compartes un círculo aparecen aquí solos. O agrega a alguien por su nombre de usuario.')), actions: `<a class="btn btn-primary" href="#/circles">${t('Busca un círculo')}</a>` })}
          </div>
          <aside class="fr-side">
            <section class="card-box paper fr-panel fr-add"><span class="kicker">${t('Agregar a un amigo')}</span>
              <form id="fr-form" autocomplete="off"><div class="field"><label for="fr-q">${t('Nombre de usuario')}</label>
                <div class="fr-addrow"><input class="input" id="fr-q" maxlength="20" placeholder="${esc(t('empieza a escribir un nombre'))}" autocomplete="off" value="${esc(keep.q)}"><button class="btn btn-primary">${t('Mandar solicitud')}</button></div></div></form>
              <div class="fr-suggest" id="fr-suggest">${suggest.map(sugRow).join('')}</div>
              <small>${t('Los de tus círculos ya son tus amigos. Los demás tienen que decir que sí primero.')}</small></section>
            ${V.outgoing.length ? `<section class="card-box fr-panel"><div class="fr-ph"><span class="kicker">${t('Esperando respuesta')}</span></div>
              ${V.outgoing.map((u) => simple(u, `<button class="btn btn-secondary btn-sm" data-cancel="${u.id}">${t('Cancelar')}</button>`)).join('')}</section>` : ''}
          </aside>
        </div>`;
      if (keep.focus) { const q = $('#fr-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    }

    async function act(path, body, okMsg) {
      if (busy) return null; busy = true;
      try { V = { ...V, ...(await post(path, body)) }; if (okMsg) toast(okMsg(V), 'ok'); render(); refreshBadgesSoon(); return V; }
      catch (ex) { toast(ex.message, 'err'); return null; } finally { busy = false; }
    }

    const asked = (v, name) => (v.outcome === 'friends' ? t('{nombre} y tú ya son amigos.', { nombre: name }) : t('Le pediste a {nombre}. Tiene que decir que sí.', { nombre: name }));

    const search = debounce(async () => {
      const q = ($('#fr-q') || {}).value || '';
      if (q.trim().length < 2) { suggest = []; const box = $('#fr-suggest'); if (box) box.innerHTML = ''; return; }
      try { suggest = (await get('/api/friends/search?q=' + encodeURIComponent(q.trim()))).users; } catch { suggest = []; }
      const box = $('#fr-suggest');
      if (box) box.innerHTML = suggest.map(sugRow).join('');
    }, 220);

    root.addEventListener('input', (e) => { if (e.target.id === 'fr-q') search(); });
    root.addEventListener('change', (e) => { if (e.target.id === 'fr-hide') act('/api/friends/hide', { hide: e.target.checked }, () => (e.target.checked ? t('Ahora todos te ven desconectado.') : t('Tus amigos ya te pueden ver otra vez.'))); });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'fr-form') return;
      e.preventDefault();
      const name = $('#fr-q').value.trim(); if (!name) return;
      const d = await act('/api/friends/request', { username: name }, (v) => asked(v, name));
      if (d) { suggest = []; $('#fr-q').value = ''; const box = $('#fr-suggest'); if (box) box.innerHTML = ''; }
    });
    root.addEventListener('click', async (e) => {
      const el = e.target;
      const ask = el.closest('[data-ask]'); if (ask) { const n = ask.dataset.ask; await act('/api/friends/request', { username: n }, (v) => asked(v, n)); suggest = suggest.filter((u) => u.username !== n); render(); return; }
      const acc = el.closest('[data-accept]'); if (acc) { act('/api/friends/accept', { userId: acc.dataset.accept }, () => t('Ya son amigos.')); return; }
      const dec = el.closest('[data-decline]'); if (dec) { act('/api/friends/decline', { userId: dec.dataset.decline }); return; }
      const can = el.closest('[data-cancel]'); if (can) { act('/api/friends/cancel', { userId: can.dataset.cancel }); return; }
      const rem = el.closest('[data-remove]');
      if (rem) {
        if (await confirmBox({ title: t('¿Quitar a {nombre}?', { nombre: rem.dataset.name }), text: t('Dejan de ser amigos. Si comparten un círculo se van a seguir viendo aquí.'), confirm: t('Quitar'), danger: true })) act('/api/friends/remove', { userId: rem.dataset.remove });
        return;
      }
      const msg = el.closest('[data-msg]');
      if (msg) { try { const d = await post('/api/chats/dm', { userId: msg.dataset.msg }); go('#/chat/' + d.chat.id); } catch (ex) { toast(ex.message, 'err'); } }
    });

    await load();
    const poll = setInterval(() => { if (!document.hidden) load(); }, 20000);          // "last seen 5m ago" ages, and a missed event heals
    return { onEvent(ev) { if (ev.type === 'friends' || ev.type === 'presence') reload(); }, unmount() { dead = true; clearInterval(poll); } };
  },
};
