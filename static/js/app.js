import { get, post, setUnauthorizedHandler } from './api.js';
import { S, bus, go, refreshMe, setUser, loadCircles } from './state.js';
import { avatar, money, moneyFull, esc, ICON, debounce, parseAmount, roll, cents, until } from './util.js';
import { toast, modal, revealPasswords, confirmBox } from './ui.js';
import { GAME_LIST, gameName } from './gamelist.js';
import { logoMark, sticker, gameSticker, rankBadge } from './art.js';
import { titleHtml, setLook } from './looks.js';
import { icon } from './icons.js';
import { startPresence, stopPresence, refreshBadges, paintBadges, onSocialEvent } from './social.js';
import { voice } from './voice.js';
import * as nav from './viewstate.js';
import { startLayout } from './layout.js';
import { initLang, onLang } from './i18n.js';

let emailAsking = false, emailModalClose = null;       // the window that asks for an email (see openEmailModal), declared up here so every function can see it

const $app = document.getElementById('app');
let current = null;        // the mounted view
let stream = null;
let routeSeq = 0;
let shellReady = false;

const ROUTES = [
  [/^\/?$/, () => import('./views/markets.js')],
  [/^\/market\/(\w+)$/, () => import('./views/market.js')],
  [/^\/create$/, () => import('./views/create.js')],
  [/^\/circles$/, () => import('./views/circles.js')],
  [/^\/circle\/(\w+)$/, () => import('./views/circle.js')],
  [/^\/weekly(?:\/(\w+))?$/, () => import('./views/weekly.js')],
  [/^\/games$/, () => import('./views/games.js')],
  [/^\/games\/(\w+)$/, () => import('./views/game.js')],
  [/^\/friends$/, () => import('./views/friends.js')],
  [/^\/chat(?:\/(\w+))?$/, () => import('./views/chat.js')],
  [/^\/poker$/, () => import('./views/poker.js')],
  [/^\/poker\/(\w+)$/, () => import('./views/pokertable.js')],
  [/^\/u\/(\w+)(?:\/(edit))?$/, () => import('./views/profile.js')],
  [/^\/portfolio$/, () => import('./views/portfolio.js')],
  [/^\/exchange$/, () => import('./views/exchange.js')],
  [/^\/exchange\/(\w+)$/, () => import('./views/exchange.js')],
  [/^\/store(?:\/(\w+))?$/, () => import('./views/store.js')],
  [/^\/statement$/, () => import('./views/statement.js')],
  [/^\/challenges$/, () => import('./views/challenges.js')],
  [/^\/progress$/, () => import('./views/progress.js')],
  [/^\/loans$/, () => import('./views/loans.js')],
  [/^\/transfers$/, () => import('./views/transfers.js')],
  [/^\/ranking$/, () => import('./views/ranking.js')],
  [/^\/diseno$/, () => import('./views/diseno.js')],              // E4's sample page: reachable at /diseno, on purpose not in any menu
];

const TAGLINES = {
  circles: 'The circles // who you lose to',
  weekly: 'The weekly // somebody pays for this',
  ledger: 'The ledger // your receipts',
  social: 'Friends & chat // the people you lose to',
  exchange: 'The exchange // pretend shares, real feelings',
  store: 'The store // spend what you keep',
};

// ---------------------------------------------------------------- auth screen
let authMode = 'login';
function showAuth(mode = 'login') {
  authMode = mode;
  if (emailModalClose) emailModalClose();              // a log-out or an expired session must not leave the email window sitting over the log-in form
  closeStream(); stopPresence();
  current?.unmount?.(); current = null; shellReady = false;
  const login = mode === 'login';
  $app.innerHTML = `
  <div class="auth">
    <div class="auth-side">
      <a class="wordmark" href="#/">${logoMark(40)}<span>clique</span></a>
      <h1>Your friends think they know things.<br><em>Make them pay for it.</em></h1>
      <p>Private betting for people who can't stop arguing. Play money, real bragging rights.</p>
      <div class="auth-stickers">${sticker('crown', { size: 84, bg: 'lime', rot: -8 })}${sticker('chips', { size: 84, bg: 'felt', rot: 5 })}${sticker('ghost', { size: 84, bg: 'verm', rot: -3 })}</div>
    </div>
    <form class="auth-card paper" id="auth-form" autocomplete="on">
      <span class="lbl">${login ? 'Member entrance' : 'New member'}</span>
      <h2>${login ? 'Back again?' : 'Pull up a chair.'}</h2>
      <p class="lede">${login ? 'Log in. Your balance missed you. Your friends did not.' : '$1,000 of pretend money, on the house. Spend it badly.'}</p>
      <div class="field"><label for="au">Username</label><input class="input" id="au" name="username" autocomplete="username" maxlength="20" required placeholder="the_oracle"></div>
      ${login ? '' : '<div class="field"><label for="ae">Email</label><input class="input" id="ae" name="email" type="email" autocomplete="email" required placeholder="you@example.com"><small class="muted" style="display:block;margin-top:5px">So you can reset your password if you forget it. Nobody else sees it.</small></div>'}
      <div class="field"><label for="ap">Password</label><input class="input" id="ap" name="password" type="password" autocomplete="${login ? 'current-password' : 'new-password'}" required placeholder="6+ characters"></div>
      <div class="error-text" id="auth-err" style="min-height:20px;margin-bottom:10px"></div>
      <button class="btn btn-primary btn-lg btn-block" id="auth-go">${login ? 'Let me in' : 'Deal me in'}</button>
      <p class="auth-swap">${login ? 'No seat yet? <a href="#" id="swap">Get one</a>' : 'Already seated? <a href="#" id="swap">Log in</a>'}</p>
      ${login ? '<p class="auth-swap"><a href="#" id="forgot">Forgot your password?</a></p>' : ''}
    </form>
  </div>`;
  revealPasswords($app);
  const forgot = document.getElementById('forgot');
  if (forgot) forgot.addEventListener('click', (e) => { e.preventDefault(); openReset(); });
  document.getElementById('swap').addEventListener('click', (e) => { e.preventDefault(); showAuth(login ? 'signup' : 'login'); });
  document.getElementById('auth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('auth-go'); const err = document.getElementById('auth-err');
    btn.disabled = true; err.textContent = '';
    try {
      const body = { username: document.getElementById('au').value.trim(), password: document.getElementById('ap').value };
      if (!login) body.email = document.getElementById('ae').value.trim();
      const d = await post(login ? '/api/auth/login' : '/api/auth/register', body);
      await refreshMe();
      startApp();
      if (!login) toast(`You're in, ${d.user.username}. ${money(d.user.balance)} of pretend money. Make bad decisions.`, 'ok', { ms: 4800 });
    } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
  });
}

