import { get, post, setUnauthorizedHandler } from './api.js';
import { S, bus, go, refreshMe, setUser, loadCircles } from './state.js';
import { avatar, money, moneyFull, esc, ICON, debounce, parseAmount, roll, cents, until, num, catName } from './util.js';
import { toast, modal, revealPasswords, confirmBox } from './ui.js';
import { GAME_LIST, gameName } from './gamelist.js';
import { logoMark, sticker, gameSticker, rankBadge } from './art.js';
import { titleHtml, setLook } from './looks.js';
import { icon } from './icons.js';
import { startPresence, stopPresence, refreshBadges, paintBadges, onSocialEvent } from './social.js';
import { voice } from './voice.js';
import * as nav from './viewstate.js';
import { startLayout } from './layout.js';
import { initLang, onLang, t, th, tp } from './i18n.js';

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

/** An account's name in a sentence ("tu cuenta semanal"). */
const acctName = (a) => (a === 'accumulated' ? t('acumulada') : a === 'weekly' ? t('semanal') : a);      // i18n: no (server ids)

const TAGLINES = {                                 // i18n: claves ↓
  circles: 'Los círculos // contra quién pierdes',
  weekly: 'La semana // alguien va a pagar por esto',
  ledger: 'Tus cuentas // tus recibos',
  social: 'Amigos y chat // la gente contra la que pierdes',
  exchange: 'La bolsa // acciones de mentira, sentimientos de verdad',
  store: 'La tienda // gasta lo que guardas',
};                                                  // i18n: fin

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
      <h1>${t('Tus amigos creen que saben cosas.')}<br><em>${t('Haz que lo demuestren.')}</em></h1>
      <p>${t('Apuestas entre amigos que no paran de discutir. Las fichas son de juego; presumir es de verdad.')}</p>
      <div class="auth-stickers">${sticker('crown', { size: 84, bg: 'lime', rot: -8 })}${sticker('chips', { size: 84, bg: 'felt', rot: 5 })}${sticker('ghost', { size: 84, bg: 'verm', rot: -3 })}</div>
    </div>
    <form class="auth-card paper" id="auth-form" autocomplete="on">
      <span class="lbl">${login ? t('Entrada de socios') : t('Nuevo en el club')}</span>
      <h2>${login ? t('¿Otra vez por aquí?') : t('Acerca una silla.')}</h2>
      <p class="lede">${login ? t('Entra. Tus fichas te extrañaron. Tus amigos, no.') : t('{cantidad} en fichas de juego, cortesía de la casa. Gástalas mal.', { cantidad: money(1000, { noCents: true }) })}</p>
      <div class="field"><label for="au">${t('Usuario')}</label><input class="input" id="au" name="username" autocomplete="username" maxlength="20" required placeholder="${esc(t('el_oraculo'))}"></div>
      ${login ? '' : `<div class="field"><label for="ae">${t('Correo')}</label><input class="input" id="ae" name="email" type="email" autocomplete="email" required placeholder="${esc(t('tu@correo.com'))}"><small class="muted" style="display:block;margin-top:5px">${t('Para que recuperes tu contraseña si la olvidas. Nadie más lo ve.')}</small></div>`}
      <div class="field"><label for="ap">${t('Contraseña')}</label><input class="input" id="ap" name="password" type="password" autocomplete="${login ? 'current-password' : 'new-password'}" required placeholder="${esc(t('6 caracteres o más'))}"></div>
      <div class="error-text" id="auth-err" style="min-height:20px;margin-bottom:10px"></div>
      <button class="btn btn-primary btn-lg btn-block" id="auth-go">${login ? t('Entrar') : t('Crear mi cuenta')}</button>
      <p class="auth-swap">${login ? `${t('¿Aún no tienes lugar?')} <a href="#" id="swap">${t('Consigue uno')}</a>` : `${t('¿Ya tienes lugar?')} <a href="#" id="swap">${t('Entra')}</a>`}</p>
      ${login ? `<p class="auth-swap"><a href="#" id="forgot">${t('¿Olvidaste tu contraseña?')}</a></p>` : ''}
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
      if (!login) toast(t('Ya estás dentro, {nombre}. Tienes {cantidad} en fichas de juego. Toma malas decisiones.', { nombre: d.user.username, cantidad: money(d.user.balance) }), 'ok', { ms: 4800 });
    } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
  });
}

// ---------------------------------------------------------------- the shell (one for every page)
const avatarMenuHtml = () => `<div class="relative"><button class="avatar-btn" id="btn-avatar" aria-label="${esc(t('Menú de tu cuenta'))}"></button><div class="menu hidden" id="user-menu"></div></div>`;

