import { get, post, patch } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, money, avatar, ICON, dateShort, circleMark } from '../util.js';
import { titleHtml } from '../looks.js';
import { rankTag } from '../art.js';
import { voice } from '../voice.js';
import { recall, remember } from '../viewstate.js';
import { toast, copyText, confirmBox } from '../ui.js';
import { marketCard, wireCards, emptyState } from './components.js';
import { t, th, tp } from '../i18n.js';

export default {
  async mount(root, [id]) {
    const MEM = 'circle:' + id;
    let tab = ['markets', 'members', 'settings'].includes(recall(MEM).tab) ? recall(MEM).tab : 'markets', dead = false, D = null, MK = [];

    async function load() {
      const [d, m] = await Promise.all([get(`/api/circles/${id}`), get(`/api/markets?circle=${id}&status=open`)]);
      if (dead) return;
      D = d; MK = m.markets; draw();
    }

    function draw() {
      const c = D.circle;
      root.innerHTML = `<div class="page">
        <div class="row" style="gap:16px;align-items:flex-start;flex-wrap:wrap">
          ${circleMark(c, 72)}
          <div class="grow"><h1 class="page-title">${esc(c.name)}</h1>
            <div class="row" style="gap:8px;margin-top:6px;flex-wrap:wrap"><span class="tag">${c.visibility === 'public' ? ICON.globe + ' ' + t('Público') : ICON.lock + ' ' + t('Privado')}</span>
              <span class="mono muted" style="font-size:12px;letter-spacing:.05em;text-transform:uppercase">${tp(c.memberCount, '{n} miembro', '{n} miembros')} · ${th('lo administra {nombre}', { nombre: c.ownerName })}</span></div>
            ${c.description ? `<p class="muted" style="margin:8px 0 0">${esc(c.description)}</p>` : ''}</div>
          <div class="row" style="flex-wrap:wrap">
            ${c.isMember ? `<a class="btn btn-primary" href="#/create?circle=${c.id}">${ICON.plus} ${t('Proponer una apuesta')}</a><a class="btn btn-secondary" href="#/weekly/${c.id}">${ICON.cal} ${t('Semana')}</a>`
              : `<button class="btn btn-primary" id="join">${t('Sentarme')}</button>`}
            ${c.isMember && !c.isOwner ? `<button class="btn btn-ghost" id="leave">${t('Salirme')}</button>` : ''}</div></div>
        ${c.isMember ? `<div class="card-box pad row" style="margin-top:22px;gap:16px;flex-wrap:wrap"><span class="lbl">${t('Código de la puerta')}</span>
          <div class="code-box">${esc(c.inviteCode)}<button class="icon-btn" id="copy-code" title="${esc(t('Copiar'))}">${ICON.copy}</button></div>
          <span class="muted grow">${c.visibility === 'public' ? t('Pásaselo a tus amigos. Lo escriben en Círculos y ya están dentro (o te encuentran en la lista pública).') : t('Pásaselo a tus amigos. Lo escriben en Círculos y ya están dentro.')}</span>
          ${c.isOwner ? `<button class="btn btn-ghost btn-sm" id="regen">${t('Cambiar la chapa')}</button>` : ''}</div>` : ''}
        ${c.isMember ? '<div id="voice-card"></div>' : ''}
        <div class="tabs" id="ctabs">
          <button data-t="markets" class="${tab === 'markets' ? 'active' : ''}">${t('Apuestas abiertas ({n})', { n: MK.length })}</button>
          <button data-t="members" class="${tab === 'members' ? 'active' : ''}">${t('Posiciones')}</button>
          ${c.isOwner ? `<button data-t="settings" class="${tab === 'settings' ? 'active' : ''}">${t('Ajustes')}</button>` : ''}</div>
        <div id="ctab"></div></div>`;
      drawTab();
      drawVoice();
    }

    // The voice room of this circle: who is in it, and a button to join (never automatic: the browser asks for the microphone).
    let room = null;
    const people = () => (voice.inRoom(id) ? voice.state.people : room ? room.people : []);
    function drawVoice() {
      const box = root.querySelector('#voice-card'); if (!box) return;
      const st = voice.state, mine = voice.inRoom(id), elsewhere = st.status !== 'idle' && st.circleId && st.circleId !== id;
      const list = people(), full = room && room.full && !mine;
      const err = st.error && (st.circleId === id || !st.circleId) ? `<div class="vc-err" role="alert">${esc(t(st.error.message))}</div>` : '';
      box.innerHTML = `<div class="card-box pad vc"><div class="vc-head"><div><span class="lbl">${t('Sala de voz')}</span>
          <b>${list.length ? tp(list.length, '{n} en la sala', '{n} en la sala') : t('Nadie está hablando')}</b></div>
          <div class="vc-people">${list.map((p) => `<span class="vd-p ${voice.state.speaking[p.id] && mine ? 'speaking' : ''}" title="${esc(p.username)}">${avatar(p.username, 28)}<em>${esc(p.username)}</em></span>`).join('')}</div>
          ${mine ? `<button class="btn btn-secondary" id="vc-leave">${t('Salir de la llamada')}</button>`
            : `<button class="btn btn-primary" id="vc-join" ${full ? 'disabled' : ''}>${elsewhere ? t('Pasar mi llamada aquí') : full ? t('La sala está llena') : t('Entrar a la voz')}</button>`}</div>
        <p class="muted vc-note">${mine ? t('Estás en esta llamada. Sigue mientras recorres Clique: usa la barra de abajo para silenciarte, dejar de oír o salir.') : t('Entrar depende de ti. Tu navegador va a pedir permiso para usar el micrófono. La voz es solo para miembros de este círculo y nunca se graba nada.')}</p>${err}</div>`;
    }
    async function loadRoom() {
      try { const d = await get('/api/voice/rooms'); room = d.rooms.find((r) => r.circleId === id) || null; } catch { room = null; }
      drawVoice();
    }
    const unsub = voice.subscribe(() => drawVoice());

    function drawTab() {
      const box = root.querySelector('#ctab'), c = D.circle;
      if (tab === 'markets') {
        box.innerHTML = MK.length ? `<div class="slips">${MK.map((m) => marketCard(m)).join('')}</div>`
          : emptyState({ art: 'slip', tone: 'cream', kicker: t('Nada abierto'), title: esc(t('Mesa muerta.')), text: th('Nadie en {circulo} ha apostado nada. Qué decepción.', { circulo: c.name }), actions: c.isMember ? `<a class="btn btn-primary" href="#/create?circle=${c.id}">${ICON.plus} ${t('Proponer una apuesta')}</a>` : '' });
        wireCards(box);
      } else if (tab === 'members') {
        const rows = D.members;
        box.innerHTML = `<div class="card-box" style="max-width:720px"><div class="pad muted" style="padding-bottom:6px">${t('Ordenado por cómo va la semana: lo que tienes ahora menos lo que tenías al empezar, sin contar recargas. La peor semana se lleva el castigo.')} <a href="#/weekly/${c.id}">${t('Premios y reglas')}</a></div>
          ${rows.map((r, i) => `<div class="standing ${i === rows.length - 1 && rows.length > 1 && r.delta < rows[0].delta ? 'last' : ''}">
            <span class="rk">${r.position || i + 1}</span>${avatar(r.user.username, 36)}
            <div class="grow"><a href="#/u/${esc(r.user.username)}" style="font-weight:600">${esc(r.user.username)}</a>${rankTag(r.user.rank)}${r.isOwner ? ` <span class="tag res">${t('Dueño')}</span>` : ''}${titleHtml(r.user.username)}
              <div class="mono muted" style="font-size:11.5px;letter-spacing:.05em;text-transform:uppercase">${t('desde el {fecha}', { fecha: dateShort(r.joinedAt) })}</div></div>
            <div style="text-align:right"><b class="num ${r.delta >= 0 ? 'up' : 'down'}">${money(r.delta, { plus: true })}</b><div class="num muted" style="font-size:12.5px">${t('tiene {cantidad}', { cantidad: money(r.value) })}</div></div>
            ${c.isOwner && !r.isOwner ? `<button class="icon-btn" data-kick="${r.user.id}" data-name="${esc(r.user.username)}" title="${esc(t('Sacar'))}" aria-label="${esc(t('Sacar'))}">${ICON.x}</button>` : ''}</div>`).join('')}</div>`;
      } else if (tab === 'settings') {
        box.innerHTML = `<form class="card-box pad-lg stack" id="sform" style="max-width:560px">
          <div class="field" style="margin:0"><label>${t('Nombre')}</label><input class="input" id="s-name" value="${esc(c.name)}" maxlength="40"></div>
          <div class="field" style="margin:0"><label>${t('Descripción')}</label><input class="input" id="s-desc" value="${esc(c.description)}" maxlength="200"></div>
          <div class="field" style="margin:0"><label>${t('¿Quién puede entrar?')}</label><select class="select" id="s-vis"><option value="private" ${c.visibility === 'private' ? 'selected' : ''}>${t('Privado (solo con código)')}</option><option value="public" ${c.visibility === 'public' ? 'selected' : ''}>${t('Público (cualquiera lo encuentra y entra)')}</option></select></div>
          <div><button class="btn btn-primary">${t('Guardar')}</button></div></form>`;
      }
    }

    root.addEventListener('click', async (e) => {
      const btn = e.target.closest('button'); if (!btn) return;
      try {
        if (btn.id === 'vc-join') { btn.disabled = true; await voice.join({ id, name: D.circle.name }); drawVoice(); }
        else if (btn.id === 'vc-leave') { await voice.leave(); loadRoom(); }
        else if (btn.dataset.t) { tab = btn.dataset.t; remember(MEM, { tab }); root.querySelectorAll('#ctabs button').forEach((b) => b.classList.toggle('active', b === btn)); drawTab(); }
        else if (btn.id === 'join') { await post(`/api/circles/${id}/join`, {}); await loadCircles(); toast(t('Ya tienes lugar.'), 'ok'); load(); }
        else if (btn.id === 'leave') { if (await confirmBox({ title: t('¿Salirte de este círculo?'), text: t('Conservas tus apuestas abiertas, pero ya no verás los mercados nuevos de aquí.'), confirm: t('Salirme'), danger: true })) { await post(`/api/circles/${id}/leave`, {}); await loadCircles(); go('#/circles'); } }
        else if (btn.id === 'copy-code' || btn.closest('#copy-code')) copyText(D.circle.inviteCode);
        else if (btn.id === 'regen') { if (await confirmBox({ title: t('¿Generar un código nuevo?'), text: t('El código viejo deja de servir. Quienes ya están dentro se quedan.'), confirm: t('Código nuevo') })) { await post(`/api/circles/${id}/regen`, {}); load(); } }
        else if (btn.dataset.kick) { if (await confirmBox({ title: t('¿Sacar a {nombre}?', { nombre: btn.dataset.name }), text: t('Puede volver a entrar con el código, a menos que lo cambies.'), confirm: t('Sacar'), danger: true })) { await post(`/api/circles/${id}/kick`, { userId: btn.dataset.kick }); load(); } }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'sform') return; e.preventDefault();
      try { await patch(`/api/circles/${id}`, { name: root.querySelector('#s-name').value, description: root.querySelector('#s-desc').value, visibility: root.querySelector('#s-vis').value }); await loadCircles(); toast(t('Guardado'), 'ok'); load(); }
      catch (ex) { toast(ex.message, 'err'); }
    });
    await load();
    loadRoom();
    return { onEvent(ev) {
      if (ev.type === 'voice' && ev.k === 'room' && ev.room === id) { room = { circleId: id, people: ev.people, full: room ? room.full : false }; drawVoice(); }
      if ((ev.type === 'market' || ev.type === 'circle') && (ev.circleId === id || ev.id === id)) load().catch(() => {});
    }, unmount() { dead = true; unsub(); } };
  },
};