// ---------------------------------------------------------------- the shell (one for every page)
const avatarMenuHtml = '<div class="relative"><button class="avatar-btn" id="btn-avatar" aria-label="Account menu"></button><div class="menu hidden" id="user-menu"></div></div>';

function shellHtml() {
  return `
  <header class="top" id="top">
    <div class="top-bar">
    <div class="top-main">
      <a href="#/" class="wordmark" aria-label="Clique home">${logoMark(34)}<span>clique</span></a>
      <nav class="sections" id="sections" aria-label="Sections">
        <a class="sec" data-sec="markets" href="#/">Markets</a>
        <a class="sec" data-sec="casino" href="#/games">Casino</a>
        <a class="sec" data-sec="exchange" href="#/exchange">Exchange</a>
        <a class="sec" data-sec="store" href="#/store">Store</a>
        <a class="sec" data-sec="circles" href="#/circles">Circles</a>
        <a class="sec" data-sec="weekly" href="#/weekly">Weekly</a>
      </nav>
      <div class="top-right">
        <div class="search hide-md">${ICON.search}<input id="gsearch" placeholder="SEARCH MARKETS" autocomplete="off" aria-label="Search markets"><kbd>/</kbd></div>
        <a class="btn btn-sm hide-sm" href="#/create">${ICON.plus} Propose</a>
        <a class="icon-nav" id="btn-friends" href="#/friends" aria-label="Friends" title="Friends">${icon('users-three', 21)}<span class="nbadge online hidden" data-badge="friends"></span></a>
        <a class="icon-nav" id="btn-chat" href="#/chat" aria-label="Chat" title="Chat">${icon('chat-circle', 21)}<span class="nbadge hidden" data-badge="chat"></span></a>
        <a class="balance" href="#/statement" id="balance" aria-label="Your two accounts. Open the statement." title="Weekly: this week's chips for bets and the casino. Accumulated: what you keep, for the Store and the Exchange. Click for the statement.">
          <div><span class="lbl">Weekly</span><b class="num" data-w="cash"></b></div>
          <div><span class="lbl"><span class="full">Accumulated</span><span class="short">Saved</span></span><b class="num" data-w="accum"></b></div>
        </a>
        <button class="btn btn-primary btn-sm" id="btn-deposit"><span class="dep-add">Add </span>funds</button>
        ${avatarMenuHtml}
      </div>
    </div>
    </div>
    <div class="top-rest">
    <div class="subnav" id="subnav"></div>
    <div class="voucher-bar" id="voucher-bar" role="status"></div>
    </div>
    <div class="search-mobile"><input id="gsearch-m" placeholder="SEARCH MARKETS" autocomplete="off" aria-label="Search markets"></div>
    <div class="ticker" id="ticker" aria-label="Live wins and odds"><div class="ticker-track" id="ticker-track"></div></div>
  </header>
  <main id="view"></main>`;
}