function shellHtml() {
  return `
  <header class="top" id="top">
    <div class="top-bar">
    <div class="top-main">
      <a href="#/" class="wordmark" aria-label="${esc(t('Inicio de Clique'))}">${logoMark(34)}<span>clique</span></a>
      <nav class="sections" id="sections" aria-label="${esc(t('Secciones'))}">
        <a class="sec" data-sec="markets" href="#/">${t('Mercados')}</a>
        <a class="sec" data-sec="casino" href="#/games">${t('Casino')}</a>
        <a class="sec" data-sec="exchange" href="#/exchange">${t('Bolsa')}</a>
        <a class="sec" data-sec="store" href="#/store">${t('Tienda')}</a>
        <a class="sec" data-sec="circles" href="#/circles">${t('Círculos')}</a>
        <a class="sec" data-sec="weekly" href="#/weekly">${t('Semana')}</a>
      </nav>
      <div class="top-right">
        <div class="search hide-md">${ICON.search}<input id="gsearch" placeholder="${esc(t('BUSCAR MERCADOS'))}" autocomplete="off" aria-label="${esc(t('Buscar mercados'))}"><kbd>/</kbd></div>
        <a class="btn btn-sm hide-sm" href="#/create">${ICON.plus} ${t('Proponer')}</a>
        <a class="icon-nav" id="btn-friends" href="#/friends" aria-label="${esc(t('Amigos'))}" title="${esc(t('Amigos'))}">${icon('users-three', 21)}<span class="nbadge online hidden" data-badge="friends"></span></a>
        <a class="icon-nav" id="btn-chat" href="#/chat" aria-label="${esc(t('Chat'))}" title="${esc(t('Chat'))}">${icon('chat-circle', 21)}<span class="nbadge hidden" data-badge="chat"></span></a>
        <a class="balance" href="#/statement" id="balance" aria-label="${esc(t('Tus dos cuentas. Abre tu estado de cuenta.'))}" title="${esc(t('Semanal: las fichas de esta semana para apuestas y casino. Acumulada: lo que conservas, para la Tienda y la Bolsa. Haz clic para ver tu estado de cuenta.'))}">
          <div><span class="lbl">${t('Semanal')}</span><b class="num" data-w="cash"></b></div>
          <div><span class="lbl"><span class="full">${t('Acumulada')}</span><span class="short">${t('Acum.')}</span></span><b class="num" data-w="accum"></b></div>
        </a>
        <button class="btn btn-primary btn-sm" id="btn-deposit"><span class="dep-add">${t('Agregar')} </span>${t('fichas')}</button>
        ${avatarMenuHtml()}
      </div>
    </div>
    </div>
    <div class="top-rest">
    <div class="subnav" id="subnav"></div>
    <div class="voucher-bar" id="voucher-bar" role="status"></div>
    </div>
    <div class="search-mobile"><input id="gsearch-m" placeholder="${esc(t('BUSCAR MERCADOS'))}" autocomplete="off" aria-label="${esc(t('Buscar mercados'))}"></div>
    <div class="ticker" id="ticker" aria-label="${esc(t('Ganancias y probabilidades en vivo'))}"><div class="ticker-track" id="ticker-track"></div></div>
  </header>
  <main id="view"></main>
  ${tabbarHtml()}`;
}

/* The bar along the bottom on phones (F2): five places at most. Its look is E4's (.tabbar in the stylesheets); until that style exists
   (it announces itself with the --tabbar-h token) the bar stays hidden, so the page never shows it unstyled. */
const TABS = [                                     // i18n: claves ↓
  ['markets', '#/', 'trend-up', 'Mercados'], ['casino', '#/games', 'dice-five', 'Casino'], ['circles', '#/circles', 'users-three', 'Círculos'],
  ['weekly', '#/weekly', 'calendar-blank', 'Semana'], ['ledger', null, 'user', 'Tú']];      // i18n: fin
function tabbarHtml() {
  const me = S.user ? encodeURIComponent(S.user.username) : '';
  return `<nav class="tabbar hidden" id="tabbar" aria-label="${esc(t('Navegación principal'))}">${TABS.map(([sec, href, ic, label]) =>
    `<a class="tab" data-sec="${sec}" href="${href || '#/u/' + me}">${icon(ic, 22)}<span>${esc(t(label))}</span></a>`).join('')}</nav>`;
}
const tabbarStyled = () => !!getComputedStyle(document.documentElement).getPropertyValue('--tabbar-h').trim();

