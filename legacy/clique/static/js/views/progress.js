/* Rank and milestones. RANK is long-term progression (XP, never reset, never demoted) and is NOT the weekly leaderboard.
   MILESTONES are lifetime goals that pay into the accumulated account when you claim them. Everything shown comes from /api/progress. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, ago } from '../util.js';
import { rankBadge, gameSticker } from '../art.js';
import { toast } from '../ui.js';

const n = (x) => Number(x).toLocaleString('en-US');
const trim = (v) => String(Number(v).toFixed(2)).replace(/\.?0+$/, '');

export default {
  async mount(root) {
    let D = await get('/api/progress'), dead = false, busy = null, mtab = 'all';

    const hero = () => {
      const r = D.rank;
      return `<section class="card-box rk-hero" aria-label="Your rank">
        <div class="rk-big">${rankBadge(r, 112)}</div>
        <div><span class="kicker">Your rank</span><div class="rk-name">${esc(r.label)}</div>
          <p class="rk-xp"><b class="num">${n(D.xp)}</b> XP${r.max ? ' · the top of the ladder' : ''}</p>
          ${r.max ? '<div class="pbar" aria-hidden="true"><i style="width:100%"></i></div>'
            : `<div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.pct}" aria-label="Progress to ${esc(r.nextLabel)}"><i style="width:${r.pct}%"></i></div>
               <div class="rk-next"><span><b class="num">${n(r.toNext)}</b> XP to <b>${esc(r.nextLabel)}</b></span><span class="num">${n(r.floor)} → ${n(r.next)}</span></div>`}
          <div class="rk-next" style="margin-top:12px"><span>Today you earned <b class="num">${D.today.xp}</b> of <b class="num">${D.today.cap}</b> XP</span><span>Resets at midnight</span></div></div></section>`;
    };

    const ladder = () => `<div class="rk-ladder" role="list" aria-label="All ranks">${D.ladder.map((s) => `<div class="rk-step ${s.reached ? 'reached' : ''} ${s.current ? 'current' : ''}" role="listitem" ${s.current ? 'aria-current="true"' : ''}>${rankBadge(s, 34)}<b>${esc(s.label)}</b><small class="num">${n(s.xp)} XP</small></div>`).join('')}</div>`;

    const how = () => `<div class="rk-cols"><div class="card-box pad-lg"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 6px">How XP is earned</h3>
        <p class="muted" style="margin:0 0 12px">Taking part is what counts, a little at a time, with a daily limit so nobody can grind their way up. Only real money at a stake of ${money(1)} or more counts, and a bigger stake is worth exactly the same.</p>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>What you did</th><th class="r">XP each</th><th class="r">Paid per day</th><th class="r hide-sm">Today</th></tr></thead><tbody>
          ${D.sources.map((s) => `<tr><td>${esc(s.text)}</td><td class="r num">+${s.xp}</td><td class="r num">${s.cap}</td><td class="r num hide-sm">${s.usedToday} / ${s.cap}</td></tr>`).join('')}
          ${D.bonuses.map((b) => `<tr><td>${esc(b.text)}</td><td class="r num">+${esc(b.xp)}</td><td class="r muted">once</td><td class="r hide-sm"></td></tr>`).join('')}
        </tbody></table></div>
        <p class="muted" style="margin:12px 0 0;font-size:13px">Never more than ${D.today.cap} XP a day from taking part.</p></div>
      <div><div class="card-box pad-lg" style="margin-bottom:18px"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 10px">Does not count</h3>
        <ul class="rk-list">${D.notCounted.map((t) => `<li>${esc(t)}</li>`).join('')}</ul></div>
        <div class="card-box pad-lg"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 10px">Promotions</h3>
        ${D.history.length ? `<ul class="rk-hist">${D.history.map((h) => `<li>${rankBadge({ tier: h.tier, division: 0, label: h.to }, 22)}<span><b>${esc(h.to)}</b> <span class="muted">from ${esc(h.from)} · ${ago(h.t)}</span></span></li>`).join('')}</ul>` : '<p class="muted" style="margin:0">None yet. Your first promotion is not far off.</p>'}</div></div></div>`;

    const tierRow = (m, t) => `<div class="ms-tier ${t.status}"><div><span class="num">${esc(t.label)}</span><span class="ms-sub">${money(t.money)} into your accumulated account${t.xp ? ` · +${t.xp} XP` : ''}</span></div>
      ${t.status === 'reached' ? `<button class="btn btn-primary btn-sm" data-claim="${esc(t.id)}" ${busy === t.id ? 'disabled' : ''}>Claim</button>` : t.status === 'claimed' ? '<span class="ch-state">Claimed</span>' : '<span class="ch-state">Upcoming</span>'}</div>`;

    const milestoneCard = (m) => {
      const nxt = m.next, pct = nxt ? Math.min(100, Math.round((m.value / nxt.target) * 100)) : 100;
      const rank = m.metric === 'rank_tier';
      const now = rank ? `<b>${esc(D.rank.name)}</b> now` : m.kind === 'mult' ? `best <b class="num">${trim(m.value)}\u00d7</b>` : m.kind === 'money' ? `<b class="num">${money(m.value)}</b> won` : `<b class="num">${n(m.value)}</b> ${esc(m.unit)}`;
      return `<article class="ms-card card-box" aria-label="${esc(m.title)}"><div><h3>${m.group === 'game' ? `<span class="ch-game">${gameSticker(m.game, 30)}</span>` : ''}${esc(m.title)}</h3><p>${esc(m.desc)}</p></div>
        <div><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="${esc(m.title)} progress"><i style="width:${pct}%"></i></div>
          <div class="ch-nums" style="margin-top:6px"><span>${now}</span><span>${m.complete ? 'All tiers reached' : `next: ${esc(nxt.label)}`}</span></div></div>
        <div class="ms-tiers">${m.tiers.map((t) => tierRow(m, t)).join('')}</div>
        ${m.complete ? '' : `<a class="btn btn-ghost btn-sm" href="${esc(m.href)}" style="align-self:flex-start">Go and do it</a>`}</article>`;
    };

    const milestones = () => {
      const M = D.milestones, t = M.totals;
      const shown = M.milestones.filter((m) => mtab === 'all' || m.group === (mtab === 'games' ? 'game' : 'general'));
      const ready = (g) => M.milestones.filter((m) => g === 'all' || m.group === g).reduce((s, m) => s + m.claimable, 0);
      return `<div class="section-head" style="margin-top:46px"><div><span class="kicker">Lifetime goals</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">Milestones</h2>
          <p class="gl-sub">They never reset. Each reached tier pays once, into your <span class="acct-tag accum">Accumulated account</span> when you claim it, and the rewards never expire. Older activity counts only where the old records are reliable.</p></div></div>
        <div class="ms-sum"><span class="tag good">${t.claimable} ready to claim · ${money(t.claimableMoney)}</span><span class="muted">${t.claimed} of ${t.tiers} tiers claimed</span>
          <div class="tabs" id="mtabs" style="margin:0 0 0 auto">${[['all', 'All'], ['general', 'General'], ['games', 'Games']].map(([k, l]) => `<button data-t="${k}" class="${mtab === k ? 'active' : ''}">${l}${ready(k === 'games' ? 'game' : k) ? ` <span class="num">(${ready(k === 'games' ? 'game' : k)})</span>` : ''}</button>`).join('')}</div></div>
        <div class="ms-grid">${shown.map(milestoneCard).join('')}</div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">Long-term progression</span><h1 class="page-title">Rank &amp; milestones.</h1>
        <p class="gl-sub">Your rank grows with how much you take part, over weeks and months. It is <b>separate from the weekly leaderboard</b> (which is one week of results), it does not depend on your balance, and it never goes down.</p></div></div>
        ${hero()}${ladder()}${how()}${milestones()}</div>`;
    };
    draw();

    const reload = async () => { try { D = await get('/api/progress'); if (!dead) draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', async (e) => {
      const tb = e.target.closest('#mtabs [data-t]');
      if (tb) { mtab = tb.dataset.t; draw(); return; }
      const b = e.target.closest('[data-claim]'); if (!b || busy) return;
      busy = b.dataset.claim; draw();
      try {
        const r = await post('/api/milestones/claim', { id: busy });
        setUser(r.user);
        toast(`${money(r.amount)} claimed into your accumulated account${r.xp ? ` (+${r.xp} XP)` : ''}.`, 'ok', { ms: 5000 });
      } catch (ex) { toast(ex.message, 'err'); }
      busy = null; await reload();
    });
    return { onEvent(ev) { if (['inbox'].includes(ev.type)) reload(); }, unmount() { dead = true; } };
  },
};