function ensureShell() {
  if (shellReady && document.getElementById('view')) return;
  shellReady = true;
  $app.innerHTML = shellHtml();
  renderWallet(true); renderMenu(); renderVoucher(); announcePassGo(); paintBadges();
  document.getElementById('btn-deposit').addEventListener('click', openDeposit);
  document.getElementById('voucher-bar').addEventListener('click', redeemVoucher);
  document.getElementById('btn-avatar').addEventListener('click', (e) => { e.stopPropagation(); document.getElementById('user-menu').classList.toggle('hidden'); });
  const onSearch = debounce((e) => {
    const v = e.target.value;
    document.getElementById('gsearch').value = v; document.getElementById('gsearch-m').value = v;
    S.search = v;
    if (!/^#\/?(\?.*)?$/.test(location.hash)) location.hash = '#/'; else bus.dispatchEvent(new Event('search'));
  }, 200);
  document.getElementById('gsearch').addEventListener('input', onSearch);
  document.getElementById('gsearch-m').addEventListener('input', onSearch);
  refreshTicker();
  startLayout();                         // measures the header and the voice bar and keeps the CSS informed (layout.js)
}

function sectionOf(path) {
  if (/^\/(games|poker)/.test(path)) return 'casino';
  if (/^\/exchange/.test(path)) return 'exchange';
  if (/^\/store/.test(path)) return 'store';
  if (/^\/circles?/.test(path)) return 'circles';
  if (/^\/weekly/.test(path)) return 'weekly';
  if (/^\/(friends|chat)/.test(path)) return 'social';
  if (/^\/(u\/|portfolio|statement|challenges|progress|loans|transfers|ranking)/.test(path)) return 'ledger';
  return 'markets';
}

function subnavHtml(sec, path, query) {
  if (sec === 'markets') {
    const onHome = /^\/?$/.test(path);
    const cat = onHome ? query.get('cat') : null;
    const tab = onHome && !cat ? (query.get('tab') || 'trending') : null;
    const TABS = [['trending', 'Trending', ICON.trend], ['new', 'New', ''], ['ending', 'Ending soon', ''], ['resolved', 'Settled', '']];
    return `<div class="subnav-in">${TABS.map(([k, l, ic]) => `<a class="sub ${tab === k ? 'on' : ''}" href="${k === 'trending' ? '#/' : '#/?tab=' + k}">${ic}${l}</a>`).join('')}
      <span class="sub-sep"></span>${S.categories.map((c) => `<a class="sub ${cat === c ? 'on' : ''}" href="#/?cat=${encodeURIComponent(c)}">${esc(c)}</a>`).join('')}</div>`;
  }
  if (sec === 'casino') {
    const m = path.match(/^\/games\/(\w+)/); const key = m ? m[1] : /^\/poker/.test(path) ? 'poker' : 'lobby';
    return `<div class="subnav-in"><a class="sub ${key === 'lobby' ? 'on' : ''}" href="#/games">Lobby</a>
      ${GAME_LIST.map((g) => `<a class="sub ${key === g.id ? 'on' : ''}" href="${g.href || '#/games/' + g.id}"><span class="sub-ico">${gameSticker(g.id, 26)}</span>${esc(g.name)}</a>`).join('')}
      <span class="nav-spacer"></span>
      <div class="profit hide-sm"><span class="lbl">Today</span><b class="num" id="st-today">$0</b><span class="lbl">Week</span><b class="num" id="st-week">$0</b><span class="lbl">All time</span><b class="num" id="st-total">$0</b></div></div>`;
  }
  if (sec === 'exchange') {
    const sym = (path.match(/^\/exchange\/(\w+)/) || [])[1];
    return `<div class="subnav-in"><a class="sub ${!sym ? 'on' : ''}" href="#/exchange">Market</a><a class="sub ${sym === 'portfolio' ? 'on' : ''}" href="#/exchange/portfolio">My portfolio</a>
      <span class="sub-sep"></span><span class="sub-kicker">Simulated companies. Prices are the same for everyone. Paid from the accumulated account.</span></div>`;
  }
  if (sec === 'ledger' && S.user) {
    const me = esc(S.user.username);
    const L = [['profile', `#/u/${me}`, 'Profile', /^\/u\//.test(path)], ['portfolio', '#/portfolio', 'Portfolio', /^\/portfolio/.test(path)], ['statement', '#/statement', 'Statement', /^\/statement/.test(path)],
      ['challenges', '#/challenges', 'Challenges', /^\/challenges/.test(path)], ['progress', '#/progress', 'Rank & milestones', /^\/progress/.test(path)], ['loans', '#/loans', 'Loans', /^\/loans/.test(path)], ['transfers', '#/transfers', 'Transfers', /^\/transfers/.test(path)], ['ranking', '#/ranking', 'Global ranking', /^\/ranking/.test(path)]];
    return `<div class="subnav-in">${L.map(([k, href, label, on]) => `<a class="sub ${on ? 'on' : ''}" href="${href}">${esc(label)}</a>`).join('')}</div>`;
  }
  return `<div class="subnav-in"><span class="sub-kicker">${esc(TAGLINES[sec] || '')}</span></div>`;
}

let lastCash = null;
function renderWallet(first = false) {
  const u = S.user; if (!u) return;
  document.querySelectorAll('[data-w="cash"]').forEach((el) => {
    roll(el, money(u.balance)); el.title = moneyFull(u.balance);
    if (!first && lastCash !== null && u.balance !== lastCash) {
      el.classList.remove('flash-up', 'flash-down'); void el.offsetWidth; el.classList.add(u.balance > lastCash ? 'flash-up' : 'flash-down');
    }
  });
  document.querySelectorAll('[data-w="accum"]').forEach((el) => {
    const before = el.dataset.raw === undefined ? null : Number(el.dataset.raw);
    roll(el, money(u.accum || 0)); el.title = moneyFull(u.accum || 0); el.dataset.raw = String(u.accum || 0);
    if (!first && before !== null && before !== (u.accum || 0)) { el.classList.remove('flash-up', 'flash-down'); void el.offsetWidth; el.classList.add((u.accum || 0) > before ? 'flash-up' : 'flash-down'); }
  });
  lastCash = u.balance;
  const av = document.getElementById('btn-avatar'); if (av) av.innerHTML = avatar(u.username, 36);
  const who = document.querySelector('#user-menu .who'); if (who) renderMenu();
}

// ---- the rescue voucher, and the "you passed Go" notice
function renderVoucher() {
  const bar = document.getElementById('voucher-bar'), u = S.user, v = u && u.voucher;
  if (!bar) return;
  if (v && v.eligible) {
    bar.className = 'voucher-bar on';
    bar.innerHTML = `<span class="vb-tag">Out of chips</span><span class="vb-msg">Your weekly voucher is waiting: <b>${money(v.amount)}</b> for your weekly account. One per week.</span><button class="btn btn-sm vb-btn" id="vb-go">Redeem ${money(v.amount)}</button>`;
  } else if (v && v.used && !v.busy && u.balance < v.below) {
    bar.className = 'voucher-bar used';
    bar.innerHTML = `<span class="vb-tag">Tapped out</span><span class="vb-msg">You already used this week's voucher. ${v.goAmount > 0 ? `Your weekly account refills to <b>${money(v.goAmount)}</b> in ${until(v.resetsAt)}.` : `A fresh one turns up in ${until(v.resetsAt)}.`}</span>`;
  } else { bar.className = 'voucher-bar'; bar.innerHTML = ''; }
}
async function redeemVoucher(e) {
  const btn = e.target.closest('#vb-go'); if (!btn) return;
  btn.disabled = true;
  try {
    const d = await post('/api/wallet/voucher');
    setUser(d.user);
    toast(`Voucher cashed: ${money(d.added)} on the house. Try to make it last.`, 'ok', { ms: 5000 });
  } catch (ex) { toast(ex.message, 'err'); btn.disabled = false; refreshMe().catch(() => {}); }
}
function announcePassGo() {
  const g = S.user && S.user.passGo; if (!g) return;
  const key = 'clique-go-' + S.user.username;
  try { if (localStorage.getItem(key) === g.week) return; localStorage.setItem(key, g.week); } catch { /* storage blocked: show it, it is harmless */ }
  toast(`New week. Your weekly account is set up again: ${money(g.amount)} to play with.`, 'ok', { ms: 7000 });
}

const signed = (x) => `<span class="${x > 0 ? 'up' : x < 0 ? 'down' : ''}">${money(x, { plus: true, noCents: Math.abs(x) >= 1000 })}</span>`;
async function refreshProfit() {
  if (!document.getElementById('st-today')) return;
  try {
    const d = await get('/api/games/summary');
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.innerHTML = signed(v); };
    set('st-today', d.today); set('st-week', d.week); set('st-total', d.total);
  } catch { /* ignore */ }
}
const refreshProfitSoon = debounce(refreshProfit, 900);

// ---------------------------------------------------------------- ticker
const trunc = (t, n) => (t.length > n ? t.slice(0, n - 1) + '…' : t);
async function refreshTicker() {
  const track = document.getElementById('ticker-track'); if (!track) return;
  let wins = [], mk = [];
  try { wins = (await get('/api/games/feed')).feed.slice(0, 8); } catch { /* ignore */ }
  try { mk = (await get('/api/markets?status=open&sort=trending')).markets.slice(0, 7); } catch { /* ignore */ }
  const items = [];
  wins.forEach((w) => items.push(`<span class="tk"><b>${esc(w.user)}</b> won on ${esc(gameName(w.game))} <span class="num">${w.mult.toLocaleString()}x</span> <b class="up num">${money(w.profit, { plus: true })}</b></span>`));
  mk.forEach((m) => {
    const yn = m.binary && m.outcomes[0].name === 'Yes';
    const lead = m.outcomes.reduce((a, b) => (b.yes > a.yes ? b : a));
    const label = yn ? 'YES' : esc(trunc(lead.name, 14));
    const p = yn ? m.outcomes[0].yes : lead.yes;
    items.push(`<span class="tk">${esc(trunc(m.question, 44))} <b class="num ${p >= 0.5 ? 'up' : 'down'}">${label} ${cents(p)}</b></span>`);      // html: seguro (label es 'YES' o ya pasó por esc())
  });
  if (!items.length) items.push('<span class="tk">Quiet night. Nobody has lost anything yet. Give it time.</span>', '<span class="tk">Propose a bet. Put money on it. Regret it.</span>');
  const html = items.join('<i class="tk-sep"></i>') + '<i class="tk-sep"></i>';
  track.innerHTML = html + html;
  track.style.setProperty('--dur', Math.max(36, Math.round(items.join('').length / 9)) + 's');
}
const refreshTickerSoon = debounce(refreshTicker, 2500);

// ---------------------------------------------------------------- account menu + deposit
async function logOut() {
  try { await voice.hangUp(); } catch { /* leaving anyway */ }
  await post('/api/auth/logout'); setUser(null); location.hash = '#/'; showAuth('login');
}

function renderMenu() {
  const u = S.user;
  document.getElementById('user-menu').innerHTML = `
    <div class="who">${avatar(u.username, 40)}<div><b>${esc(u.username)}</b>${u.rank ? `<span class="rkt" title="${esc(u.rank.l)}">${rankBadge(u.rank, 18)}</span>` : ''}${titleHtml(u.username)}<div class="mono muted" style="font-size:12px">Weekly ${money(u.balance)} · Saved ${money(u.accum || 0)}</div></div></div><hr>
    <a href="#/games">${ICON.dice} Casino</a><a href="#/exchange">${ICON.trend} Exchange</a><a href="#/store">${ICON.coins} Store</a><a href="#/circles">${ICON.users} Circles</a><a href="#/friends">${ICON.user} Friends</a><a href="#/chat">${ICON.chat} Chat</a><a href="#/weekly">${ICON.cal} Weekly</a><a href="#/create">${ICON.plus} Propose a bet</a><hr>
    <a href="#/u/${esc(u.username)}">${ICON.user} Profile & awards</a>
    <a href="#/u/${esc(u.username)}/edit">${ICON.pencil} Customize profile</a>
    <a href="#/portfolio">${ICON.wallet} Portfolio</a>
    <a href="#/statement">${ICON.clockc} Statement</a>
    <a href="#/challenges">${ICON.trophy} Challenges${u.unseen ? ` <span class="nbadge" style="position:static;display:inline-block;vertical-align:1px;margin-left:4px">${u.unseen}</span>` : ''}</a>
    <a href="#/progress">${ICON.crown} Rank &amp; milestones</a>
    <a href="#/loans">${ICON.coins} Loans${u.debt ? ` <span class="mono muted" style="font-size:12px">(owe ${money(u.debt)})</span>` : ''}</a>
    <a href="#/transfers">${ICON.arrowR} Transfers</a>
    <a href="#/ranking">${ICON.trend} Global ranking</a>
    <button id="m-email">${ICON.lock} Email${u.email && u.email.address ? (u.email.verified ? ' (confirmed)' : ' (not confirmed)') : ' (add one)'}</button>
    <button id="m-theme">${ICON.moon} Switch theme</button><hr>
    <button id="m-out">${ICON.out} Log out</button>`;
  document.getElementById('m-theme').addEventListener('click', () => {
    const t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('clique-theme', t); } catch { /* ignore */ }
    bus.dispatchEvent(new Event('theme'));
  });
  document.getElementById('m-out').addEventListener('click', logOut);
  document.getElementById('m-email').addEventListener('click', (e) => { e.stopPropagation(); document.getElementById('user-menu').classList.add('hidden'); openEmailModal({ forced: false }); });
  document.getElementById('user-menu').addEventListener('click', () => document.getElementById('user-menu').classList.add('hidden'));
}
document.addEventListener('click', () => document.getElementById('user-menu')?.classList.add('hidden'));
document.addEventListener('keydown', (e) => {
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '') && S.user) { e.preventDefault(); document.getElementById('gsearch')?.focus(); }
});

