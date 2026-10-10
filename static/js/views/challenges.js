/* Weekly challenges: three that pay into the WEEKLY account and three that pay into the ACCUMULATED account. The page only shows
   what the server worked out (/api/challenges) and asks it to claim; it never counts anything itself. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, until, dateShort } from '../util.js';
import { toast } from '../ui.js';
import { gameSticker } from '../art.js';
import { emptyState } from './components.js';

const ACCT = {
  weekly: { cls: 'weekly', tag: 'Weekly account', head: 'Pays into your weekly account', note: 'Chips for the week they were earned in: play with them, or they pay off a loan. What is left is reset when the week closes, like everything in the weekly account.' },
  accumulated: { cls: 'accum', tag: 'Accumulated account', head: 'Pays into your accumulated account', note: 'Money you keep. It never resets, and it is what the Store and the Exchange spend.' },
};
const trim = (v) => String(Number(v).toFixed(2)).replace(/\.?0+$/, '');
/** What a number means for this goal: plain count, a multiplier, or dollars. */
const show = (c, v) => (c.kind === 'mult' ? `${trim(v)}\u00d7` : c.kind === 'money' ? money(v) : Number(v).toLocaleString('en-US'));
const STATUS = { available: 'Not started', in_progress: 'In progress', completed: 'Finished: claim it', claimed: 'Claimed', expired: 'Expired' };

export default {
  async mount(root) {
    let D = await get('/api/challenges'), dead = false, busy = null;

    const card = (c, past = false) => {
      const a = ACCT[c.account], pct = Math.round((c.progress / c.target) * 100);
      const done = c.status === 'completed', claimed = c.status === 'claimed', expired = c.status === 'expired';
      return `<article class="ch-card card-box ${c.status} ${a.cls}-c" data-id="${esc(c.id)}" aria-label="${esc(c.title)}">
        <div class="ch-top"><h3>${c.game ? `<span class="ch-game">${gameSticker(c.game, 30)}</span>` : ''}${esc(c.title)}</h3><span class="acct-tag ${a.cls}">${a.tag}</span></div>
        <p class="ch-desc">${esc(c.desc)}</p>
        <div><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="${c.target}" aria-valuenow="${c.progress}" aria-label="${esc(c.title)} progress"><i style="width:${pct}%"></i></div>
          <div class="ch-nums" style="margin-top:6px"><span><b>${show(c, c.progress)}</b> / ${show(c, c.target)}${c.kind === 'count' ? ' ' + esc(c.unit) : c.kind === 'mult' ? ' in one round' : ' won'}</span><span class="ch-state">${STATUS[c.status]}</span></div></div>
        <div class="ch-reward"><span class="amt">${money(c.reward)}</span><span>into your <b>${a.tag.toLowerCase()}</b></span>${c.xp ? `<span class="tag">+${c.xp} XP</span>` : ''}</div>
        <p class="ch-rule">${esc(c.rule)}</p>
        <div class="ch-actions">
          ${claimed ? `<span class="muted" style="font-size:13px">${c.claim && c.claim.auto ? 'Credited automatically when the week closed.' : 'Reward claimed.'}</span>`
            : expired ? '<span class="muted" style="font-size:13px">Not finished before the week closed, so it expired.</span>'
            : done && !past ? `<button class="btn btn-primary" data-claim="${esc(c.id)}" ${busy === c.id ? 'disabled' : ''}>Claim ${money(c.reward)}</button>`
            : `<a class="btn btn-secondary btn-sm" href="${esc(c.href)}">${esc(c.cta)}</a>`}
          ${past ? '' : `<span class="muted num" style="font-size:12px">${until(D.end)} left</span>`}
        </div></article>`;
    };

    const column = (key, rows) => `<section aria-label="${ACCT[key].head}"><div class="gl-colhead ${ACCT[key].cls}"><h2>${ACCT[key].tag}</h2><p><b>${ACCT[key].head}.</b> ${ACCT[key].note}</p></div>${rows.map((c) => card(c)).join('')}</section>`;

    const history = () => {
      if (!D.history.length) return '';
      return `<div class="ch-hist"><div class="section-head"><div><span class="kicker">Earlier weeks</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">History</h2></div></div>
        <p class="muted" style="margin:-8px 0 16px;max-width:70ch">A challenge you finished but did not claim was credited for you when its week closed. One you did not finish simply expired.</p>
        ${D.history.map((h) => `<details><summary><span>Week of ${dateShort(new Date(h.week + 'T12:00:00').getTime())}</span><span class="muted">${h.items.filter((i) => i.status === 'claimed').length} paid · ${h.items.filter((i) => i.status === 'expired').length} expired</span></summary>
          ${h.items.map((i) => `<div class="hrow"><span class="acct-tag ${ACCT[i.account].cls}">${i.account === 'weekly' ? 'Weekly' : 'Accum.'}</span><span>${esc(i.title)}<br><small class="muted">${show(i, i.progress)} / ${show(i, i.target)}${i.kind === 'count' ? ' ' + esc(i.unit) : ''}</small></span><b class="num">${money(i.reward)}</b><span class="ch-state">${STATUS[i.status]}</span></div>`).join('')}</details>`).join('')}</div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">New every Monday</span><h1 class="page-title">Weekly challenges.</h1>
          <p class="gl-sub">Eight goals each week. Four pay into your <b>weekly account</b>, four into your <b>accumulated account</b>, and every card says which. Some ask for variety or showing up; some are about one game (play so many hands, reach a multiplier, win some money). None rewards losing, borrowing or betting bigger. ${D.rules.claimRule}</p></div>
          <div class="stat" style="min-width:150px"><small>This week closes in</small><b class="num">${until(D.end)}</b></div></div>
        <div class="gl-grid2">${column('weekly', D.weekly)}${column('accumulated', D.accumulated)}</div>
        <p class="muted" style="font-size:13px;max-width:78ch;margin:6px 2px 0">Only real-money actions count (a stake of at least ${money(D.rules.minStake)}). Practice rounds, loans, repayments, transfers and Store purchases never count. Challenge rewards are credits from outside play, so they never move your weekly leaderboard result.</p>
        ${history()}</div>`;
    };
    draw();

    const reload = async () => { try { D = await get('/api/challenges'); if (!dead) draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-claim]'); if (!b || busy) return;
      busy = b.dataset.claim; draw();
      try {
        const r = await post('/api/challenges/claim', { id: busy });
        setUser(r.user);
        toast(`${money(r.amount)} claimed into your ${r.account} account${r.xp ? ` (+${r.xp} XP)` : ''}.`, 'ok', { ms: 5000 });
      } catch (ex) { toast(ex.message, 'err'); }
      busy = null; await reload();
    });
    const timer = setInterval(() => { if (!dead) draw(); }, 60000);          // the clock counts down
    return { onEvent(ev) { if (['inbox', 'week'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
