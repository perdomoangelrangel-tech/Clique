import { get, post, del, api } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, detailText, money, moneyFull, num, cents, avatar, ago, dateShort, ICON, circleMark } from '../util.js';
import { awardSticker, rankBadge } from '../art.js';
import { gameName } from '../gamelist.js';
import { bannerCss, setLook, titleHtml } from '../looks.js';
import { productArt, plainAvatar } from '../cosmetics.js';
import { toast, modal } from '../ui.js';
import { guardForm, recall, remember } from '../viewstate.js';
import { emptyState } from './components.js';
import { t, LANGS, getLang, setLang } from '../i18n.js';
import { mountSpread } from './spread.js';

const KIND = { buy: ['Bought', '−'], sell: ['Sold', '+'], win: ['Won', '+'], loss: ['Lost', ''], refund: ['Refund', '+'], deposit: ['Funds added', '+'], game: ['Game', ''], start: ['Welcome bonus', '+'], go: ['Passed Go', '+'], voucher: ['Voucher', '+'], poker: ['Poker', ''], reward: ['Weekly reward', '+'], warn: ['Reminder', ''] };

export default {
  async mount(root, [name, edit]) {
    const prof = await get(`/api/users/${encodeURIComponent(name)}`);
    const mine = prof.user.username.toLowerCase() === S.user.username.toLowerCase();
    const P = mine ? await get('/api/portfolio') : null;
    const defs = Object.fromEntries(prof.awardDefs.map((a) => [a.key, a]));
    const tot = prof.totals;
    const trophyTotal = Object.values(prof.trophies).reduce((a, b) => a + b, 0);
    const MEM = 'profile:' + prof.user.username.toLowerCase();
    let tab = ['positions', 'closed', 'activity', 'games'].includes(recall(MEM).tab) ? recall(MEM).tab : 'positions';

    const PF = prof.user.profile || { slots: {}, art: {}, bg: 'ink', bio: '', style: {}, upload: null };
    const pfHead = (p, who, can) => {
      const banner = (p.art && p.art.banner) || {};
      const accent = (p.art && p.art.accent && p.art.accent.color) || '#C6F432';
      const bgc = ((prof.user.backgrounds || p.backgrounds || DEFAULT_BGS)[p.bg] || DEFAULT_BGS[p.bg] || DEFAULT_BGS.ink).color;
      const light = p.bg === 'paper';
      const fam = (p.fonts || FONT_STACKS)[(p.art && p.art.font && p.art.font.family) || 'display'] || FONT_STACKS.display;
      const title = (p.art && p.art.title && p.art.title.text) || '';
      const look = p.style || {};
      return `<section class="pf" style="--pf-bg:${bgc};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-mute:${light ? '#5A5246' : '#BDB19C'};--pf-accent:${accent};--pf-font:${fam}">
        <div class="pf-banner" style="${bannerCss(banner)}"></div>
        <div class="pf-main"><div class="pf-av">${plainAvatar(who, 104, look)}</div>
          <div class="pf-id"><h1 class="pf-name">${esc(who)}</h1>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}
            ${prof.rank ? `<div class="pf-rank" title="Rank is long-term progression, separate from the weekly leaderboard">${rankBadge(prof.rank, 30)}<span><b>${esc(prof.rank.label)}</b> · ${Number(prof.rank.xp).toLocaleString('en-US')} XP${mine ? ` · <a href="#/progress">Rank &amp; milestones</a>` : ''}</span></div>` : ''}
            ${p.bio ? `<p class="pf-bio">${esc(p.bio)}</p>` : ''}
            <div class="pf-meta">Seated ${dateShort(prof.user.createdAt)} · ${prof.circles.length ? prof.circles.map((c) => esc(c.name)).join(', ') : 'no circles yet'}</div></div>
          ${can}</div><i class="pf-rule"></i></section>`;
    };
    const DEFAULT_BGS = { ink: { color: '#14110F' }, felt: { color: '#1E3B2C' }, wine: { color: '#3A1A16' }, slate: { color: '#22262B' }, paper: { color: '#EFE6D2' } };
    const FONT_STACKS = { display: "'Bricolage Grotesque', 'Helvetica Neue', Arial, sans-serif", body: "'Instrument Sans', Arial, sans-serif", mono: "'JetBrains Mono', ui-monospace, monospace", serif: "'Fraunces', Georgia, serif", marker: "'Rubik Mono One', 'Arial Black', sans-serif" };
    const editBtn = mine ? `<a class="btn btn-secondary pf-edit" href="#/u/${esc(prof.user.username)}/edit">${ICON.pencil} Customize</a>` : '';

    if (mine && edit) return openEditor(root, prof, PF);

    root.innerHTML = `<div class="page">
      ${pfHead(PF, prof.user.username, editBtn)}${''/* html: seguro (pfHead escapa el nombre por dentro) */}
      ${mine ? `<div class="acct-cards" style="margin-top:22px"><div class="card-box pad-lg acct"><span class="lbl">Weekly account</span><b class="num" title="${moneyFull(P.balance)}">${money(P.balance)}</b><p class="muted">This week's chips. Set up again every Monday. <a href="#/portfolio">Where is it?</a></p></div>
        <div class="card-box pad-lg acct"><span class="lbl">Accumulated account</span><b class="num" title="${moneyFull(prof.accounts.accumulated)}">${money(prof.accounts.accumulated)}</b><p class="muted">What you keep. <a href="#/portfolio">Portfolio</a> · <a href="#/store">Store</a> · <a href="#/exchange">Exchange</a> · <a href="#/statement">Statement</a></p></div></div>` : ''}
      ${mine ? `<div class="card-box pad lang-pick" style="margin-top:16px"><div class="field" style="margin:0"><label for="pf-lang">${t('Idioma de la app')}</label>
        <select class="input" id="pf-lang">${Object.entries(LANGS).map(([code, name]) => `<option value="${code}" ${code === getLang() ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></div></div>` : ''}
      <div class="stats">
        <div class="stat"><small>Held in the weekly game</small><b title="${moneyFull(prof.netWorth)}">${money(prof.netWorth)}</b></div>
        <div class="stat"><small>Awards won</small><b>${trophyTotal}</b></div>
        <div class="stat"><small>Bets proposed</small><b>${num(tot.marketsCreated || 0, 0)}</b></div>
        <div class="stat"><small>Won / lost</small><b>${num(tot.betsWon || 0, 0)} / ${num(tot.betsLost || 0, 0)}</b></div>
        <div class="stat"><small>Casino P/L</small><b class="${(tot.gamePnl || 0) >= 0 ? 'up' : 'down'}" title="${moneyFull(tot.gamePnl || 0)}">${money(tot.gamePnl || 0, { plus: true })}</b></div>
      </div>
      ${mine ? '<div id="spread" style="margin-top:28px"></div>' : ''}
      ${mine && prof.rewards && prof.rewards.length ? `<div class="section-head" style="margin-top:44px"><div><span class="kicker">Paid into your accumulated account</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">Weekly rewards</h2></div></div>
        <div class="card-box pad">${prof.rewards.slice(0, 12).map((r) => `<div class="list-row"><div class="grow"><b>#${r.position}</b> in ${esc(r.circle)} <span class="muted">· week of ${esc(r.week)}</span></div><b class="num up">${money(r.amount, { plus: true })}</b><span class="tag ${r.paid ? 'good' : ''}">${r.paid ? 'paid' : 'due'}</span></div>`).join('')}</div>` : ''}
      <div class="section-head" style="margin-top:44px"><div><span class="kicker">Weekly hardware</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">Trophy case</h2></div></div>
      ${trophyTotal ? `<div class="badge-row">${Object.entries(prof.trophies).sort((a, b) => b[1] - a[1]).map(([k, n]) => defs[k] ? `<div class="trophy">${awardSticker(k, 48)}<div><b>${esc(defs[k].name)}</b><small>x${n}</small></div></div>` : '').join('')}</div>
        ${prof.recent.length ? `<details style="margin-top:18px"><summary class="lbl" style="cursor:pointer">Recent awards</summary>
          <div style="margin-top:8px">${prof.recent.map((r) => `<div class="list-row"><span style="line-height:0">${awardSticker(r.key, 32)}</span><div class="grow"><b>${esc(defs[r.key]?.name || r.key)}</b> <span class="muted">· ${esc(r.circle)}</span></div><span class="mono muted" style="font-size:12px">${esc(r.value)} · week of ${esc(r.week)}</span></div>`).join('')}</div></details>` : ''}`
        : emptyState({ art: 'shelf', tone: 'cream', tight: true, kicker: 'Empty shelf', title: 'Nothing on the shelf.', text: 'Awards are handed out when the weekly poll closes. Go earn something. Or lose spectacularly. Both count.' })}
      <div id="own"></div></div>`;

    if (!mine) return {};
    root.querySelector('#pf-lang').addEventListener('change', (e) => setLang(e.target.value));      // the whole app repaints in place (app.js)
    mountSpread(root.querySelector('#spread'), P.distribution, { go });
    const own = root.querySelector('#own');
    const draw = () => {
      const tabs = [['positions', `Open slips (${P.open.length})`], ['closed', 'Settled'], ['activity', 'Receipts'], ['games', 'Casino history']];
      own.innerHTML = `<div class="tabs" id="ptabs" style="margin-top:44px">${tabs.map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${l}</button>`).join('')}</div><div id="pbody"></div>`;
      const body = own.querySelector('#pbody');
      const posTable = (rows, closed) => rows.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>Market</th><th>Position</th><th class="r">Shares</th><th class="r">Avg</th><th class="r">${closed ? 'Paid' : 'Value'}</th><th class="r">P/L</th></tr></thead><tbody>
        ${rows.map((r) => `<tr style="cursor:pointer" data-m="${r.market}"><td style="max-width:340px"><b>${esc(r.question)}</b></td><td><span class="tag ${r.side === 'yes' ? 'good' : 'bad'}">${esc(r.label)}</span></td>
          <td class="r num">${num(r.shares)}</td><td class="r num">${cents(r.avgPrice)}</td><td class="r num">${money(r.value ?? 0)}</td>
          <td class="r num ${(r.pnl || 0) >= 0 ? 'up' : 'down'}">${r.refunded ? 'refund' : money(r.pnl || 0, { plus: true })}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: closed ? 'paper' : 'slip', tone: 'cream', tight: true, kicker: closed ? 'Nothing settled' : 'No open slips', title: closed ? 'Nothing to collect on.' : 'You have no skin in the game.', text: closed ? 'Settled bets land here.' : 'Find a bet and put some money where your mouth is.', actions: closed ? '' : '<a class="btn btn-primary" href="#/">Browse the board</a>' });
      if (tab === 'positions') body.innerHTML = `<div class="muted" style="margin-bottom:12px">Your open slips are worth <b class="num">${money(P.positionsValue)}</b> if you cashed out right now.</div>` + posTable(P.open, false);
      else if (tab === 'closed') body.innerHTML = posTable(P.closed, true);
      else if (tab === 'activity') body.innerHTML = P.activity.length ? `<div class="card-box pad">${P.activity.map((a) => {
        const [lbl] = KIND[a.kind] || [a.kind]; const pos = a.amount > 0;
        return `<div class="list-row"><div class="grow"><b>${lbl}</b> <span class="muted">${esc(a.text)}</span></div><span class="muted">${ago(a.t)}</span><b class="num ${pos ? 'up' : a.amount < 0 ? 'down' : ''}" style="width:110px;text-align:right">${a.amount ? money(a.amount, { plus: true }) : '—'}</b></div>`;
      }).join('')}</div>` : '<p class="quiet">Nothing yet.</p>';
      else body.innerHTML = P.history.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>Game</th><th class="r">Bet</th><th class="r">Payout</th><th class="r">Multiplier</th><th>Result</th><th class="r">When</th></tr></thead><tbody>
        ${P.history.map((h) => `<tr><td><b>${esc(gameName(h.game))}</b></td><td class="r num">${money(h.bet)}</td><td class="r num ${h.profit > 0 ? 'up' : h.profit < 0 ? 'down' : ''}">${money(h.payout)}</td><td class="r num">${h.mult ? h.mult.toLocaleString() + '×' : '—'}</td><td class="muted">${detailText(h.detail)}</td><td class="r muted">${ago(h.t)}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: 'snake', tone: 'cream', tight: true, kicker: 'No bets', title: 'Snake eyes. Literally nothing.', text: 'You have not played a single hand.', actions: '<a class="btn btn-primary" href="#/games">Open the casino</a>' });
    };
    draw();
    own.addEventListener('click', (e) => {
      const b = e.target.closest('[data-t]'); if (b) { tab = b.dataset.t; remember(MEM, { tab }); draw(); return; }
      const r = e.target.closest('[data-m]'); if (r) go(`#/market/${r.dataset.m}`);
    });
    return {};
  },
};

// ---------------------------------------------------------------------------------------------------------------------------
// The editor: choose how your profile looks, see it live, then save. Free options are always there; the rest must be owned.
// ---------------------------------------------------------------------------------------------------------------------------
const SLOT_LABEL = { avatar: 'Picture', frame: 'Frame', badge: 'Badge', title: 'Title', banner: 'Banner', accent: 'Colour', font: 'Name font' };
const SLOT_ORDER = ['avatar', 'frame', 'badge', 'title', 'banner', 'accent', 'font'];

async function openEditor(root, prof, startProfile) {
  const [store, mineP] = await Promise.all([get('/api/store'), get('/api/profile')]);
  let P = mineP.profile;                                                        // what is saved
  const sel = { ...P.slots, bg: P.bg, bio: P.bio };                             // what is chosen right now
  let upload = P.upload;                                                        // the saved uploaded picture (a url), if any
  const items = store.items, byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const dirty = () => SLOT_ORDER.some((k) => sel[k] !== P.slots[k]) || sel.bg !== P.bg || sel.bio !== P.bio;
  const guard = guardForm(() => dirty(), 'Your profile changes have not been saved. Leave without saving?');

  const lookOfSel = () => {
    const look = {};
    if (sel.avatar === 'upload' && upload) look.u = upload.split('/').pop();
    else if (byId[sel.avatar] && byId[sel.avatar].art.icon) look.a = { icon: byId[sel.avatar].art.icon, bg: byId[sel.avatar].art.bg };
    const f = byId[sel.frame] && byId[sel.frame].art; if (f && f.style !== 'none') look.f = f;
    const b = byId[sel.badge] && byId[sel.badge].art; if (b && b.glyph) look.b = b.glyph;
    return look;
  };
  const preview = () => {
    const art = {}; for (const k of SLOT_ORDER) art[k] = byId[sel[k]] ? byId[sel[k]].art : {};
    const p = { art, bg: sel.bg, bio: sel.bio, style: lookOfSel(), fonts: store.fonts, backgrounds: P.backgrounds };
    return p;
  };
  const optionHtml = (kind) => {
    const list = items.filter((i) => i.kind === kind).sort((a, b) => (b.free - a.free) || (a.price - b.price));
    const opts = list.map((i) => {
      const usable = i.owned, on = sel[kind] === i.id;
      const note = usable ? (i.free ? 'Free' : 'Owned') : i.state === 'locked' ? 'Locked' : `Store · ${money(i.price, { noCents: true })}`;
      return `<button type="button" class="pick ${on ? 'on' : ''} ${usable ? '' : 'na'}" data-slot="${kind}" data-id="${i.id}" ${usable ? '' : 'data-store="1"'} title="${esc(i.name)}${usable ? '' : ' (not yours yet)'}" aria-pressed="${on}">
        <span class="pick-art">${productArt(i, { name: S.user.username, size: 40, fonts: store.fonts })}</span><span class="pick-name">${esc(i.name)}</span><span class="pick-note ${usable ? '' : 'buy'}">${esc(note)}</span></button>`;
    });
    if (kind === 'avatar') {
      opts.unshift(`<button type="button" class="pick ${sel.avatar === 'upload' ? 'on' : ''} ${upload ? '' : 'na'}" data-slot="avatar" data-id="upload" ${upload ? '' : 'disabled'} aria-pressed="${sel.avatar === 'upload'}">
        <span class="pick-art">${upload ? plainAvatar(S.user.username, 40, { u: upload.split('/').pop() }) : '<span class="pa-none">none</span>'}</span><span class="pick-name">Your upload</span><span class="pick-note">${upload ? 'Free' : 'Upload one'}</span></button>`);
    }
    return opts.join('');
  };
  const bgHtml = () => Object.entries(P.backgrounds).map(([id, b]) => `<button type="button" class="pick ${sel.bg === id ? 'on' : ''}" data-bg="${id}" aria-pressed="${sel.bg === id}"><span class="pick-art"><i class="bg-chip" style="background:${b.color}"></i></span><span class="pick-name">${esc(b.name)}</span><span class="pick-note">Free</span></button>`).join('');

  function paintPreview() {
    const p = preview();
    root.querySelector('#ed-preview').innerHTML = pfPreview(p);
    const mini = root.querySelector('#ed-mini');
    mini.innerHTML = pfMini(p);
    root.querySelector('#ed-save').disabled = !dirty();
    root.querySelector('#bio-n').textContent = String(140 - sel.bio.length);
  }
  /* On a phone the big preview scrolls out of sight while you pick things, so a one-line copy of it stays pinned above the options. */
  const pfMini = (p) => {
    const accent = (p.art.accent && p.art.accent.color) || '#C6F432', light = p.bg === 'paper';
    const fam = store.fonts[(p.art.font && p.art.font.family) || 'display'], title = (p.art.title && p.art.title.text) || '';
    return `<section class="pf pf-mini" style="--pf-bg:${p.backgrounds[p.bg].color};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-accent:${accent};--pf-font:${fam}">
      <span class="pf-av">${plainAvatar(S.user.username, 44, p.style)}</span>
      <span class="pm-id"><b class="pf-name">${esc(S.user.username)}</b>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}</span>
      <button type="button" class="btn btn-primary btn-sm" id="ed-mini-save" ${dirty() ? '' : 'disabled'}>Save</button><i class="pf-rule"></i></section>`;
  };
  const pfPreview = (p) => {
    const banner = p.art.banner || {}, accent = (p.art.accent && p.art.accent.color) || '#C6F432', light = p.bg === 'paper';
    const bgc = p.backgrounds[p.bg].color, fam = store.fonts[(p.art.font && p.art.font.family) || 'display'];
    const title = (p.art.title && p.art.title.text) || '';
    return `<section class="pf" style="--pf-bg:${bgc};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-mute:${light ? '#5A5246' : '#BDB19C'};--pf-accent:${accent};--pf-font:${fam}">
      <div class="pf-banner" style="${bannerCss(banner)}"></div><div class="pf-main"><div class="pf-av">${plainAvatar(S.user.username, 104, p.style)}</div>
      <div class="pf-id"><h1 class="pf-name">${esc(S.user.username)}</h1>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}${p.bio ? `<p class="pf-bio">${esc(p.bio)}</p>` : ''}</div></div><i class="pf-rule"></i></section>`;
  };

  function draw() {
    root.innerHTML = `<div class="page">
      <div class="section-head"><div><span class="kicker">Make it yours</span><h1 class="page-title">Customize profile.</h1></div>
        <a class="btn btn-ghost" href="#/u/${esc(S.user.username)}" id="ed-back">${ICON.chevL} Back to your profile</a></div>
      <p class="muted" style="max-width:68ch;margin:0 0 6px">Pick what you like and watch the preview change. Nothing is saved until you press Save. <b>Free</b> options are always yours, <b>Owned</b> ones you bought, and <b>Store</b> ones you can get in the <a href="#/store">Store</a> with your accumulated account. Only your picture, frame and badge show up in lists around the site; the rest lives on your profile page.</p>
      <div class="ed">
        <div class="ed-prev"><div class="lbl" style="margin-bottom:8px">Preview</div><div id="ed-preview"></div>
          <div class="ed-actions"><button class="btn btn-primary" id="ed-save" disabled>Save changes</button><button class="btn btn-secondary" id="ed-reset" title="Put everything back to the plain defaults">${icon_('arrow-counter-clockwise')} Reset to defaults</button></div>
          <p class="muted" id="ed-msg" style="min-height:20px;margin:8px 0 0;font-size:13px" role="status"></p></div>
        <div class="ed-ctl"><div class="ed-mini" id="ed-mini"></div>
          <div class="card-box pad ed-sec"><h3>Picture</h3>
            <div class="upl"><label class="btn btn-secondary btn-sm" for="up-file">${icon_('upload-simple')} Upload a picture</label><input type="file" id="up-file" accept="image/png,image/jpeg,image/webp" hidden>
              ${upload ? '<button type="button" class="btn btn-ghost btn-sm" id="up-del">Remove my upload</button>' : ''}<span class="muted" style="font-size:12.5px">PNG, JPEG or WebP. It is squared up and shrunk on your device first; the server then checks what is really inside the file.</span></div>
            <div class="picks" id="o-avatar">${optionHtml('avatar')}</div></div>
          <div class="card-box pad ed-sec"><h3>Frame</h3><div class="picks" id="o-frame">${optionHtml('frame')}</div></div>
          <div class="card-box pad ed-sec"><h3>Badge</h3><div class="picks" id="o-badge">${optionHtml('badge')}</div></div>
          <div class="card-box pad ed-sec"><h3>Title</h3><div class="picks" id="o-title">${optionHtml('title')}</div></div>
          <div class="card-box pad ed-sec"><h3>Banner</h3><div class="picks" id="o-banner">${optionHtml('banner')}</div></div>
          <div class="card-box pad ed-sec"><h3>Accent colour</h3><div class="picks" id="o-accent">${optionHtml('accent')}</div><p class="muted" style="margin:8px 0 0;font-size:12.5px">Some colours are too hard to read on some backgrounds. Clique will say so instead of saving a profile nobody can read.</p></div>
          <div class="card-box pad ed-sec"><h3>Profile background</h3><div class="picks" id="o-bg">${bgHtml()}</div></div>
          <div class="card-box pad ed-sec"><h3>Name font</h3><div class="picks" id="o-font">${optionHtml('font')}</div></div>
          <div class="card-box pad ed-sec"><h3>About you</h3><textarea class="input" id="ed-bio" rows="3" maxlength="140" placeholder="One line about you. Plain text.">${esc(sel.bio)}</textarea><div class="muted" style="text-align:right;font-size:12px"><span id="bio-n">${140 - sel.bio.length}</span> left</div></div>
        </div></div></div>`;
    paintPreview();
  }
  const icon_ = (n) => (ICON[n] || '');

  const flash = (text, bad) => { const m = root.querySelector('#ed-msg'); if (m) { m.textContent = text; m.className = bad ? 'error-text' : 'muted'; } };
  const refreshAll = async () => { const [a, b] = await Promise.all([get('/api/profile'), get('/api/store')]); P = a.profile; Object.assign(store, b); items.length = 0; items.push(...b.items); for (const i of items) byId[i.id] = i; upload = P.upload; };

  root.addEventListener('click', async (e) => {
    const o = e.target.closest('.pick');
    if (o) {
      if (o.dataset.store) { toast('That one is not yours yet. You can get it in the Store.', '', { onClick: () => go(`#/store/${byId[o.dataset.id].kind}`), ms: 5000 }); return; }
      if (o.dataset.slot) { sel[o.dataset.slot] = o.dataset.id; }
      else if (o.dataset.bg) { sel.bg = o.dataset.bg; }
      else return;
      const parent = o.parentElement; parent.querySelectorAll('.pick').forEach((x) => { const on = x === o; x.classList.toggle('on', on); x.setAttribute('aria-pressed', String(on)); });
      paintPreview(); flash(''); return;
    }
    const b = e.target.closest('button'); if (!b) return;
    if (b.id === 'ed-mini-save') { root.querySelector('#ed-save').click(); return; }     // the pinned bar's Save is the same Save
    try {
      if (b.id === 'ed-save') {
        b.disabled = true;
        const body = { ...Object.fromEntries(SLOT_ORDER.map((k) => [k, sel[k]])), bg: sel.bg, bio: sel.bio };
        const d = await post('/api/profile', body);
        P = d.profile; sel.bg = P.bg; setLook(S.user.username, P.style); await refreshAll();
        flash('Saved. This is how everybody sees you now.'); paintPreview(); setUser({ ...S.user });
      } else if (b.id === 'ed-reset') {
        const d = await post('/api/profile', { reset: true });
        P = d.profile; Object.assign(sel, P.slots, { bg: P.bg, bio: P.bio }); setLook(S.user.username, P.style); await refreshAll(); draw(); flash('Back to the defaults. Everything you bought is still yours.'); setUser({ ...S.user });
      } else if (b.id === 'up-del') {
        const d = await del('/api/profile/avatar'); P = d.profile; setLook(S.user.username, P.style); await refreshAll(); if (sel.avatar === 'upload') sel.avatar = P.slots.avatar; draw(); flash('Your uploaded picture is gone.'); setUser({ ...S.user });
      }
    } catch (ex) { flash(ex.message, true); const s = root.querySelector('#ed-save'); if (s) s.disabled = !dirty(); }
  });
  root.addEventListener('input', (e) => { if (e.target.id === 'ed-bio') { sel.bio = e.target.value; paintPreview(); flash(''); } });
  root.addEventListener('change', async (e) => {
    if (e.target.id !== 'up-file' || !e.target.files[0]) return;
    const file = e.target.files[0];
    flash('Checking your picture…');
    try {
      const blob = await squareUp(file);
      const res = await fetch('/api/profile/avatar', { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob, credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'That picture was not accepted.');
      P = data.profile; sel.avatar = 'upload'; setLook(S.user.username, P.style); await refreshAll(); draw(); flash('Uploaded. Press Save to keep the other changes you made.'); setUser({ ...S.user });
    } catch (ex) { flash(ex.message, true); }
    e.target.value = '';
  });
  draw();
  return guard;
}

/** Crops a picture to a square and shrinks it to at most 320 pixels, so the upload is small and fast. The server checks it again. */
async function squareUp(file) {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) throw new Error('Choose a PNG, JPEG or WebP picture.');
  if (file.size > 12 * 1024 * 1024) throw new Error('That file is huge. Pick a smaller picture.');
  let bmp;
  try { bmp = await createImageBitmap(file); } catch { throw new Error('That file could not be opened as a picture.'); }
  const side = Math.min(bmp.width, bmp.height), out = Math.min(320, side);
  if (side < 64) throw new Error('That picture is too small. Use one at least 64 pixels wide and tall.');
  const c = document.createElement('canvas'); c.width = c.height = out;
  c.getContext('2d').drawImage(bmp, (bmp.width - side) / 2, (bmp.height - side) / 2, side, side, 0, 0, out, out);
  const pick = (type, q) => new Promise((r) => c.toBlob((b) => r(b && b.type === type ? b : null), type, q));
  return (await pick('image/webp', 0.88)) || (await pick('image/png')) || (() => { throw new Error('Your browser could not prepare that picture.'); })();
}
