import { get, post, del } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, money, avatar, ICON, until, ago, dateLong } from '../util.js';
import { titleHtml } from '../looks.js';
import { recall, remember } from '../viewstate.js';
import { toast, confirmBox } from '../ui.js';
import { sticker, awardSticker, rankTag } from '../art.js';
import { emptyState } from './components.js';

export default {
  async mount(root, [cid]) {
    await loadCircles().catch(() => {});
    if (!S.myCircles.length) {
      root.innerHTML = `<div class="page">${emptyState({ art: 'scale', tone: 'cream', kicker: 'No circle', title: 'No circle, no weekly drama.', text: 'Join or start a circle and every week somebody gets punished. It might be you.', actions: `<a class="btn btn-primary" href="#/circles">${ICON.users} Find a circle</a>` })}</div>`;
      return;
    }
    let last = null; try { last = localStorage.getItem('clique-weekly-circle'); } catch { /* ignore */ }
    const circleId = cid || (S.myCircles.find((c) => c.id === last) || S.myCircles[0]).id;
    if (!cid) { location.replace(`#/weekly/${circleId}`); return; }
    try { localStorage.setItem('clique-weekly-circle', circleId); } catch { /* ignore */ }

    let rulesOpen = !!recall('weekly-rules').open;                          // the page redraws itself when things happen; it must not close what you were reading
    const MEM = 'weekly:' + circleId;
    let week = recall(MEM).week || '', D = null, dead = false;
    const load = async () => {
      D = await get(`/api/circles/${circleId}/weekly${week ? `?week=${week}` : ''}`);
      if (dead) return; draw();
    };
    const defs = () => Object.fromEntries(D.awardDefs.map((a) => [a.key, a]));
    const wkLabel = () => D.label;

    function hotSeat() {
      const rows = D.standings;
      const lead = D.poll[0];
      const risky = D.isCurrent ? rows.filter((r) => r.req && r.req.atRisk) : [];
      const riskLine = risky.length ? `<div class="hs-risk">Also losing the week unless they catch up on the weekly minimum: ${risky.slice(0, 6).map((r) => esc(r.user.username)).join(', ')}${risky.length > 6 ? ` and ${risky.length - 6} more` : ''}.</div>` : '';
      if (D.isCurrent) {
        if (!D.hotSeat.length) return `<div class="hotseat safe"><span class="lbl">This week</span>${sticker('scale', { size: 64, bg: 'cream', rot: 6 })}<div class="who"><b>Nobody's losing yet.</b></div>
          <div class="pun">Everyone's level. Place some bets so somebody can be embarrassed. Whoever has the worst week takes the punishment.</div>${riskLine}</div>`;
        const names = D.hotSeat.map((u) => esc(u.username)).join(' &amp; ');
        const val = rows.find((r) => r.user.id === D.hotSeat[0].id);
        return `<div class="hotseat"><span class="lbl">In the hot seat</span>${sticker('flame', { size: 64, bg: 'cream', rot: 6 })}
          <div class="who">${D.hotSeat.slice(0, 3).map((u) => avatar(u.username, 56)).join('')}<div><b>${names}</b><div class="val">${val ? money(val.delta, { plus: true }) : ''} this week · worst week</div></div></div>
          <div class="pun">${lead ? `Leading sentence: <b>${esc(lead.text)}</b> (${lead.votes} vote${lead.votes === 1 ? '' : 's'})` : "Nobody's suggested a punishment. Be creative. Be cruel, but fair."}</div>${riskLine}</div>`;
      }
      const r = D.recap;
      if (!r || !D.hotSeat.length) return `<div class="hotseat safe"><span class="lbl">The verdict</span>${sticker('scale', { size: 64, bg: 'cream', rot: 6 })}<div class="who"><b>Nobody pays.</b></div><div class="pun">${esc(r?.note || 'Nothing was recorded for this week.')}</div></div>`;
      return `<div class="hotseat"><span class="lbl">The verdict</span>${sticker('paper', { size: 64, bg: 'cream', rot: 6 })}
        <div class="who">${D.hotSeat.slice(0, 3).map((u) => avatar(u.username, 56)).join('')}<div><b>${D.hotSeat.map((u) => esc(u.username)).join(' &amp; ')}</b><div class="val">${r.reason === 'minimum' ? 'missed the weekly minimum' : 'finished last'}</div></div></div>
        <div class="pun">${r.punishment ? `Sentence: <b>${esc(r.punishment.text)}</b>${r.note ? `<div style="color:#BDB19C;font-weight:400;margin-top:4px;font-size:13px">${esc(r.note)}</div>` : ''}` : esc(r.note)}</div>
        ${r.punishment ? `<div class="row" style="margin-top:14px">${r.served ? '<span class="tag" style="background:#0E0C0A;border-color:#0E0C0A;color:var(--lime)">Served</span>' : '<span class="tag" style="background:#0E0C0A;border-color:#0E0C0A;color:#F2EADB">Pending</span>'}
          ${D.canMarkServed ? `<button class="btn btn-sm" id="served">${r.served ? 'Undo' : 'They did it'}</button>` : ''}</div>` : ''}</div>`;
    }

    function poll() {
      const max = Math.max(1, ...D.poll.map((p) => p.votes));
      const winnerId = !D.isCurrent && D.recap?.punishment?.id;
      return `<div class="card-box pad-lg"><div class="section-head" style="margin-bottom:4px"><h3 style="font-size:30px;letter-spacing:-.045em">The punishment poll</h3>
          <span class="kicker">${D.isCurrent ? 'Suggest one. Vote for one.' : 'Polls closed'}</span></div>
        <p class="muted" style="margin:0 0 16px">Whoever has the worst week (the biggest drop, or the smallest gain) does the winning punishment, and so does anybody who skips the weekly minimum.</p>
        ${D.isCurrent ? `<form id="pform" class="row" style="margin-bottom:16px"><input class="input" id="ptext" maxlength="120" placeholder="Sing at the supermarket. Wear the chicken suit."><button class="btn btn-primary">Add</button></form>` : ''}
        <div class="stack" style="gap:12px">${D.poll.length ? D.poll.map((p) => `
          <div class="pun-item paper ${p.voted ? 'voted' : ''}" ${D.isCurrent ? `data-vote="${p.id}"` : ''} style="${winnerId === p.id ? 'box-shadow:4px 4px 0 var(--verm-shadow);' : ''}">
            <div class="bar" style="width:${(p.votes / max) * 100}%"></div>
            <span class="votebtn">${ICON.check}</span>
            <div class="grow"><div style="font-weight:600;line-height:1.2">${esc(p.text)} ${winnerId === p.id ? '<span class="tag bad">Winner</span>' : ''}</div>
              <div class="mono muted" style="font-size:11px;margin-top:3px;letter-spacing:.03em;text-transform:uppercase">${esc(p.author.username)}${p.voters.length ? ` · ${p.voters.map(esc).join(', ')}` : ''}</div></div>
            <b class="num" style="font-size:22px">${p.votes}</b>
            ${D.isCurrent ? `<button class="icon-btn" data-delp="${p.id}" title="Remove" aria-label="Remove">${ICON.x}</button>` : ''}</div>`).join('')
          : `<p class="quiet">${D.isCurrent ? 'No suggestions. Be creative. Be cruel, but fair.' : 'Nobody suggested a punishment this week. Lucky.'}</p>`}</div></div>`;
    }

    const wkDate = (key) => new Date(key + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    /** The weekly minimum: bet in a poll and play the casino, or lose the week. Shown as progress, and as the result once the week is settled. */
    function minimum() {
      const R = D.rules.requirements, req = D.me && D.me.req;
      if (!R || !req || !(R.polls || R.casino)) return '';
      const bar = (label, have, need) => need ? `<div class="req-row ${have >= need ? 'done' : ''}"><div class="req-top"><span>${label}</span><b class="num">${Math.min(have, need)} / ${need}</b></div>
          <div class="req-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${need}" aria-valuenow="${Math.min(have, need)}" aria-label="${esc(label)}"><i style="width:${Math.min(100, (have / need) * 100)}%"></i></div></div>` : '';
      const cur = D.isCurrent;
      let note, tone = '';
      if (req.exempt) note = 'You joined this week, so the minimum starts for you next week.';
      else if (!req.enforced) note = `The minimum starts with the week of ${wkDate(R.from)}. Until then this is only a preview.`;
      else if (cur) { note = req.met ? 'You have kept the minimum. Nothing more is needed this week.' : 'Miss either one before the week closes and you lose the week: you take the punishment and earn no reward.'; tone = req.met ? 'ok' : 'warn'; }
      else { note = D.me.out ? 'You missed the minimum, so you lost this week: the punishment, and no reward.' : 'You kept the minimum.'; tone = D.me.out ? 'warn' : 'ok'; }
      return `<div class="req ${tone}"><div class="lbl">The weekly minimum</div>
        ${bar(plural(R.polls, 'poll bet', 'poll bets'), req.polls.have, R.polls)}${bar(plural(R.casino, 'casino bet', 'casino bets'), req.casino.have, R.casino)}
        <p>${note}</p></div>`;
    }
    const place = (n) => `${n}${[, 'st', 'nd', 'rd'][(n % 100 >> 3) ^ 1 && n % 10] || 'th'}`;
    function ruleLines() {
      const R = D.rules, pay = R.rewards.map((v, i) => `${place(i + 1)} ${money(v, { noCents: true })}`).join(', ');
      const scale = [2, 3, 4, R.fullAt].map((n) => `${n}${n === R.fullAt ? '+' : ''} active = ${Math.round(Math.min(1, (n - 1) / (R.fullAt - 1)) * 100)}%`).join(', ');
      return [
        `<b>How you are ranked.</b> Weekly performance = what you hold now (weekly account plus what it is working on: open bets at cash-out value, rounds still being played) minus what you held when the week began, minus anything handed to you (the weekly refill, top-ups, vouchers). Wins and losses count. The accumulated account, the Store and the Exchange do not.`,
        ...(D.rules.requirements && (D.rules.requirements.polls || D.rules.requirements.casino) ? [
          `<b>The weekly minimum.</b> To stay in the challenge you have to bet in at least ${plural(D.rules.requirements.polls, 'poll', 'polls')} and play at least ${plural(D.rules.requirements.casino, 'casino round', 'casino rounds')} during the week. Miss either one when the week closes and you <b>lose the week automatically</b>: you take the week's punishment (in place of whoever finished last, so it can be several people) and earn no reward, whatever your result. Practice rounds do not count, a round counts once it is finished, and an account created during the week is exempt for that first week.${D.rules.requirements.from && D.rules.requirements.from > D.week && D.isCurrent ? ` It starts with the week of ${wkDate(D.rules.requirements.from)}.` : ''}`] : []),
        `<b>Ties.</b> Higher performance first, then more held at the end, then the older account, then the account id. Nobody is ever ordered by chance.`,
        `<b>When the week runs.</b> Monday 00:00 to the next Monday 00:00, ${esc(D.timezone)} (a week ends at the stroke of midnight on Sunday night).`,
        `<b>Rewards</b> go into your <b>accumulated</b> account when the week closes: ${pay}; anybody else who played earns ${money(R.participation, { noCents: true })}.`,
        `<b>To earn one</b> you need at least ${R.minMoves} bet or casino round this week (practice rounds do not count). Idle members are listed but do not take a place. A circle needs ${R.minActive} active members; smaller circles are paid on a scale (${scale}).`,
        `<b>Several circles?</b> You are paid for your best finish only (${R.maxPerUser} reward a week).`,
        `<b>Your weekly account</b> ${R.mode === 'reset' ? `is set to ${money(R.allocation, { noCents: true })} when each week starts; leftovers do not carry over` : `gets ${money(R.allocation, { noCents: true })} added when each week starts`}. Bets you are still holding when the week closes stay yours, and count at their value in the next week.`,
      ];
    }
    function yourWeek() {
      const me = D.me, cur = D.isCurrent;
      let head;
      if (!me) head = `<p class="muted" style="margin:6px 0 0">${D.standings.length ? 'You were not in this circle that week.' : 'Nothing to rank for this week.'}</p>`;
      else {
        const rewardTxt = me.reward > 0
          ? `<b class="num up">${money(me.reward, { plus: true })}</b><small>${cur ? (me.req && me.req.atRisk ? 'estimated, only if you meet the weekly minimum' : 'estimated, if the week ended now') : me.paid ? 'paid to your accumulated account' : 'decided'}</small>`
          : `<b class="num">$0.00</b><small>${esc(me.note || (cur ? 'nothing earned right now' : 'no reward'))}</small>`;
        head = `<div class="yw-stats">
          <div class="stat"><small>${cur ? 'Position right now' : 'Final position'}</small><b>${me.position}<span class="muted" style="font-size:.55em"> of ${me.of}</span></b></div>
          <div class="stat"><small>Weekly performance</small><b class="num ${me.delta >= 0 ? 'up' : 'down'}">${money(me.delta, { plus: true })}</b><small>${me.moves} bet${me.moves === 1 ? '' : 's'} and round${me.moves === 1 ? '' : 's'} so far</small></div>
          <div class="stat"><small>Reward</small>${rewardTxt}</div></div>`;
      }
      const sc = D.scale ?? 0;
      return `<div class="card-box pad-lg yw"><div class="section-head" style="margin-bottom:6px"><h3 style="font-size:30px;letter-spacing:-.045em">Your week</h3>
          <span class="kicker">${cur ? `closes in <span id="w-left">${until(D.end)}</span>` : `settled ${D.recap ? ago(D.recap.finalizedAt) : ''}`}</span></div>
        ${head}
        ${minimum()}
        ${D.activeCount !== undefined ? `<p class="muted" style="margin:14px 0 0;font-size:14px">${D.activeCount} active member${D.activeCount === 1 ? '' : 's'} in this circle ${cur ? 'so far' : 'that week'}. ${sc >= 1 ? 'Rewards are paid in full.' : sc > 0 ? `Rewards are paid at ${Math.round(sc * 100)}% (small circle).` : `No rewards are paid unless ${D.rules.minActive} members are active.`}</p>` : ''}
        <details style="margin-top:14px" ${rulesOpen ? 'open' : ''}><summary class="lbl" style="cursor:pointer">The rules, in full</summary>
          <ul class="rules">${ruleLines().map((l) => `<li>${l}</li>`).join('')}</ul></details></div>`;
    }

    const missingOf = (req) => [req.polls.have < req.polls.need ? plural(req.polls.need - req.polls.have, 'more poll bet', 'more poll bets') : '',
      req.casino.have < req.casino.need ? plural(req.casino.need - req.casino.have, 'more casino bet', 'more casino bets') : ''].filter(Boolean).join(' and ');
    function standings() {
      const rows = D.standings;
      return `<div class="card-box"><div class="pad" style="padding-bottom:8px"><b style="font-family:var(--f-display);font-size:26px;letter-spacing:-.04em">Standings</b> <span class="kicker" style="margin-left:6px">${D.provisional ? 'live' : 'final'} · weekly performance</span></div>
        ${rows.length ? rows.map((r, i) => `<div class="standing ${D.hotSeat.some((h) => h.id === r.user.id) ? 'last' : ''} ${S.user && r.user.id === S.user.id ? 'me' : ''}"><span class="rk">${r.position || i + 1}</span>${avatar(r.user.username, 36)}
          <div class="grow"><a href="#/u/${esc(r.user.username)}" style="font-weight:600">${esc(r.user.username)}</a>${rankTag(r.user.rank)}${i === 0 && rows.length > 1 && r.delta > rows[rows.length - 1].delta ? ` <span class="up" title="Best week">${ICON.crown}</span>` : ''}${D.hotSeat.some((h) => h.id === r.user.id) ? ` <span class="down" title="Hot seat">${ICON.flame}</span>` : ''}${titleHtml(r.user.username)}
 ${r.out ? `<span class="tag bad" title="${esc(r.rewardNote)}">lost the week</span>` : r.req && r.req.atRisk && D.isCurrent ? `<span class="tag warnish" title="${esc(`Still needs ${missingOf(r.req)} before the week closes, or loses it`)}">at risk</span>` : ''}
            ${r.reward > 0 ? `<span class="tag good" title="${D.provisional ? 'Estimated reward, paid into the accumulated account when the week closes, if the weekly minimum is met' : r.rewardPaid ? 'Paid into the accumulated account' : 'Reward'}">${money(r.reward, { plus: true, noCents: true })}</span>` : r.rewardNote && !r.out ? `<span class="muted rw-note" title="${esc(r.rewardNote)}">${r.active ? 'no reward' : 'idle'}</span>` : ''}</div>
          <div style="text-align:right"><b class="num ${r.delta >= 0 ? 'up' : 'down'}">${money(r.delta, { plus: true })}</b><div class="num muted" style="font-size:12.5px">holding ${money(r.value)}</div></div></div>`).join('')
          : '<p class="quiet pad">No numbers for this week.</p>'}</div>`;
    }

    function awards() {
      const df = defs();
      const names = Object.fromEntries(D.standings.map((r) => [r.user.id, r.user]));
      const won = new Set(D.awards.map((a) => a.key));
      const cards = D.awards.map((a, i) => {
        const def = df[a.key]; if (!def) return '';
        const tone = a.key === 'topDog' ? 'gold' : a.key === 'hotSeat' ? 'fire' : '';
        return `<div class="award paper ${tone}" style="animation-delay:${i * 45}ms">${awardSticker(a.key, 58)}<h5>${esc(def.name)}</h5><p>${esc(def.desc)}</p>
          <div class="win">${a.userIds.map((id) => names[id] ? `${avatar(names[id].username, 26)}<a href="#/u/${esc(names[id].username)}">${esc(names[id].username)}</a>` : '').join('')}</div>
          <div class="val">${esc(a.value)}</div></div>`;
      }).join('');
      const open = D.isCurrent ? D.awardDefs.filter((d) => !won.has(d.key)) : [];
      return `<div class="section-head" style="margin-top:50px"><div><span class="kicker">${D.provisional ? 'Not final until the week closes' : 'Final'}</span><h2 class="page-title" style="font-size:clamp(30px,3.6vw,48px)">${D.isCurrent ? 'The awards race' : 'The awards'}</h2></div></div>
        ${cards ? `<div class="awards">${cards}</div>` : '<p class="quiet">No awards yet. Do something worth remembering.</p>'}
        ${open.length ? `<details style="margin-top:26px"><summary class="lbl" style="cursor:pointer;padding:6px 0">${open.length} awards nobody has earned yet</summary>
          <div class="badge-row" style="margin-top:14px">${open.map((d) => `<div class="trophy" style="opacity:.62"><span style="filter:grayscale(1)">${awardSticker(d.key, 40)}</span><div><b>${esc(d.name)}</b><small>${esc(d.desc)}</small></div></div>`).join('')}</div></details>` : ''}`;
    }

    function draw() {
      const list = [...new Set([S.week || D.week, ...D.weeks])].sort().reverse();
      const idx = list.indexOf(D.week);
      root.innerHTML = `<div class="page">
        <div class="section-head">
          <div><span class="kicker">Somebody pays for this</span><h1 class="page-title">The weekly.</h1></div>
          <div class="row" style="flex-wrap:wrap;gap:14px">
            <select class="select" id="w-circle" style="height:38px" aria-label="Circle">${S.myCircles.map((c) => `<option value="${c.id}" ${c.id === circleId ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select>
            <div class="row">
              <button class="icon-btn" id="w-prev" aria-label="Earlier week" ${idx >= list.length - 1 ? 'disabled style="opacity:.3"' : ''}>${ICON.chevL}</button>
              <div style="text-align:center;min-width:176px"><b class="mono" style="font-size:13px;letter-spacing:.03em;text-transform:uppercase">${wkLabel()}</b>
                <div class="kicker">${D.isCurrent ? `closes in ${until(D.end)}` : 'settled'}</div></div>
              <button class="icon-btn" id="w-next" aria-label="Later week" ${idx <= 0 ? 'disabled style="opacity:.3"' : ''}>${ICON.chevR}</button></div></div></div>
        <div class="wk"><div class="stack">${yourWeek()}${hotSeat()}${poll()}</div><div class="stack">${standings()}</div></div>
        ${awards()}</div>`;
      root.querySelector('#w-circle').addEventListener('change', (e) => go(`#/weekly/${e.target.value}`));
      root.querySelector('#w-prev').addEventListener('click', () => { if (idx < list.length - 1) { week = list[idx + 1]; remember(MEM, { week }); load(); } });
      root.querySelector('#w-next').addEventListener('click', () => { if (idx > 0) { week = list[idx - 1]; remember(MEM, { week }); load(); } });
    }

    root.addEventListener('toggle', (e) => { if (e.target.matches && e.target.matches('.yw details')) { rulesOpen = e.target.open; remember('weekly-rules', { open: rulesOpen }); } }, true);
    root.addEventListener('click', async (e) => {
      try {
        const del1 = e.target.closest('[data-delp]');
        if (del1) { e.stopPropagation(); if (await confirmBox({ title: 'Pull this punishment?', text: 'Its votes go with it.', confirm: 'Pull it', danger: true })) { await del(`/api/circles/${circleId}/punishments/${del1.dataset.delp}`); load(); } return; }
        const v = e.target.closest('[data-vote]');
        if (v) { await post(`/api/circles/${circleId}/punishments/${v.dataset.vote}/vote`, {}); load(); return; }
        if (e.target.id === 'served') { await post(`/api/circles/${circleId}/recaps/${D.week}/served`, {}); load(); }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'pform') return; e.preventDefault();
      const input = root.querySelector('#ptext');
      try { await post(`/api/circles/${circleId}/punishments`, { text: input.value }); toast('Added. It counts as your vote.', 'ok'); load(); } catch (ex) { toast(ex.message, 'err'); }
    });
    await load();
    const clock = setInterval(() => { const el = root.querySelector('#w-left'); if (el && D) el.textContent = until(D.end); }, 15000);
    return { onEvent(ev) { if (ev.type === 'week' || ev.type === 'reward' || (ev.type === 'weekly' && ev.circleId === circleId) || ev.type === 'market') load().catch(() => {}); }, unmount() { dead = true; clearInterval(clock); } };
  },
};