function ensureShell() {
  if (shellReady && document.getElementById('view')) return;
  shellReady = true;
  $app.innerHTML = shellHtml();
  if (tabbarStyled()) document.getElementById('tabbar').classList.remove('hidden');
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
    const SUBS = [['trending', t('En tendencia'), ICON.trend], ['new', t('Nuevos'), ''], ['ending', t('Cierran pronto'), ''], ['resolved', t('Resueltos'), '']];
    return `<div class="subnav-in">${SUBS.map(([k, l, ic]) => `<a class="sub ${tab === k ? 'on' : ''}" href="${k === 'trending' ? '#/' : '#/?tab=' + k}">${ic}${esc(l)}</a>`).join('')}
      <span class="sub-sep"></span>${S.categories.map((c) => `<a class="sub ${cat === c ? 'on' : ''}" href="#/?cat=${encodeURIComponent(c)}">${esc(catName(c))}</a>`).join('')}</div>`;
  }
  if (sec === 'casino') {
    const m = path.match(/^\/games\/(\w+)/); const key = m ? m[1] : /^\/poker/.test(path) ? 'poker' : 'lobby';
    return `<div class="subnav-in"><a class="sub ${key === 'lobby' ? 'on' : ''}" href="#/games">${t('Vestíbulo')}</a>
      ${GAME_LIST.map((g) => `<a class="sub ${key === g.id ? 'on' : ''}" href="${g.href || '#/games/' + g.id}"><span class="sub-ico">${gameSticker(g.id, 26)}</span>${esc(gameName(g.id))}</a>`).join('')}
      <span class="nav-spacer"></span>
      <div class="profit hide-sm"><span class="lbl">${t('Hoy')}</span><b class="num" id="st-today">${money(0, { noCents: true })}</b><span class="lbl">${t('Semana')}</span><b class="num" id="st-week">${money(0, { noCents: true })}</b><span class="lbl">${t('Siempre')}</span><b class="num" id="st-total">${money(0, { noCents: true })}</b></div></div>`;
  }
  if (sec === 'exchange') {
    const sym = (path.match(/^\/exchange\/(\w+)/) || [])[1];
    return `<div class="subnav-in"><a class="sub ${!sym ? 'on' : ''}" href="#/exchange">${t('Mercado')}</a><a class="sub ${sym === 'portfolio' ? 'on' : ''}" href="#/exchange/portfolio">${t('Mi portafolio')}</a>
      <span class="sub-sep"></span><span class="sub-kicker">${t('Empresas simuladas. Los precios son iguales para todos. Se paga con la cuenta acumulada.')}</span></div>`;
  }
  if (sec === 'ledger' && S.user) {
    const me = esc(S.user.username);
    const L = [['profile', `#/u/${me}`, t('Perfil'), /^\/u\//.test(path)], ['portfolio', '#/portfolio', t('Portafolio'), /^\/portfolio/.test(path)], ['statement', '#/statement', t('Estado de cuenta'), /^\/statement/.test(path)],
      ['challenges', '#/challenges', t('Retos'), /^\/challenges/.test(path)], ['progress', '#/progress', t('Rango y logros'), /^\/progress/.test(path)], ['loans', '#/loans', t('Préstamos'), /^\/loans/.test(path)], ['transfers', '#/transfers', t('Envíos'), /^\/transfers/.test(path)], ['ranking', '#/ranking', t('Ranking global'), /^\/ranking/.test(path)]];
    return `<div class="subnav-in">${L.map(([k, href, label, on]) => `<a class="sub ${on ? 'on' : ''}" href="${href}">${esc(label)}</a>`).join('')}</div>`;
  }
  return `<div class="subnav-in"><span class="sub-kicker">${esc(TAGLINES[sec] ? t(TAGLINES[sec]) : '')}</span></div>`;
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
    bar.innerHTML = `<span class="vb-tag">${t('Sin fichas')}</span><span class="vb-msg">${th('Tu vale semanal te espera: <b>{cantidad}</b> para tu cuenta semanal. Uno por semana.', { cantidad: money(v.amount) })}</span><button class="btn btn-sm vb-btn" id="vb-go">${t('Canjear {cantidad}', { cantidad: money(v.amount) })}</button>`;
  } else if (v && v.used && !v.busy && u.balance < v.below) {
    bar.className = 'voucher-bar used';
    bar.innerHTML = `<span class="vb-tag">${t('Sin nada')}</span><span class="vb-msg">${t('Ya usaste el vale de esta semana.')} ${v.goAmount > 0 ? th('Tu cuenta semanal vuelve a <b>{cantidad}</b> en {tiempo}.', { cantidad: money(v.goAmount), tiempo: until(v.resetsAt) }) : th('Llega uno nuevo en {tiempo}.', { tiempo: until(v.resetsAt) })}</span>`;
  } else { bar.className = 'voucher-bar'; bar.innerHTML = ''; }
}
async function redeemVoucher(e) {
  const btn = e.target.closest('#vb-go'); if (!btn) return;
  btn.disabled = true;
  try {
    const d = await post('/api/wallet/voucher');
    setUser(d.user);
    toast(t('Vale canjeado: {cantidad} cortesía de la casa. Haz que te duren.', { cantidad: money(d.added) }), 'ok', { ms: 5000 });
  } catch (ex) { toast(ex.message, 'err'); btn.disabled = false; refreshMe().catch(() => {}); }
}
function announcePassGo() {
  const g = S.user && S.user.passGo; if (!g) return;
  const key = 'clique-go-' + S.user.username;
  try { if (localStorage.getItem(key) === g.week) return; localStorage.setItem(key, g.week); } catch { /* storage blocked: show it, it is harmless */ }
  toast(t('Semana nueva. Tu cuenta semanal arranca otra vez: {cantidad} para jugar.', { cantidad: money(g.amount) }), 'ok', { ms: 7000 });
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
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
async function refreshTicker() {
  const track = document.getElementById('ticker-track'); if (!track || document.getElementById('ticker').classList.contains('hidden')) return;
  let wins = [], mk = [];
  try { wins = (await get('/api/games/feed')).feed.slice(0, 8); } catch { /* ignore */ }
  try { mk = (await get('/api/markets?status=open&sort=trending')).markets.slice(0, 7); } catch { /* ignore */ }
  const items = [];
  wins.forEach((w) => items.push(`<span class="tk">${th('<b>{nombre}</b> ganó en {juego}', { nombre: w.user, juego: gameName(w.game) })} <span class="num">${num(w.mult)}x</span> <b class="up num">${money(w.profit, { plus: true })}</b></span>`));
  mk.forEach((m) => {
    const yn = m.binary && m.outcomes[0].name === 'Yes';      // i18n: no (the name the server gives the first side of a yes/no market)
    const lead = m.outcomes.reduce((a, b) => (b.yes > a.yes ? b : a));
    const label = yn ? esc(t('SÍ')) : esc(trunc(lead.name, 14));
    const p = yn ? m.outcomes[0].yes : lead.yes;
    items.push(`<span class="tk">${esc(trunc(m.question, 44))} <b class="num ${p >= 0.5 ? 'up' : 'down'}">${label} ${cents(p)}</b></span>`);      // html: seguro (label es 'YES' o ya pasó por esc())
  });
  if (!items.length) items.push(`<span class="tk">${t('Noche tranquila. Nadie ha perdido nada todavía. Dale tiempo.')}</span>`, `<span class="tk">${t('Propón una apuesta. Ponle fichas. Arrepiéntete.')}</span>`);
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
    <div class="who">${avatar(u.username, 40)}<div><b>${esc(u.username)}</b>${u.rank ? `<span class="rkt" title="${esc(u.rank.l)}">${rankBadge(u.rank, 18)}</span>` : ''}${titleHtml(u.username)}<div class="mono muted" style="font-size:12px">${t('Semanal {cantidad}', { cantidad: money(u.balance) })} · ${t('Acumulada {cantidad}', { cantidad: money(u.accum || 0) })}</div></div></div><hr>
    <a href="#/games">${ICON.dice} ${t('Casino')}</a><a href="#/exchange">${ICON.trend} ${t('Bolsa')}</a><a href="#/store">${ICON.coins} ${t('Tienda')}</a><a href="#/circles">${ICON.users} ${t('Círculos')}</a><a href="#/friends">${ICON.user} ${t('Amigos')}</a><a href="#/chat">${ICON.chat} ${t('Chat')}</a><a href="#/weekly">${ICON.cal} ${t('Semana')}</a><a href="#/create">${ICON.plus} ${t('Proponer una apuesta')}</a><hr>
    <a href="#/u/${esc(u.username)}">${ICON.user} ${t('Perfil y premios')}</a>
    <a href="#/u/${esc(u.username)}/edit">${ICON.pencil} ${t('Personalizar perfil')}</a>
    <a href="#/portfolio">${ICON.wallet} ${t('Portafolio')}</a>
    <a href="#/statement">${ICON.clockc} ${t('Estado de cuenta')}</a>
    <a href="#/challenges">${ICON.trophy} ${t('Retos')}${u.unseen ? ` <span class="nbadge" style="position:static;display:inline-block;vertical-align:1px;margin-left:4px">${u.unseen}</span>` : ''}</a>
    <a href="#/progress">${ICON.crown} ${t('Rango y logros')}</a>
    <a href="#/loans">${ICON.coins} ${t('Préstamos')}${u.debt ? ` <span class="mono muted" style="font-size:12px">${t('(debes {cantidad})', { cantidad: money(u.debt) })}</span>` : ''}</a>
    <a href="#/transfers">${ICON.arrowR} ${t('Envíos')}</a>
    <a href="#/ranking">${ICON.trend} ${t('Ranking global')}</a>
    <button id="m-email">${ICON.lock} ${u.email && u.email.address ? (u.email.verified ? t('Correo (confirmado)') : t('Correo (sin confirmar)')) : t('Correo (agrega uno)')}</button>
    <button id="m-theme">${ICON.moon} ${t('Cambiar tema')}</button><hr>
    <button id="m-out">${ICON.out} ${t('Salir')}</button>`;
  document.getElementById('m-theme').addEventListener('click', () => {
    const theme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('clique-theme', theme); } catch { /* ignore */ }
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
    box.innerHTML = `<span class="lbl">${t('¿Olvidaste tu contraseña?')}</span><h2>${t('Recupérala con tu correo')}</h2>
      <p class="lede">${t('Escribe el correo de tu cuenta y te mandamos un código de 6 dígitos.')}</p>
      <form id="rs-form">
        <div class="field"><label for="rs-mail">${t('Correo')}</label><input class="input" id="rs-mail" type="email" autocomplete="email" required placeholder="${esc(t('tu@correo.com'))}" value="${esc(email)}"></div>
        <div class="error-text" id="rs-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary" id="rs-go">${t('Mándame un código')}</button></div>
      </form>
      <p class="muted" style="font-size:13px;margin:14px 0 0">${t('¿Tu cuenta no tiene correo?')} <a href="#" id="rs-funds">${t('Pídeselo a quien administra el sitio')}</a> ${t('(vas a necesitar la contraseña de fichas).')}</p>`;
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
    box.innerHTML = `<span class="lbl">${t('Revisa tu correo')}</span><h2>${t('Escribe el código')}</h2>
      <p class="lede">${th('Si <b>{correo}</b> es de una cuenta, ya va en camino un código de 6 dígitos. Puede tardar un minuto (revisa también el spam) y sirve 15 minutos.', { correo: email })}</p>
      <form id="rs-form">
        <div class="field"><label for="rs-code">${t('Código')}</label><input class="input" id="rs-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required placeholder="123456"></div>
        <div class="field"><label for="rs-new">${t('Contraseña nueva')}</label><input class="input" id="rs-new" type="password" autocomplete="new-password" required placeholder="${esc(t('6 caracteres o más'))}"></div>
        <div class="error-text" id="rs-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" id="rs-back">${t('Otro correo')}</button><button class="btn btn-primary" id="rs-go">${t('Guardar la contraseña nueva')}</button></div>
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
        toast(t('Listo, {nombre} tiene contraseña nueva. Entra con ella.', { nombre: d.username }), 'ok', { ms: 5200 });
      } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };
  stepEmail();
}