bus.addEventListener('user', (e) => { if (e.detail && e.detail.demo) return; if (S.user) { renderWallet(); renderVoucher(); announcePassGo(); refreshProfitSoon(); } });

/** Locked out: the funds password lets the person who runs the site set a new password for anyone. */
/* "Forgot your password?": a 6-digit code sent to the email on the account; or, for accounts with no email, the funds password. */
function openReset() {
  const typed = (document.getElementById('au') || {}).value || '';
  const m = modal('<div id="rs-box"></div>');
  const box = m.el.querySelector('#rs-box');
  let email = typed.includes('@') ? typed : '';
  const toFunds = () => { m.close(); openFundsReset(); };

  const stepEmail = () => {
    box.innerHTML = `<span class="lbl">Forgot your password?</span><h2>Reset it with your email</h2>
      <p class="lede">Type the email address on your account and we will send you a 6-digit code.</p>
      <form id="rs-form">
        <div class="field"><label for="rs-mail">Email</label><input class="input" id="rs-mail" type="email" autocomplete="email" required placeholder="you@example.com" value="${esc(email)}"></div>
        <div class="error-text" id="rs-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary" id="rs-go">Send me a code</button></div>
      </form>
      <p class="muted" style="font-size:13px;margin:14px 0 0">No email on your account yet? <a href="#" id="rs-funds">Ask whoever runs the site</a> (you will need the funds password).</p>`;
    box.querySelector('[data-close]').addEventListener('click', () => m.close());
    box.querySelector('#rs-funds').addEventListener('click', (e) => { e.preventDefault(); toFunds(); });
    box.querySelector('#rs-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#rs-err'), btn = box.querySelector('#rs-go');
      email = box.querySelector('#rs-mail').value.trim();
      btn.disabled = true; err.textContent = '';
      try { await post('/api/auth/forgot', { email }); stepCode(); } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };
  const stepCode = () => {
    box.innerHTML = `<span class="lbl">Check your email</span><h2>Type the code</h2>
      <p class="lede">If <b>${esc(email)}</b> belongs to an account, a 6-digit code is on its way. It can take a minute (look in spam too) and works for 15 minutes.</p>
      <form id="rs-form">
        <div class="field"><label for="rs-code">Code</label><input class="input" id="rs-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required placeholder="123456"></div>
        <div class="field"><label for="rs-new">New password</label><input class="input" id="rs-new" type="password" autocomplete="new-password" required placeholder="6+ characters"></div>
        <div class="error-text" id="rs-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" id="rs-back">Different email</button><button class="btn btn-primary" id="rs-go">Set the new password</button></div>
      </form>`;
    revealPasswords(box);
    box.querySelector('#rs-back').addEventListener('click', stepEmail);
    box.querySelector('#rs-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#rs-err'), btn = box.querySelector('#rs-go');
      btn.disabled = true; err.textContent = '';
      try {
        const d = await post('/api/auth/reset-by-email', { email, code: box.querySelector('#rs-code').value.trim(), newPassword: box.querySelector('#rs-new').value });
        m.close();
        const au = document.getElementById('au'), ap = document.getElementById('ap');
        if (au) au.value = d.username;
        if (ap) { ap.value = ''; ap.focus(); }
        toast(`New password set for ${d.username}. Log in with it.`, 'ok', { ms: 5200 });
      } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };
  stepEmail();
}

