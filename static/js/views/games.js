import { get } from '../api.js';
import { go } from '../state.js';
import { esc, money, ago, avatar, ICON } from '../util.js';
import { GAME_LIST, gameById, gameName } from '../gamelist.js';
import { gameSticker } from '../art.js';
import { emptyState } from './components.js';

const FAV_KEY = 'clique-fav-games';
const favs = () => { try { return JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); } catch { return []; } };
const toggleFav = (id) => {
  const f = favs(); const i = f.indexOf(id);
  if (i >= 0) f.splice(i, 1); else f.push(id);
  try { localStorage.setItem(FAV_KEY, JSON.stringify(f)); } catch { /* ignore */ }
  return i < 0;
};

const layout = ['big', '', '', 'wide', '', '', '', '', 'wide', 'wide', 'wide', '', '', 'full'];
const poster = (g, i, cls = layout[i] ?? '') => `<a class="pstr ${cls}" href="${g.href || '#/games/' + g.id}">
  <button class="fav ${favs().includes(g.id) ? 'on' : ''}" data-fav="${g.id}" title="Favourite" aria-label="Favourite ${esc(g.name)}">${favs().includes(g.id) ? ICON.starOn : ICON.star}</button>
  ${g.art({ wide: cls === 'wide', banner: cls === 'full' })}
  <div class="pstr-label"><h3>${esc(g.name)}</h3><p>${esc(g.tag)}</p><div class="meta"><span>${g.rtp ? 'Returns ' + g.rtp : g.meta || ''}</span><span>Play ${ICON.arrowR}</span></div></div></a>`;

export default {
  async mount(root, _p, query) {
    const view = query.get('view') || 'home';
    let dead = false;
    const [feedRes, histRes] = await Promise.all([get('/api/games/feed').catch(() => ({ feed: [] })), get('/api/games/history').catch(() => ({ history: [] }))]);
    if (dead) return;

    const seg = `<div class="seg" role="tablist"><button data-v="home" class="${view === 'home' ? 'active' : ''}">All games</button><button data-v="favorites" class="${view === 'favorites' ? 'active' : ''}">Favourites</button><button data-v="recent" class="${view === 'recent' ? 'active' : ''}">Played lately</button></div>`;
    const head = `<div class="lobby-head"><div><span class="kicker">The casino // the house always wins (eventually)</span>
        <h1>Lose money<br><em>with style.</em></h1><p>Thirteen games. Ten-cent minimum, no maximum, and the house has feelings about that. Every game has a Demo switch if you want to practise losing first.</p></div>${seg}</div>`;

    const recentIds = [...new Set(histRes.history.map((h) => h.game))];
    let body;
    if (view === 'favorites') {
      const list = GAME_LIST.filter((g) => favs().includes(g.id));
      body = list.length ? `<div class="posters">${list.map((g, i) => poster(g, i, '')).join('')}</div>`
        : emptyState({ art: 'star', tone: 'lime', kicker: 'No favourites', title: 'No favourites. No taste.', text: 'Tap the star on a poster to pin it here.', actions: '<a class="btn btn-primary" href="#/games">Pick some games</a>' });
    } else if (view === 'recent') {
      const list = recentIds.map(gameById).filter(Boolean);
      body = list.length ? `<div class="posters">${list.map((g, i) => poster(g, i, '')).join('')}</div>
        <div class="ledger-sec"><h2>Your last bets</h2><div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>Game</th><th class="r">Bet</th><th class="r">Payout</th><th class="r">Multiplier</th><th class="r">When</th></tr></thead><tbody>
        ${histRes.history.slice(0, 12).map((h) => `<tr><td><b>${esc(gameName(h.game))}</b></td><td class="r">${money(h.bet)}</td><td class="r ${h.profit > 0 ? 'up' : h.profit < 0 ? 'down' : ''}">${money(h.payout)}</td><td class="r">${h.mult ? h.mult.toLocaleString() + 'x' : '—'}</td><td class="r muted">${ago(h.t)}</td></tr>`).join('')}</tbody></table></div></div>`
        : emptyState({ art: 'snake', tone: 'cream', kicker: 'Nothing played', title: 'Snake eyes. Literally nothing.', text: 'You have not placed a single bet in here.', actions: '<a class="btn btn-primary" href="#/games">Pick a game</a>' });
    } else {
      body = `<div class="posters">${GAME_LIST.map((g, i) => poster(g, i)).join('')}</div>
        <div class="ledger-sec"><span class="kicker">Receipts from the floor</span><h2>Biggest recent wins</h2>
        ${feedRes.feed.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>Winner</th><th>Game</th><th class="r">Multiplier</th><th class="r">Profit</th><th class="r">When</th></tr></thead><tbody>
          ${feedRes.feed.map((w) => `<tr><td><span class="row" style="gap:10px">${avatar(w.user, 26)}<b>${esc(w.user)}</b></span></td><td><span class="row" style="gap:8px">${gameSticker(w.game, 26)}<span>${esc(gameName(w.game))}</span></span></td>
          <td class="r">${w.mult.toLocaleString()}x</td><td class="r up">${money(w.profit, { plus: true })}</td><td class="r muted">${ago(w.t)}</td></tr>`).join('')}</tbody></table></div>`
          : emptyState({ art: 'trophy', tone: 'lime', tight: true, kicker: 'No winners', title: 'Nobody has won big. Yet.', text: 'Win something at 2x or better and your name goes up here.' })}</div>`;
    }
    root.innerHTML = `<div class="page">${head}${body}</div>`;      // html: seguro (head y body se arman arriba con esc())

    root.addEventListener('click', (e) => {
      const f = e.target.closest('[data-fav]');
      if (f) {
        e.preventDefault(); e.stopPropagation();
        const on = toggleFav(f.dataset.fav); f.classList.toggle('on', on); f.innerHTML = on ? ICON.starOn : ICON.star;
        if (view === 'favorites' && !on) go('#/games?view=favorites');
        return;
      }
      const v = e.target.closest('.seg [data-v]');
      if (v) go(v.dataset.v === 'home' ? '#/games' : `#/games?view=${v.dataset.v === 'favorites' ? 'favorites' : 'recent'}`);
    });
    return { unmount() { dead = true; } };
  },
};