function openFundsReset() {
  const typed = (document.getElementById('au') || {}).value || '';
  const m = modal(`<span class="lbl">${t('¿Te quedaste fuera?')}</span><h2>${t('Cambiar una contraseña')}</h2><p class="lede">${t('Nadie puede ver una contraseña vieja, pero quien administra este sitio puede poner una nueva. Necesitas la contraseña de fichas (la de Agregar fichas).')}</p>
    <form id="rs-form">
      <div class="field"><label for="rs-user">${t('Usuario')}</label><input class="input" id="rs-user" autocomplete="username" maxlength="20" value="${esc(typed.includes('@') ? '' : typed)}"></div>
      <div class="field"><label for="rs-funds">${t('Contraseña de fichas')}</label><input class="input" id="rs-funds" type="password" autocomplete="off" placeholder="${esc(t('la contraseña de fichas'))}"></div>
      <div class="field"><label for="rs-new">${t('Contraseña nueva')}</label><input class="input" id="rs-new" type="password" autocomplete="new-password" placeholder="${esc(t('6 caracteres o más'))}"></div>
      <div class="error-text" id="rs-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary" id="rs-go">${t('Guardar la contraseña nueva')}</button></div>
    </form>`);
  revealPasswords(m.el);
  m.el.querySelector('#rs-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = m.el.querySelector('#rs-err'), btn = m.el.querySelector('#rs-go');
    const username = m.el.querySelector('#rs-user').value.trim();
    if (!username) { err.textContent = t('Primero escribe el usuario.'); return; }
    btn.disabled = true; err.textContent = '';
    try {
      const d = await post('/api/auth/reset', { username, fundsPassword: m.el.querySelector('#rs-funds').value, newPassword: m.el.querySelector('#rs-new').value });
      m.close();
      const au = document.getElementById('au'), ap = document.getElementById('ap');
      if (au) au.value = d.username;
      if (ap) { ap.value = ''; ap.focus(); }
      toast(t('Listo, {nombre} tiene contraseña nueva. Entra con ella.', { nombre: d.username }), 'ok', { ms: 4800 });
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
  const hint = () => em().preview ? `<p class="muted" style="font-size:13px;margin:10px 0 14px">${t('Esta copia del sitio no está conectada a un servicio de correo, así que el código aparece en la ventana de la Terminal donde corre el sitio.')}</p>` : '';

  const stepEnter = (note = '') => {
    const changing = em().address && em().verified;
    box.innerHTML = `<span class="lbl">${forced ? t('Una cosa rápida') : t('Tu cuenta')}</span><h2>${changing ? t('Cambia tu correo') : t('Agrega tu correo')}</h2>
      <p class="lede">${forced ? t('Ahora todos necesitan un correo en su cuenta.') + ' ' : ''}${t('Si algún día olvidas tu contraseña, te mandamos un código a este correo para que pongas una nueva. Nadie más puede verlo.')}</p>
      ${note}${''/* html: seguro (note es HTML del propio código; hoy nadie lo pasa) */}
      <form id="em-form">
        <div class="field"><label for="em-addr">${t('Correo')}</label><input class="input" id="em-addr" type="email" autocomplete="email" required placeholder="${esc(t('tu@correo.com'))}" value="${esc(changing ? '' : (em().address || ''))}"></div>
        ${changing ? `<div class="field"><label for="em-pw">${t('Tu contraseña')}</label><input class="input" id="em-pw" type="password" autocomplete="current-password" required placeholder="${esc(t('para confirmar que eres tú'))}"></div>` : ''}
        <div class="error-text" id="em-err" style="min-height:18px"></div>
        <div class="modal-actions">${forced ? `<button type="button" class="btn btn-ghost" id="em-out">${t('Salir')}</button>` : `<button type="button" class="btn btn-secondary" data-close>${t('Ahora no')}</button>`}<button class="btn btn-primary" id="em-go">${t('Guardar correo')}</button></div>
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
    box.innerHTML = `<span class="lbl">${t('Guardado')}</span><h2>${t('Gracias')}</h2><p class="lede">${t('Tu correo quedó guardado. En cuanto este sitio pueda mandar correos, te pediremos confirmarlo con un código.')}</p>
      <div class="modal-actions"><button class="btn btn-primary" id="em-ok">${t('Listo')}</button></div>`;
    box.querySelector('#em-ok').addEventListener('click', done);
  };
  const stepVerify = (note = '') => {
    const target = em().pending || em().address;
    box.innerHTML = `<span class="lbl">${t('Revisa tu correo')}</span><h2>${t('Confirma que es tuyo')}</h2>
      <p class="lede">${th('Mandamos un código de 6 dígitos a <b>{correo}</b>. Puede tardar un minuto (revisa también el spam). Escríbelo aquí para poder usar ese correo si olvidas tu contraseña.', { correo: target })}</p>
      ${hint()}${note}${''/* html: seguro (note es HTML del propio código; hoy nadie lo pasa) */}
      <form id="em-form">
        <div class="field"><label for="em-code">${t('Código')}</label><input class="input" id="em-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required placeholder="123456"></div>
        <div class="error-text" id="em-err" style="min-height:18px"></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary" id="em-later">${t('Después')}</button><button class="btn btn-primary" id="em-go">${t('Confirmar')}</button></div>
      </form>
      <p class="muted" style="font-size:13px;margin:14px 0 0"><a href="#" id="em-resend">${t('Mandar otro código')}</a> · <a href="#" id="em-change">${t('Usar otro correo')}</a></p>`;
    box.querySelector('#em-later').addEventListener('click', () => { try { sessionStorage.setItem('clique-mail-later', '1'); } catch { /* ignore */ } done(); });
    box.querySelector('#em-change').addEventListener('click', (e) => { e.preventDefault(); stepEnter(); });
    box.querySelector('#em-resend').addEventListener('click', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#em-err');
      try { await post('/api/me/email/resend'); err.textContent = ''; toast(t('Ya va en camino otro código.'), 'ok'); } catch (ex) { err.textContent = ex.message; }
    });
    box.querySelector('#em-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = box.querySelector('#em-err'), btn = box.querySelector('#em-go');
      btn.disabled = true; err.textContent = '';
      try {
        await post('/api/me/email/verify', { code: box.querySelector('#em-code').value.trim() });
        await refreshMe();
        done();
        toast(t('Tu correo está confirmado. Si algún día olvidas tu contraseña, puedes recuperarla con él.'), 'ok', { ms: 5200 });
      } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
  };

  const e0 = em();
  if (!e0.address) stepEnter();
  else if (!e0.verified || e0.pending) { if (e0.delivery) stepVerify(); else stepSaved(); }
  else stepEnter();                                   // a confirmed address: this is "change it"
}

function openDeposit() {
  const m = modal(`<span class="lbl">${t('Caja')}</span><h2>${t('Agregar fichas')}</h2><p class="lede">${t('¿Sabes la contraseña? Entonces la casa está abierta, por la cantidad que quieras. Pero antes votan todos los demás: las fichas se quedan apartadas hasta que termine la votación.')}</p>
    <div class="note-box hidden" id="dep-hold"></div>
    <form id="dep-form">
      <div class="field"><label>${t('¿A qué cuenta?')}</label><div class="seg" role="radiogroup" aria-label="${esc(t('Cuenta'))}">
        <label class="seg-opt"><input type="radio" name="dep-acct" value="weekly" checked><span><b>${t('Semanal')}</b><small>${t('fichas para apuestas y casino. Nunca cuentan como ganancia.')}</small></span></label>
        <label class="seg-opt"><input type="radio" name="dep-acct" value="accumulated"><span><b>${t('Acumulada')}</b><small>${t('para la Tienda y la Bolsa.')}</small></span></label></div></div>
      <div class="field"><label for="dep-amt">${t('Cantidad')}</label><input class="input num" id="dep-amt" inputmode="decimal" placeholder="5000" autocomplete="off"></div>
      <div class="chips" style="margin:-6px 0 16px">${[1000, 10000, 100000, 1000000].map((v) => `<button type="button" class="pill" data-v="${v}">+${money(v, { noCents: true })}</button>`).join('')}</div>
      <div class="field"><label for="dep-pw">${t('Contraseña')}</label><input class="input" id="dep-pw" type="password" autocomplete="off" placeholder="${esc(t('la contraseña de fichas'))}"></div>
      <div class="error-text" id="dep-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary" id="dep-go">${t('Agregar las fichas')}</button></div>
    </form>`);
  revealPasswords(m.el);
  get('/api/fundvotes').then((d) => {                                   // funds of yours that are still waiting for a vote
    const open = (d.mine || []).find((x) => x.status === 'open');
    if (!open || !m.el.isConnected) return;
    const box = m.el.querySelector('#dep-hold');
    box.innerHTML = th('Tienes <b>{cantidad}</b> apartadas para tu cuenta {cuenta}: han votado {votos} de {total}. Puedes agregar más cuando termine esa votación.', { cantidad: money(open.amount), cuenta: acctName(open.account), votos: open.voted, total: open.total });
    box.classList.remove('hidden'); m.el.querySelector('#dep-go').disabled = true;
  }).catch(() => {});
  m.el.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => { m.el.querySelector('#dep-amt').value = b.dataset.v; }));
  m.el.querySelector('#dep-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const amt = parseAmount(m.el.querySelector('#dep-amt').value), err = m.el.querySelector('#dep-err');
    if (!(amt > 0)) { err.textContent = t('Primero pon una cantidad.'); return; }
    const btn = m.el.querySelector('#dep-go'); btn.disabled = true; err.textContent = '';
    try {
      const account = m.el.querySelector('input[name="dep-acct"]:checked').value;
      const d = await post('/api/wallet/deposit', { amount: amt, password: m.el.querySelector('#dep-pw').value, account });
      setUser(d.user); m.close();
      if (d.added) toast(t('{cantidad} llegaron a tu cuenta {cuenta}.', { cantidad: money(d.added), cuenta: acctName(account) }), 'ok');          // (nobody else to ask)
      else toast(t('{cantidad} quedan apartadas. Los demás están votando: se agregan si hay más votos a favor que en contra (la votación termina en menos de {horas} h).', { cantidad: money(d.vote.amount), horas: Math.max(1, Math.round((d.vote.closesAt - Date.now()) / 3600000)) }), 'ok', { ms: 12000 });
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
    if (fresh.length > 3) toast(tp(fresh.length - 3, '…y {n} aviso más.', '…y {n} avisos más.'), '', { ms: 6000 });
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
    const when = hrs >= 1 ? tp(hrs, '{n} hora', '{n} horas') : tp(Math.max(1, Math.round(left / 60000)), '{n} minuto', '{n} minutos');
    const m = modal(`<span class="lbl">${t('Votación de fichas')}</span><h2>${th('{nombre} quiere agregar fichas', { nombre: v.username })}</h2>
      <p class="lede">${th('<b>{nombre}</b> está agregando <b>{cantidad}</b> a su cuenta {cuenta}. Las fichas se quedan apartadas hasta que termine la votación. ¿Estás a favor?', { nombre: v.username, cantidad: money(v.amount), cuenta: acctName(v.account) })}</p>
      <div class="note-box">${th('Han votado {votos} de {total}. La votación termina cuando el resultado ya no puede cambiar, cuando todos votaron o en {tiempo}. Si hay más votos a favor que en contra, se agregan las fichas; si no, no.', { votos: v.voted, total: v.total, tiempo: when })}</div>
      <div class="modal-actions"><button class="btn btn-no" id="fv-no">${t('En contra')}</button><button class="btn btn-primary" id="fv-yes">${t('A favor')}</button></div>`, { locked: true });
    m.el.parentElement.classList.add('above-toasts');                    // (a notification must never sit on top of the two buttons of a window that cannot be closed)
    const answer = async (favor) => {
      m.el.querySelectorAll('button').forEach((b) => { b.disabled = true; });
      try { await post(`/api/fundvotes/${v.id}/vote`, { favor }); m.close(); toast(t('Tu voto ya cuenta.'), 'ok'); resolve(true); }
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
    toast(t('{nombre} propuso: {pregunta}', { nombre: ev.by, pregunta: ev.question }), '', { onClick: () => go(`#/market/${ev.id}`), ms: 5000 });
  }
  if (ev.type === 'market' && ev.action === 'resolved') toast(t('Resuelto: {pregunta}', { pregunta: ev.question }), '', { onClick: () => go(`#/market/${ev.id}`), ms: 5000 });
  if (ev.type === 'week') toast(t('Semana nueva. Alguien le debe un castigo a alguien.'), '', { onClick: () => go('#/weekly'), ms: 6000 });
  if (ev.type === 'reward') toast(t('Premio semanal: {cantidad} por quedar #{lugar} en {circulo}. Ya está en tu cuenta acumulada.', { cantidad: money(ev.amount), lugar: ev.position, circulo: ev.circle }), 'ok', { onClick: () => go('#/weekly'), ms: 9000 });
  if (ev.type === 'weekwarn') toast(ev.text, 'err', { onClick: () => go('#/weekly'), ms: 15000 });
  if (ev.type === 'inbox') showNotice(ev.item);
  if (ev.type === 'market' && ev.action === 'edited' && ev.by !== S.user?.username) {
    toast(ev.material ? t('{nombre} cambió las reglas o la fecha de: {pregunta}', { nombre: ev.by, pregunta: ev.question }) : t('{nombre} aclaró: {pregunta}', { nombre: ev.by, pregunta: ev.question }), '', { onClick: () => go(`#/market/${ev.id}`), ms: 7000 });
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
  document.querySelectorAll('#tabbar .tab').forEach((a) => { const on = a.dataset.sec === sec; a.classList.toggle('on', on); if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  // R3: in the casino the market search and the price ticker go away, so the bet button has the room (at 1366x768 they covered it)
  const casino = sec === 'casino', ticker = document.getElementById('ticker'), wasHidden = ticker.classList.contains('hidden');
  ticker.classList.toggle('hidden', casino);
  document.querySelectorAll('.top-right .search, .search-mobile').forEach((el) => el.classList.toggle('hidden', casino));
  if (wasHidden && !casino) refreshTicker();
  document.getElementById('btn-friends')?.classList.toggle('on', /^\/friends/.test(path));
  document.getElementById('btn-chat')?.classList.toggle('on', /^\/chat/.test(path));
  if (sec === 'casino') refreshProfit();
}

// Where you came from, and the pages that get a "Back to ..." shortcut (everything that is a place you drill into).
let here = null, before = null;
const BACK_ON = /^\/(market\/|circle\/|games\/|poker\/|exchange\/|u\/|create|statement|store\/)/;
const WHERE = [                                    // i18n: claves ↓
  [/^\/?$/, 'Mercados'], [/^\/market\//, 'la apuesta'], [/^\/create/, 'proponer apuesta'], [/^\/circles$/, 'Círculos'], [/^\/circle\//, 'el círculo'], [/^\/weekly/, 'la Semana'],
  [/^\/games$/, 'el vestíbulo del casino'], [/^\/games\//, 'el juego'], [/^\/poker/, 'el póker'], [/^\/friends/, 'Amigos'], [/^\/chat/, 'Chat'], [/^\/exchange$/, 'la Bolsa'],
  [/^\/exchange\/portfolio/, 'tu portafolio'], [/^\/exchange\//, 'la empresa'], [/^\/store/, 'la Tienda'], [/^\/statement/, 'tu estado de cuenta'], [/^\/portfolio/, 'tu portafolio'], [/^\/challenges/, 'los retos'], [/^\/progress/, 'tu rango'], [/^\/loans/, 'tus préstamos'], [/^\/transfers/, 'tus envíos'], [/^\/u\//, 'el perfil']];
const whereName = (p) => t((WHERE.find(([rx]) => rx.test(p)) || [0, 'donde estabas'])[1]);      // i18n: fin

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
    <div class="empty-copy"><span class="kicker">${t('Error 404')}</span><h3>${t('Esta página lo perdió todo al rojo.')}</h3><p>${t('Apostó todo a un solo giro y se fue. Igual que lo que buscabas.')}</p>
    <div class="btns"><a class="btn btn-primary" href="#/">${t('Volver a la acción')}</a></div></div></div></div>`;
}

/** "Back to ..." on pages you drill into: goes back in history when that is where you came from, so the page you left is restored as it was. */
function addBackLink(root, path, arrival) {
  if (!BACK_ON.test(path) || !before || before.path === path) return;
  const page = root.querySelector('.page'); if (!page || page.querySelector('.back-to')) return;
  const a = document.createElement('a');
  a.className = 'back-to'; a.href = before.hash;
  a.innerHTML = `${ICON.chevL} ${th('Volver a {lugar}', { lugar: whereName(before.path) })}`;
  a.addEventListener('click', (e) => { e.preventDefault(); if (!arrival.revisit && history.length > 1) history.back(); else location.hash = before.hash; });
  page.prepend(a);
}

function errorBlock(message) {
  return `<div class="empty"><div class="empty-art">${sticker('warning', { size: 112, bg: 'lime' })}</div>
    <div class="empty-copy"><span class="kicker">${t('Algo se rompió')}</span><h3>${t('La casa se equivocó.')}</h3><p>${esc(message)}</p><div class="btns"><a class="btn btn-primary" href="#/">${t('Volver a la acción')}</a></div></div></div>`;
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
  confirmBox({ title: t('¿Salir sin guardar?'), text: g.message, confirm: t('Sí, salir'), danger: true }).then((ok) => { if (ok) { skipGuard = true; location.hash = target; } });
});
window.addEventListener('beforeunload', closeStream);
setInterval(() => { if (S.user) refreshTicker(); }, 60000);

// A new language paints everything again, in place: no reload, and the screen keeps its scroll (viewstate.js sees the same entry).
onLang(() => {
  if (!S.user) { if (document.getElementById('auth-form')) showAuth(authMode); return; }
  shellReady = false;
  route();
});

// Installable app (F2): the worker keeps the shell so the app opens without a connection (static/sw.js); nothing about money is kept.
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => { /* the app works the same without it */ });
// Losing the connection is said out loud: what is on screen may be out of date, and nothing can be bet until it is back.
window.addEventListener('offline', () => { if (S.user) toast(t('Sin conexión. Lo que ves puede no estar al día y no puedes apostar hasta que vuelva.'), 'err', { ms: 8000 }); });
window.addEventListener('online', () => { if (S.user) { toast(t('Volvió la conexión.'), 'ok'); refreshMe().catch(() => {}); refreshTicker(); } else if (document.getElementById('retry')) location.reload(); });

(async function boot() {
  await initLang();                                  // before the first paint, so nobody sees the other language flash by
  try {
    const u = await refreshMe();
    if (u) startApp(); else showAuth('login');
  } catch (e) {
    const offline = navigator.onLine === false || e.code === 'NETWORK';
    $app.innerHTML = `<div class="auth"><form class="auth-card paper" role="alert"><span class="lbl">${esc(offline ? t('Sin conexión') : t('Sin señal'))}</span>
      <h2>${esc(offline ? t('Estás sin internet.') : t('No podemos llegar a la casa.'))}</h2>
      <p class="lede">${esc(offline ? t('Clique necesita conexión para mostrarte tus fichas y tus apuestas. En cuanto vuelva la señal, seguimos.') : e.message)}</p>
      <button type="button" class="btn btn-primary" id="retry">${esc(t('Intentar otra vez'))}</button></form></div>`;
    document.getElementById('retry').addEventListener('click', () => location.reload());
  }
})();