function openFundsReset() {
  const typed = (document.getElementById('au') || {}).value || '';
  const m = modal(`<span class="lbl">Locked out?</span><h2>Reset a password</h2><p class="lede">Nobody can see an old password, but the person who runs this site can set a new one. You need the funds password (the one for Add funds).</p>
    <form id="rs-form">
      <div class="field"><label for="rs-user">Username</label><input class="input" id="rs-user" autocomplete="username" maxlength="20" value="${esc(typed.includes('@') ? '' : typed)}"></div>
      <div class="field"><label for="rs-funds">Funds password</label><input class="input" id="rs-funds" type="password" autocomplete="off" placeholder="the funds password"></div>
      <div class="field"><label for="rs-new">New password</label><input class="input" id="rs-new" type="password" autocomplete="new-password" placeholder="6+ characters"></div>
      <div class="error-text" id="rs-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary" id="rs-go">Set the new password</button></div>
    </form>`);
  revealPasswords(m.el);
  m.el.querySelector('#rs-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = m.el.querySelector('#rs-err'), btn = m.el.querySelector('#rs-go');
    const username = m.el.querySelector('#rs-user').value.trim();
    if (!username) { err.textContent = 'Type the username first.'; return; }
    btn.disabled = true; err.textContent = '';
    try {
      const d = await post('/api/auth/reset', { username, fundsPassword: m.el.querySelector('#rs-funds').value, newPassword: m.el.querySelector('#rs-new').value });
      m.close();
      const au = document.getElementById('au'), ap = document.getElementById('ap');
      if (au) au.value = d.username;
      if (ap) { ap.value = ''; ap.focus(); }
      toast(`New password set for ${d.username}. Log in with it.`, 'ok', { ms: 4800 });
    } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
  });
}

// ---------------------------------------------------------------- the email on your account
/** Everybody must have an email on their account. Anybody who does not gets a window they cannot close until they give one
 *  (every time they open the site); an address that is not confirmed yet gets a gentler one, once per visit. */
function maybeAskForEmail() {
  const em = S.user && S.user.email;
  if (!em || emailAsking) return;
  let later = false; try { later = sessionStorage.getItem('clique-mail-later') === '1'; } catch { /* ignore */ }
  if (em.needed) openEmailModal({ forced: true });
  else if (!em.verified && em.delivery && !later) openEmailModal({ forced: false });
}

function openEmailModal({ forced }) {
  if (emailAsking) return;
  emailAsking = true;
  const m = modal('<div id="em-box"></div>', { locked: forced, onClose: () => { emailAsking = false; emailModalClose = null; } });
  const box = m.el.querySelector('#em-box');
  const em = () => S.user.email;
  const done = () => { emailAsking = false; emailModalClose = null; m.close(); };
  emailModalClose = done;
  const hint = () => em().preview ? '<p class="muted" style="font-size:13px;margin:10px 0 14px">This copy of the site is not connected to an email service, so the code is shown in the Terminal window where the site is running.</p>' : '';

  const stepEnter = (note = '') => {
    const changing = em().address && em().verified;
    box.innerHTML = `<span class="lbl">${forced ? 'One quick thing' : 'Your account'}</span><h2>${changing ? 'Change your email' : 'Add your email'}</h2>
      <p class="lede">${forced ? 'Everybody needs an email on their account now. ' : ''}If you ever forget your password, we will send a code to this address so you can set a new one. Nobody else can see it.</p>
      ${note}${''/* html: seguro (note es HTML del propio código; hoy nadie lo pasa) */}
      <form id="em-form">
        <div class="field"><label for="em-addr">Email</label><input class="input" id="em-addr" type="email" autocomplete="email" required placeholder="you@example.com" value="${esc(changing ? '' : (em().address || ''))}"></div>
        ${changing ? '<div class="field"><label for="em-pw">Your password</label><input class="input" id="em-pw" type="password" autocomplete="current-password" required placeholder="to make sure it is you"></div>' : ''}
        <div class="error-text" id="em-err" style="min-height:18px"></div>
        <div class="modal-actions">${forced ? '<button type="button" class="btn btn-ghost" id="em-out">Log out</button>' : '<button type="button" class="btn btn-secondary" data-close>Not now</button>'}<button class="btn btn-primary" id="em-go">Save email</button></div>
      </form>`;
    revealPasswords(box);
    box.querySelector('[data-close]')?.addEventListener('click', done);
    box.querySelector('#em-out')?.addEventListener('click', async () => { done(); await logOut(); });
    box.querySelector('#em-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#em-err'), btn = box.querySelector('#em-go');
      btn.disabled = true; err.textContent = '';
      try {
        await post('/api/me/email', { email: box.querySelector('#em-addr').value.trim(), password: box.querySelector('#em-pw')?.value });
        await refreshMe();
        if (em().delivery) stepVerify(); else stepSaved();
      } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };
  const stepSaved = () => {
    box.innerHTML = `<span class="lbl">Saved</span><h2>Thank you</h2><p class="lede">Your email is saved. As soon as this site can send email, you will be asked to confirm it with a code.</p>
      <div class="modal-actions"><button class="btn btn-primary" id="em-ok">Done</button></div>`;
    box.querySelector('#em-ok').addEventListener('click', done);
  };
  const stepVerify = (note = '') => {
    const target = em().pending || em().address;
    box.innerHTML = `<span class="lbl">Check your email</span><h2>Confirm it is yours</h2>
      <p class="lede">We sent a 6-digit code to <b>${esc(target)}</b>. It can take a minute (look in spam too). Type it here so the address can be used to reset your password.</p>
      ${hint()}${note}${''/* html: seguro (note es HTML del propio código; hoy nadie lo pasa) */}
      <form id="em-form">
        <div class="field"><label for="em-code">Code</label><input class="input" id="em-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required placeholder="123456"></div>
        <div class="error-text" id="em-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" id="em-later">Later</button><button class="btn btn-primary" id="em-go">Confirm</button></div>
      </form>
      <p class="muted" style="font-size:13px;margin:14px 0 0"><a href="#" id="em-resend">Send a new code</a> · <a href="#" id="em-change">Use a different email</a></p>`;
    box.querySelector('#em-later').addEventListener('click', () => { try { sessionStorage.setItem('clique-mail-later', '1'); } catch { /* ignore */ } done(); });
    box.querySelector('#em-change').addEventListener('click', (e) => { e.preventDefault(); stepEnter(); });
    box.querySelector('#em-resend').addEventListener('click', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#em-err');
      try { await post('/api/me/email/resend'); err.textContent = ''; toast('A new code is on its way.', 'ok'); } catch (ex) { err.textContent = ex.message; }
    });
    box.querySelector('#em-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#em-err'), btn = box.querySelector('#em-go');
      btn.disabled = true; err.textContent = '';
      try {
        await post('/api/me/email/verify', { code: box.querySelector('#em-code').value.trim() });
        await refreshMe();
        done();
        toast('Your email is confirmed. You can now reset your password with it if you ever forget it.', 'ok', { ms: 5200 });
      } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };

  const e0 = em();
  if (!e0.address) stepEnter();
  else if (!e0.verified || e0.pending) { if (e0.delivery) stepVerify(); else stepSaved(); }
  else stepEnter();                                   // a confirmed address: this is "change it"
}

