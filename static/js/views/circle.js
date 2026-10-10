import { get, post, patch } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, money, avatar, ICON, dateShort, circleMark } from '../util.js';
import { titleHtml } from '../looks.js';
import { rankTag } from '../art.js';
import { voice } from '../voice.js';
import { recall, remember } from '../viewstate.js';
import { toast, copyText, confirmBox } from '../ui.js';
import { marketCard, wireCards, emptyState } from './components.js';

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
            <div class="row" style="gap:8px;margin-top:6px;flex-wrap:wrap"><span class="tag">${c.visibility === 'public' ? ICON.globe + ' Public' : ICON.lock + ' Private'}</span>
              <span class="mono muted" style="font-size:12px;letter-spacing:.05em;text-transform:uppercase">${c.memberCount} member${c.memberCount === 1 ? '' : 's'} · run by ${esc(c.ownerName)}</span></div>
            ${c.description ? `<p class="muted" style="margin:8px 0 0">${esc(c.description)}</p>` : ''}</div>
          <div class="row" style="flex-wrap:wrap">
            ${c.isMember ? `<a class="btn btn-primary" href="#/create?circle=${c.id}">${ICON.plus} Propose a bet</a><a class="btn btn-secondary" href="#/weekly/${c.id}">${ICON.cal} Weekly</a>`
              : `<button class="btn btn-primary" id="join">Take a seat</button>`}
            ${c.isMember && !c.isOwner ? '<button class="btn btn-ghost" id="leave">Leave</button>' : ''}</div></div>
        ${c.isMember ? `<div class="card-box pad row" style="margin-top:22px;gap:16px;flex-wrap:wrap"><span class="lbl">Door code</span>
          <div class="code-box">${esc(c.inviteCode)}<button class="icon-btn" id="copy-code" title="Copy">${ICON.copy}</button></div>
          <span class="muted grow">Hand it to friends. They type it under <b>Circles</b> and they're in${c.visibility === 'public' ? ' (or they just find you in the public list)' : ''}.</span>
          ${c.isOwner ? '<button class="btn btn-ghost btn-sm" id="regen">Change the locks</button>' : ''}</div>` : ''}
        ${c.isMember ? '<div id="voice-card"></div>' : ''}
        <div class="tabs" id="ctabs">
          <button data-t="markets" class="${tab === 'markets' ? 'active' : ''}">Open bets (${MK.length})</button>
          <button data-t="members" class="${tab === 'members' ? 'active' : ''}">Standings</button>
          ${c.isOwner ? `<button data-t="settings" class="${tab === 'settings' ? 'active' : ''}">Settings</button>` : ''}</div>
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
      const err = st.error && (st.circleId === id || !st.circleId) ? `<div class="vc-err" role="alert">${esc(st.error.message)}</div>` : '';
      box.innerHTML = `<div class="card-box pad vc"><div class="vc-head"><div><span class="lbl">Voice room</span>
          <b>${list.length ? `${list.length} in the room` : 'Nobody is talking'}</b></div>
          <div class="vc-people">${list.map((p) => `<span class="vd-p ${voice.state.speaking[p.id] && mine ? 'speaking' : ''}" title="${esc(p.username)}">${avatar(p.username, 28)}<em>${esc(p.username)}</em></span>`).join('')}</div>
          ${mine ? `<button class="btn btn-secondary" id="vc-leave">Leave the call</button>`
            : `<button class="btn btn-primary" id="vc-join" ${full ? 'disabled' : ''}>${elsewhere ? 'Move my call here' : full ? 'Room is full' : 'Join voice'}</button>`}</div>
        <p class="muted vc-note">${mine ? 'You are in this call. It keeps going while you look around Clique: use the bar at the bottom to mute, deafen or leave.' : 'Joining is up to you. Your browser will ask to use your microphone. Voice is only for members of this circle, and nothing is ever recorded.'}</p>${err}</div>`;
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
          : emptyState({ art: 'slip', tone: 'cream', kicker: 'Nothing open', title: 'Dead table.', text: `Nobody in ${esc(c.name)} has bet on anything. Disappointing.`, actions: c.isMember ? `<a class="btn btn-primary" href="#/create?circle=${c.id}">${ICON.plus} Propose a bet</a>` : '' });
        wireCards(box);
      } else if (tab === 'members') {
        const rows = D.members;
        box.innerHTML = `<div class="card-box" style="max-width:720px"><div class="pad muted" style="padding-bottom:6px">Ranked by this week's performance: what you hold now, minus what you started the week with, ignoring top-ups. The worst week does the punishment. <a href="#/weekly/${c.id}">Rewards and rules</a></div>
          ${rows.map((r, i) => `<div class="standing ${i === rows.length - 1 && rows.length > 1 && r.delta < rows[0].delta ? 'last' : ''}">
            <span class="rk">${r.position || i + 1}</span>${avatar(r.user.username, 36)}
            <div class="grow"><a href="#/u/${esc(r.user.username)}" style="font-weight:600">${esc(r.user.username)}</a>${rankTag(r.user.rank)}${r.isOwner ? ' <span class="tag res">Owner</span>' : ''}${titleHtml(r.user.username)}
              <div class="mono muted" style="font-size:11.5px;letter-spacing:.05em;text-transform:uppercase">seated ${dateShort(r.joinedAt)}</div></div>
            <div style="text-align:right"><b class="num ${r.delta >= 0 ? 'up' : 'down'}">${money(r.delta, { plus: true })}</b><div class="num muted" style="font-size:12.5px">holding ${money(r.value)}</div></div>
            ${c.isOwner && !r.isOwner ? `<button class="icon-btn" data-kick="${r.user.id}" data-name="${esc(r.user.username)}" title="Remove" aria-label="Remove">${ICON.x}</button>` : ''}</div>`).join('')}</div>`;
      } else if (tab === 'settings') {
        box.innerHTML = `<form class="card-box pad-lg stack" id="sform" style="max-width:560px">
          <div class="field" style="margin:0"><label>Name</label><input class="input" id="s-name" value="${esc(c.name)}" maxlength="40"></div>
          <div class="field" style="margin:0"><label>Description</label><input class="input" id="s-desc" value="${esc(c.description)}" maxlength="200"></div>
          <div class="field" style="margin:0"><label>Who can join?</label><select class="select" id="s-vis"><option value="private" ${c.visibility === 'private' ? 'selected' : ''}>Private (invite code only)</option><option value="public" ${c.visibility === 'public' ? 'selected' : ''}>Public (anyone can find and join)</option></select></div>
          <div><button class="btn btn-primary">Save it</button></div></form>`;
      }
    }

    root.addEventListener('click', async (e) => {
      const t = e.target.closest('button'); if (!t) return;
      try {
        if (t.id === 'vc-join') { t.disabled = true; await voice.join({ id, name: D.circle.name }); drawVoice(); }
        else if (t.id === 'vc-leave') { await voice.leave(); loadRoom(); }
        else if (t.dataset.t) { tab = t.dataset.t; remember(MEM, { tab }); root.querySelectorAll('#ctabs button').forEach((b) => b.classList.toggle('active', b === t)); drawTab(); }
        else if (t.id === 'join') { await post(`/api/circles/${id}/join`, {}); await loadCircles(); toast('You have a seat.', 'ok'); load(); }
        else if (t.id === 'leave') { if (await confirmBox({ title: 'Leave this circle?', text: 'You keep any open bets, but you will no longer see new markets here.', confirm: 'Leave', danger: true })) { await post(`/api/circles/${id}/leave`, {}); await loadCircles(); go('#/circles'); } }
        else if (t.id === 'copy-code' || t.closest('#copy-code')) copyText(D.circle.inviteCode);
        else if (t.id === 'regen') { if (await confirmBox({ title: 'Generate a new code?', text: 'The old code stops working. People already inside stay in.', confirm: 'New code' })) { await post(`/api/circles/${id}/regen`, {}); load(); } }
        else if (t.dataset.kick) { if (await confirmBox({ title: `Remove ${t.dataset.name}?`, text: 'They can rejoin with the invite code unless you change it.', confirm: 'Remove', danger: true })) { await post(`/api/circles/${id}/kick`, { userId: t.dataset.kick }); load(); } }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'sform') return; e.preventDefault();
      try { await patch(`/api/circles/${id}`, { name: root.querySelector('#s-name').value, description: root.querySelector('#s-desc').value, visibility: root.querySelector('#s-vis').value }); await loadCircles(); toast('Saved', 'ok'); load(); }
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
