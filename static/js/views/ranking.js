/* The global ranking: everybody registered on the site, by the money in their accumulated account. Not the weekly leaderboard (that one is per
   circle and resets every week). The order shown is a choice; place 1 is always the person with the most. Everything comes from /api/ranking. */
import { get } from '../api.js';
import { esc, moneyFull, avatar } from '../util.js';
import { rankTag } from '../art.js';
import { t } from '../i18n.js';

export default {
  async mount(root) {
    let D = await get('/api/ranking'), order = 'poorest', dead = false;

    const row = (p) => `<div class="list-row" role="listitem" ${p.isMe ? 'aria-current="true"' : ''} style="padding:12px 16px;${p.isMe ? 'background:color-mix(in srgb, var(--lime) 10%, transparent)' : ''}">
      <span class="num muted" style="width:46px;flex:none;text-align:right">#${p.place}</span>
      <a href="#/u/${esc(p.username)}" class="row grow" style="gap:10px;min-width:0">${avatar(p.username, 32)}<b style="overflow-wrap:anywhere">${esc(p.username)}</b>${rankTag(p.rank)}${p.isMe ? `<span class="tag new">${t('tú')}</span>` : ''}</a>
      <b class="num" style="flex:none;max-width:48%;text-align:right;overflow-wrap:anywhere">${moneyFull(p.accum)}</b></div>`;

    const draw = () => {
      const list = order === 'poorest' ? [...D.people].reverse() : D.people;
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">${t('Todo el sitio')}</span><h1 class="page-title">${t('Ranking global.')}</h1>
        <p class="gl-sub">${t('Todos los jugadores registrados, según las fichas de su cuenta <b>acumulada</b>. El lugar 1 es quien tiene más.')}</p></div>
        <div class="row" style="flex-wrap:wrap;gap:10px"><div class="chips" role="group" aria-label="${esc(t('Orden de la lista'))}">
          ${[['poorest', t('Primero quien tiene menos')], ['richest', t('Primero quien tiene más')]].map(([k, l]) => `<button type="button" data-o="${k}" class="pill ${order === k ? 'active' : ''}" aria-pressed="${order === k}">${esc(l)}</button>`).join('')}</div>
          ${D.myPlace ? `<button type="button" class="btn btn-secondary btn-sm" id="gr-me">${t('Encuéntrame')}</button>` : ''}</div></div>
        <div class="stats" style="margin-bottom:22px"><div class="stat"><small>${t('Jugadores')}</small><b class="num">${D.count}</b></div>
          ${D.myPlace ? `<div class="stat"><small>${t('Tu lugar')}</small><b class="num">#${D.myPlace}</b></div>` : ''}
          <div class="stat"><small>${t('Lo más')}</small><b class="num" title="${moneyFull(D.richest)}">${moneyFull(D.richest)}</b></div>
          <div class="stat"><small>${t('Lo menos')}</small><b class="num" title="${moneyFull(D.poorest)}">${moneyFull(D.poorest)}</b></div></div>
        <div class="card-box" role="list" aria-label="${esc(t('Ranking global'))}">${list.length ? list.map(row).join('') : `<p class="muted" style="padding:20px;margin:0">${t('Nadie todavía.')}</p>`}</div></div>`;
      root.querySelectorAll('[data-o]').forEach((b) => b.addEventListener('click', () => { order = b.dataset.o; draw(); }));
      root.querySelector('#gr-me')?.addEventListener('click', () => root.querySelector('[aria-current="true"]')?.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    };
    draw();
    const timer = setInterval(async () => { try { D = await get('/api/ranking'); if (!dead) draw(); } catch { /* keep what is on screen */ } }, 30000);
    return { unmount() { dead = true; clearInterval(timer); } };
  },
};