function openDeposit() {
  const m = modal(`<span class="lbl">Cashier</span><h2>Add funds</h2><p class="lede">Know the password? Then the house is open. Any amount. But everybody else votes on it first: the money stays on hold until the vote ends.</p>
    <div class="note-box hidden" id="dep-hold"></div>
    <form id="dep-form">
      <div class="field"><label>Into which account?</label><div class="seg" role="radiogroup" aria-label="Account">
        <label class="seg-opt"><input type="radio" name="dep-acct" value="weekly" checked><span><b>Weekly</b><small>chips for bets and the casino. Never counts as winnings.</small></span></label>
        <label class="seg-opt"><input type="radio" name="dep-acct" value="accumulated"><span><b>Accumulated</b><small>for the Store and the Exchange.</small></span></label></div></div>
      <div class="field"><label for="dep-amt">Amount</label><input class="input num" id="dep-amt" inputmode="decimal" placeholder="5000" autocomplete="off"></div>
      <div class="chips" style="margin:-6px 0 16px">${[1000, 10000, 100000, 1000000].map((v) => `<button type="button" class="pill" data-v="${v}">+${money(v, { noCents: true })}</button>`).join('')}</div>
      <div class="field"><label for="dep-pw">Password</label><input class="input" id="dep-pw" type="password" autocomplete="off" placeholder="the funds password"></div>
      <div class="error-text" id="dep-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary" id="dep-go">Add the money</button></div>
    </form>`);
  revealPasswords(m.el);
  get('/api/fundvotes').then((d) => {                                   // funds of yours that are still waiting for a vote
    const open = (d.mine || []).find((x) => x.status === 'open');
    if (!open || !m.el.isConnected) return;
    const box = m.el.querySelector('#dep-hold');
    box.innerHTML = `<b>${money(open.amount)}</b> of yours is on hold for your ${open.account} account: ${open.voted} of ${open.total} have voted. You can add more once that vote ends.`;
    box.classList.remove('hidden'); m.el.querySelector('#dep-go').disabled = true;
  }).catch(() => {});
  m.el.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => { m.el.querySelector('#dep-amt').value = b.dataset.v; }));
  m.el.querySelector('#dep-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const amt = parseAmount(m.el.querySelector('#dep-amt').value), err = m.el.querySelector('#dep-err');
    if (!(amt > 0)) { err.textContent = 'Put in an amount first.'; return; }
    const btn = m.el.querySelector('#dep-go'); btn.disabled = true; err.textContent = '';
    try {
      const account = m.el.querySelector('input[name="dep-acct"]:checked').value;
      const d = await post('/api/wallet/deposit', { amount: amt, password: m.el.querySelector('#dep-pw').value, account });
      setUser(d.user); m.close();
      if (d.added) toast(`${money(d.added)} landed in your ${account} account.`, 'ok');          // (nobody else to ask)
      else toast(`${money(d.vote.amount)} is on hold. Everybody else is voting on it: it is added if more are in favor than against (the vote ends within ${Math.max(1, Math.round((d.vote.closesAt - Date.now()) / 3600000))} h).`, 'ok', { ms: 12000 });
    } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
  });
}

// ---------------------------------------------------------------- live updates
function startStream() {
  closeStream();
  stream = new EventSource('/api/stream');
  stream.onopen = () => voice.checkHealth();                  // the live stream (re)opened: make sure a call is still in the room
  stream.onmessage = (m) => {
    let ev; try { ev = JSON.parse(m.data); } catch { return; }
    onServerEvent(ev);
  };
}
function closeStream() { if (stream) { stream.close(); stream = null; } }

