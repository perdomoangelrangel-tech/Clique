/* The global ranking: everybody registered on the site, by the money in their accumulated account. Not the weekly leaderboard (that one is per
   circle and resets every week). The order shown is a choice; place 1 is always the person with the most. Everything comes from /api/ranking. */
import { get } from '../api.js';
import { esc, moneyFull, avatar } from '../util.js';
import { rankTag } from '../art.js';

export default {
  async mount(root) {
    let D = await get('/api/ranking'), order = 'poorest', dead = false;

    const row = (p) => `<div class="list-row" role="listitem" ${p.isMe ? 'aria-current="true"' : ''} style="padding:12px 16px;${p.isMe ? 'background:color-mix(in srgb, var(--lime) 10%, transparent)' : ''}">
      <span class="num muted" style="width:46px;flex:none;text-align:right">#${p.place}</span>
      <a href="#/u/${esc(p.username)}" class="row grow" style="gap:10px;min-width:0">${avatar(p.username, 32)}<b style="overflow-wrap:anywhere">${esc(p.username)}</b>${rankTag(p.rank)}${p.isMe ? '<span class="tag new">you</span>' : ''}</a>
      <b class="num" style="flex:none;max-width:48%;text-align:right;overflow-wrap:anywhere">${moneyFull(p.accum)}</b></div>`;

    const draw = () => {
      const list = order === 'poorest' ? [...D.people].reverse() : D.people;
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">Everybody on the site</span><h1 class="page-title">Global ranking.</h1>
        <p class="gl-sub">Every registered player, by the money in their <b>accumulated</b> account. Place 1 is the person with the most.</p></div>
        <div class="row" style="flex-wrap:wrap;gap:10px"><div class="chips" role="group" aria-label="Order of the list">
          ${[['poorest', 'Poorest first'], ['richest', 'Richest first']].map(([k, l]) => `<button type="button" data-o="${k}" class="pill ${order === k ? 'active' : ''}" aria-pressed="${order === k}">${l}</button>`).join('')}</div>
          ${D.myPlace ? '<button type="button" class="btn btn-secondary btn-sm" id="gr-me">Find me</button>' : ''}</div></div>
        <div class="stats" style="margin-bottom:22px"><div class="stat"><small>Players</small><b class="num">${D.count}</b></div>
          ${D.myPlace ? `<div class="stat"><small>Your place</small><b class="num">#${D.myPlace}</b></div>` : ''}
          <div class="stat"><small>The most money</small><b class="num" title="${moneyFull(D.richest)}">${moneyFull(D.richest)}</b></div>
          <div class="stat"><small>The least</small><b class="num" title="${moneyFull(D.poorest)}">${moneyFull(D.poorest)}</b></div></div>
        <div class="card-box" role="list" aria-label="Global ranking">${list.length ? list.map(row).join('') : '<p class="muted" style="padding:20px;margin:0">Nobody yet.</p>'}</div></div>`;
      root.querySelectorAll('[data-o]').forEach((b) => b.addEventListener('click', () => { order = b.dataset.o; draw(); }));
      root.querySelector('#gr-me')?.addEventListener('click', () => root.querySelector('[aria-current="true"]')?.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    };
    draw();
    const timer = setInterval(async () => { try { D = await get('/api/ranking'); if (!dead) draw(); } catch { /* keep what is on screen */ } }, 30000);
    return { unmount() { dead = true; clearInterval(timer); } };
  },
};
