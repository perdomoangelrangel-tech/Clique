import { post } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, ICON, circleMark } from '../util.js';
import { emptyState } from './components.js';
import { toast, modal } from '../ui.js';

const EMOJIS = ['👥', '🔥', '🎯', '🍻', '🎮', '⚽', '🏀', '🏠', '🎓', '💼', '🌎', '🐸', '👑', '🦄', '🚀', '🎲'];

export function circleCard(c, joinBtn = false) {
  return `<div class="ccard" data-open="${c.id}">
    <div class="row" style="gap:14px">${circleMark(c, 54)}
      <div class="grow"><h3 class="ellipsis">${esc(c.name)}</h3>
        <div class="row" style="gap:6px;margin-top:3px"><span class="tag">${c.visibility === 'public' ? ICON.globe + ' Public' : ICON.lock + ' Private'}</span>
          ${c.isOwner ? '<span class="tag res">Owner</span>' : ''}</div></div></div>
    <p>${esc(c.description) || '&nbsp;'}</p>
    <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px"><span class="mono muted" style="font-size:12px;letter-spacing:.04em;text-transform:uppercase">${c.memberCount} member${c.memberCount === 1 ? '' : 's'} · ${esc(c.ownerName)}</span>
      ${joinBtn ? `<button class="btn btn-primary btn-sm" data-join="${c.id}">Join</button>` : ''}</div></div>`;
}

export function openCreateCircle() {
  let vis = 'private', emoji = '👥';
  const m = modal(`<span class="lbl">New table</span><h2>Start a circle</h2><p class="lede">A circle is your group. Bets, punishments and awards all live inside it. Pick people you can stand losing to.</p>
    <form id="cc-form" autocomplete="off">
      <div class="field"><label>Name</label><input class="input" id="cc-name" maxlength="40" placeholder="The Usual Suspects"></div>
      <div class="field"><label>Description <span class="muted" style="font-weight:400">(optional)</span></label><input class="input" id="cc-desc" maxlength="200" placeholder="Arguing since 2019"></div>
      <div class="field"><label>Icon <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">(or keep the letter)</span></label><div class="emoji-pick" id="cc-emoji">${EMOJIS.map((e) => `<button type="button" data-e="${e}" class="${e === emoji ? 'active' : ''}">${e}</button>`).join('')}</div></div>
      <div class="field"><label>Who can join?</label>
        <div class="seg" id="cc-vis" style="align-self:flex-start"><button type="button" data-v="private" class="active">${ICON.lock} Private</button><button type="button" data-v="public">${ICON.globe} Public</button></div>
        <small id="cc-help">Invite code only. Strangers can't even see it.</small></div>
      <div class="error-text" id="cc-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary">Start it</button></div>
    </form>`);
  m.el.querySelector('#cc-emoji').addEventListener('click', (e) => { const b = e.target.closest('[data-e]'); if (!b) return; emoji = b.dataset.e; m.el.querySelectorAll('#cc-emoji button').forEach((x) => x.classList.toggle('active', x === b)); });
  m.el.querySelector('#cc-vis').addEventListener('click', (e) => {
    const b = e.target.closest('[data-v]'); if (!b) return; vis = b.dataset.v;
    m.el.querySelectorAll('#cc-vis button').forEach((x) => x.classList.toggle('active', x === b));
    m.el.querySelector('#cc-help').textContent = vis === 'private' ? "Invite code only. Strangers can't even see it." : 'Anyone on this site can find it, read its bets and sit down.';
  });
  m.el.querySelector('#cc-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = m.el.querySelector('#cc-err'); err.textContent = '';
    try {
      const d = await post('/api/circles', { name: m.el.querySelector('#cc-name').value, description: m.el.querySelector('#cc-desc').value, visibility: vis, emoji });
      await loadCircles(); m.close(); toast('Circle open. Share the code with people you trust (or don\'t).', 'ok'); go(`#/circle/${d.circle.id}`);
    } catch (ex) { err.textContent = ex.message; }
  });
}

export function openJoinByCode() {
  const m = modal(`<span class="lbl">Password at the door</span><h2>Got a code?</h2><p class="lede">Six letters. Whoever runs the circle has it.</p>
    <form id="jc-form" autocomplete="off"><div class="field"><input class="input" id="jc-code" maxlength="6" placeholder="ABC123" style="text-transform:uppercase;letter-spacing:.3em;font-weight:700;text-align:center;font-size:20px;height:52px"></div>
    <div class="error-text" id="jc-err" style="min-height:18px"></div>
    <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary">Come in</button></div></form>`);
  m.el.querySelector('#jc-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const d = await post('/api/circles/join', { code: m.el.querySelector('#jc-code').value });
      await loadCircles(); m.close(); toast(`You're in ${d.circle.name}.`, 'ok'); go(`#/circle/${d.circle.id}`);
    } catch (ex) { m.el.querySelector('#jc-err').textContent = ex.message; }
  });
}

export default {
  async mount(root) {
    let dead = false;
    const draw = async () => {
      const d = await loadCircles();
      if (dead) return;
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">Tables you sit at</span><h1 class="page-title">Your circles.</h1></div>
          <div class="row"><button class="btn btn-secondary" id="b-join">Got a code?</button><button class="btn btn-primary" id="b-new">${ICON.plus} Start a circle</button></div></div>
        ${d.mine.length ? `<div class="circle-grid">${d.mine.map((c) => circleCard(c)).join('')}</div>`
          : emptyState({ art: 'cards', tone: 'cream', kicker: 'Empty chair', title: 'Table for one. Sad.', text: 'Start a circle and drag your friends in, or beg someone for their code.' })}
        <div class="section-head" style="margin-top:52px"><div><span class="kicker">Walk-ins welcome</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">Public circles.</h2></div></div>
        ${d.discover.length ? `<div class="circle-grid">${d.discover.map((c) => circleCard(c, true)).join('')}</div>`
          : `<p class="quiet">No public circles right now. Private ones never show up here. That's the point.</p>`}
      </div>`;
    };
    await draw();
    root.addEventListener('click', async (e) => {
      if (e.target.closest('#b-new')) return openCreateCircle();
      if (e.target.closest('#b-join')) return openJoinByCode();
      const j = e.target.closest('[data-join]');
      if (j) { e.stopPropagation(); try { await post(`/api/circles/${j.dataset.join}/join`, {}); toast('Pulled up a chair.', 'ok'); go(`#/circle/${j.dataset.join}`); } catch (ex) { toast(ex.message, 'err'); } return; }
      const c = e.target.closest('[data-open]'); if (c) go(`#/circle/${c.dataset.open}`);
    });
    return { onEvent(ev) { if (ev.type === 'circle') draw(); }, unmount() { dead = true; } };
  },
};