/** Notifications from the server (a promotion, a finished challenge, money from a friend...). One toast each; the person is not shown it twice. */
const NOTICE_GO = { promotion: '#/progress', milestone: '#/progress', challenge: '#/challenges', loan: '#/loans', transfer: '#/transfers', bonus: '#/statement', funds: '#/statement' };
function showNotice(item) {
  if (!item) return;
  if (item.kind === 'fundvote') { post('/api/inbox/seen', { ids: [item.id] }).catch(() => {}); checkFundVotes(); return; }      // a vote to cast: a pop-up, not a toast
  toast(`${item.title}${item.text ? ': ' + item.text : ''}`, item.kind === 'loan' ? 'err' : 'ok', { onClick: () => go(NOTICE_GO[item.kind] || '#/'), ms: 9000 });
  post('/api/inbox/seen', { ids: [item.id] }).catch(() => {});
  refreshMe().catch(() => {});
}
async function checkInbox() {
  try {
    const d = await get('/api/inbox');
    const fresh = d.items.filter((i) => !i.seen && i.kind !== 'fundvote');
    fresh.slice(0, 3).reverse().forEach((i) => toast(`${i.title}${i.text ? ': ' + i.text : ''}`, i.kind === 'loan' ? 'err' : 'ok', { onClick: () => go(NOTICE_GO[i.kind] || '#/'), ms: 9000 }));
    if (fresh.length > 3) toast(`…and ${fresh.length - 3} more notifications.`, '', { ms: 6000 });
    await post('/api/inbox/seen', {});
  } catch { /* the notifications are still there next time */ }
  checkFundVotes();                                                       // and any vote that is still waiting for this person
}

// ---- a vote on added funds (backend/fundvotes.py): somebody used "Add funds", and everybody else has to say yes or no
let askingVotes = false;
async function checkFundVotes() {
  if (askingVotes || !S.user) return;
  askingVotes = true;
  try {
    for (let i = 0; i < 20; i++) {                                        // one pop-up at a time, until nothing is waiting
      const d = await get('/api/fundvotes');
      if (!d.owed.length || !(await askFundVote(d.owed[0]))) break;
    }
  } catch { /* asked again the next time the app starts or a notification arrives */ }
  askingVotes = false;
}
function askFundVote(v) {
  return new Promise((resolve) => {
    const left = Math.max(0, v.closesAt - Date.now()), hrs = Math.floor(left / 3600000);
    const when = hrs >= 1 ? `${hrs} hour${hrs === 1 ? '' : 's'}` : `${Math.max(1, Math.round(left / 60000))} minutes`;
    const m = modal(`<span class="lbl">Funds vote</span><h2>${esc(v.username)} wants to add funds</h2>
      <p class="lede"><b>${esc(v.username)}</b> is adding <b>${money(v.amount)}</b> to their ${esc(v.account)} account. The money stays on hold until the vote ends. Are you in favor?</p>
      <div class="note-box">${v.voted} of ${v.total} have voted. The vote ends when the result cannot change, when everybody has voted, or in ${when}. More in favor than against and the money is added; anything else and it is not.</div>
      <div class="modal-actions"><button class="btn btn-no" id="fv-no">Against</button><button class="btn btn-primary" id="fv-yes">In favor</button></div>`, { locked: true });
    m.el.parentElement.classList.add('above-toasts');                    // (a notification must never sit on top of the two buttons of a window that cannot be closed)
    const answer = async (favor) => {
      m.el.querySelectorAll('button').forEach((b) => { b.disabled = true; });
      try { await post(`/api/fundvotes/${v.id}/vote`, { favor }); m.close(); toast('Your vote is counted.', 'ok'); resolve(true); }
      catch (ex) { m.close(); toast(ex.message, 'err'); resolve(/already ended/.test(ex.message)); }      // (a vote that is over: carry on to the next one)
    };
    m.el.querySelector('#fv-yes').addEventListener('click', () => answer(true));
    m.el.querySelector('#fv-no').addEventListener('click', () => answer(false));
  });
}

const refreshMeSoon = debounce(() => refreshMe().catch(() => {}), 400);
const SOCIAL_EVENTS = ['chat', 'chats', 'friends', 'presence', 'seen'];
function onServerEvent(ev) {
  if (ev.type === 'voice') { voice.onEvent(ev); current?.onEvent?.(ev); return; }            // calls live in voice.js, outside every page
  if (SOCIAL_EVENTS.includes(ev.type)) onSocialEvent(ev); else refreshMeSoon();
  if (ev.type === 'market') refreshTickerSoon();
  if (ev.type === 'market' && ev.action === 'created' && ev.by !== S.user?.username) {
    toast(`${ev.by} proposed: ${ev.question}`, '', { onClick: () => go(`#/market/${ev.id}`), ms: 5000 });
  }
  if (ev.type === 'market' && ev.action === 'resolved') toast(`Settled: ${ev.question}`, '', { onClick: () => go(`#/market/${ev.id}`), ms: 5000 });
  if (ev.type === 'week') toast('New week. Somebody owes somebody a punishment.', '', { onClick: () => go('#/weekly'), ms: 6000 });
  if (ev.type === 'reward') toast(`Weekly reward: ${money(ev.amount)} for finishing #${ev.position} in ${ev.circle}. It is in your accumulated account.`, 'ok', { onClick: () => go('#/weekly'), ms: 9000 });
  if (ev.type === 'weekwarn') toast(ev.text, 'err', { onClick: () => go('#/weekly'), ms: 15000 });
  if (ev.type === 'inbox') showNotice(ev.item);
  if (ev.type === 'market' && ev.action === 'edited' && ev.by !== S.user?.username) {
    toast(`${ev.by} ${ev.material ? 'changed the rules or date of' : 'clarified'}: ${ev.question}`, '', { onClick: () => go(`#/market/${ev.id}`), ms: 7000 });
  }
  current?.onEvent?.(ev);
}

// ---------------------------------------------------------------- router
function setActive(path, query) {
  const sec = sectionOf(path);
  document.querySelectorAll('#sections .sec').forEach((a) => a.classList.toggle('on', a.dataset.sec === sec));
  const strip = document.getElementById('sections'), here = strip && strip.querySelector('.sec.on');     // on a phone the tab row scrolls: keep the open section showing
  if (here) {
    const a = here.getBoundingClientRect(), b = strip.getBoundingClientRect();
    if (a.left < b.left || a.right > b.right) strip.scrollLeft += a.left - b.left - 16;
  }
  document.getElementById('subnav').innerHTML = subnavHtml(sec, path, query);
  document.getElementById('btn-friends')?.classList.toggle('on', /^\/friends/.test(path));
  document.getElementById('btn-chat')?.classList.toggle('on', /^\/chat/.test(path));
  if (sec === 'casino') refreshProfit();
}

// Where you came from, and the pages that get a "Back to ..." shortcut (everything that is a place you drill into).
let here = null, before = null;
const BACK_ON = /^\/(market\/|circle\/|games\/|poker\/|exchange\/|u\/|create|statement|store\/)/;
const WHERE = [[/^\/?$/, 'Markets'], [/^\/market\//, 'the bet'], [/^\/create/, 'the bet form'], [/^\/circles$/, 'Circles'], [/^\/circle\//, 'the circle'], [/^\/weekly/, 'the Weekly'],
  [/^\/games$/, 'the casino lobby'], [/^\/games\//, 'the game'], [/^\/poker/, 'poker'], [/^\/friends/, 'Friends'], [/^\/chat/, 'Chat'], [/^\/exchange$/, 'the Exchange'],
  [/^\/exchange\/portfolio/, 'your portfolio'], [/^\/exchange\//, 'the company'], [/^\/store/, 'the Store'], [/^\/statement/, 'your statement'], [/^\/portfolio/, 'your portfolio'], [/^\/challenges/, 'the challenges'], [/^\/progress/, 'your rank'], [/^\/loans/, 'your loans'], [/^\/transfers/, 'your transfers'], [/^\/u\//, 'the profile']];
const whereName = (p) => (WHERE.find(([rx]) => rx.test(p)) || [0, 'where you were'])[1];

async function route() {
  if (!S.user) return showAuth('login');
  const raw = location.hash.slice(1) || (location.pathname === '/diseno' ? '/diseno' : '/');      // /diseno is the one address without a #
  const [path, qs] = raw.split('?');
  const query = new URLSearchParams(qs || '');
  const seq = ++routeSeq;
  nav.leaving();                                     // remember how far the old screen was scrolled
  current?.unmount?.(); current = null;
  ensureShell();
  setActive(path, query);
  const old = document.getElementById('view');
  if (!old) return;
  const root = document.createElement('main');      // fresh container so old listeners vanish with the old page
  root.id = 'view';
  old.replaceWith(root);
  const arrival = nav.arrive();                      // a fresh visit, or Back/Forward to one we have seen
  if (here && here.path !== path) before = here;       // the page you came from (a tab or filter change on the same page keeps it)
  here = { path, hash: location.hash || '#/' };
  for (const [rx, loader] of ROUTES) {
    const m = path.match(rx);
    if (!m) continue;
    root.innerHTML = '<div class="spinner"></div>';
    try {
      const mod = await loader();
      if (seq !== routeSeq) return;
      root.innerHTML = '';
      const params = m.slice(1);
      current = (await mod.default.mount(root, params, query, path)) || null;
      if (seq !== routeSeq) { current?.unmount?.(); current = null; return; }
      addBackLink(root, path, arrival);
      nav.settle(arrival);                           // scroll back to where you were (or to the top for a fresh visit)
    } catch (ex) {
      console.error(ex);
      if (seq === routeSeq) root.innerHTML = `<div class="page">${errorBlock(ex.message)}</div>`;
    }
    return;
  }
  root.innerHTML = `<div class="page"><div class="empty"><div class="empty-art">${sticker('wheel', { size: 132, bg: 'verm' })}</div>
    <div class="empty-copy"><span class="kicker">Error 404</span><h3>That page lost everything on red.</h3><p>It put the whole stack on one spin and it's gone. So is whatever you were looking for.</p>
    <div class="btns"><a class="btn btn-primary" href="#/">Back to the action</a></div></div></div></div>`;
}

/** "Back to ..." on pages you drill into: goes back in history when that is where you came from, so the page you left is restored as it was. */
function addBackLink(root, path, arrival) {
  if (!BACK_ON.test(path) || !before || before.path === path) return;
  const page = root.querySelector('.page'); if (!page || page.querySelector('.back-to')) return;
  const a = document.createElement('a');
  a.className = 'back-to'; a.href = before.hash;
  a.innerHTML = `${ICON.chevL} Back to ${esc(whereName(before.path))}`;
  a.addEventListener('click', (e) => { e.preventDefault(); if (!arrival.revisit && history.length > 1) history.back(); else location.hash = before.hash; });
  page.prepend(a);
}

function errorBlock(message) {
  return `<div class="empty"><div class="empty-art">${sticker('warning', { size: 112, bg: 'lime' })}</div>
    <div class="empty-copy"><span class="kicker">Something broke</span><h3>The house made a mistake.</h3><p>${esc(message)}</p><div class="btns"><a class="btn btn-primary" href="#/">Back to the action</a></div></div></div>`;
}

function startApp() {
  shellReady = false;
  startStream();
  startPresence();
  checkInbox();
  refreshBadges();
  loadCircles().catch(() => {});
  route();
  maybeAskForEmail();
}

setUnauthorizedHandler(() => { voice.hangUp().catch(() => {}); setUser(null); showAuth('login'); });
// Leaving a form that has real unsaved changes: the page underneath is left exactly as it is while we ask.
let skipGuard = false;
window.addEventListener('hashchange', (e) => {
  if (!S.user) return;
  const g = !skipGuard && nav.unsaved();
  skipGuard = false;
  if (!g) { route(); return; }
  const target = new URL(e.newURL).hash, from = new URL(e.oldURL).hash || '#/';
  try { history.pushState({ cq: nav.entryNow() }, '', from); } catch { /* the address bar stays as it is */ }       // put the address back on the form: it never went anywhere
  confirmBox({ title: 'Leave without saving?', text: g.message, confirm: 'Leave', danger: true }).then((ok) => { if (ok) { skipGuard = true; location.hash = target; } });
});
window.addEventListener('beforeunload', closeStream);
setInterval(() => { if (S.user) refreshTicker(); }, 60000);

// A new language paints everything again, in place: no reload, and the screen keeps its scroll (viewstate.js sees the same entry).
onLang(() => {
  if (!S.user) { if (document.getElementById('auth-form')) showAuth(authMode); return; }
  shellReady = false;
  route();
});

(async function boot() {
  await initLang();                                  // before the first paint, so nobody sees the other language flash by
  try {
    const u = await refreshMe();
    if (u) startApp(); else showAuth('login');
  } catch (e) {
    $app.innerHTML = `<div class="auth"><form class="auth-card paper"><span class="lbl">No signal</span><h2>Can't reach the house.</h2><p class="lede">${esc(e.message)}</p><button type="button" class="btn btn-primary" id="retry">Try again</button></form></div>`;
    document.getElementById('retry').addEventListener('click', () => location.reload());
  }
})();
