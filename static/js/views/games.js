import { get } from '../api.js';
import { go } from '../state.js';
import { esc, money, ago, avatar, ICON, num } from '../util.js';
import { GAME_LIST, gameById, gameName, gameTag, gameMeta } from '../gamelist.js';
import { t } from '../i18n.js';
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
  <button class="fav ${favs().includes(g.id) ? 'on' : ''}" data-fav="${g.id}" title="${esc(t('Favorito'))}" aria-label="${esc(t('Marcar {juego} como favorito', { juego: gameName(g.id) }))}">${favs().includes(g.id) ? ICON.starOn : ICON.star}</button>
  ${g.art({ wide: cls === 'wide', banner: cls === 'full' })}
  <div class="pstr-label"><h3>${esc(gameName(g.id))}</h3><p>${esc(gameTag(g))}</p><div class="meta"><span>${esc(g.rtp ? t('Devuelve {pct}', { pct: g.rtp }) : gameMeta(g))}</span><span>${t('Jugar')} ${ICON.arrowR}</span></div></div></a>`;

export default {
  async mount(root, _p, query) {
    const view = query.get('view') || 'home';
    let dead = false;
    const [feedRes, histRes] = await Promise.all([get('/api/games/feed').catch(() => ({ feed: [] })), get('/api/games/history').catch(() => ({ history: [] }))]);
    if (dead) return;

    const seg = `<div class="seg" role="tablist"><button data-v="home" class="${view === 'home' ? 'active' : ''}">${t('Todos los juegos')}</button><button data-v="favorites" class="${view === 'favorites' ? 'active' : ''}">${t('Favoritos')}</button><button data-v="recent" class="${view === 'recent' ? 'active' : ''}">${t('Jugados hace poco')}</button></div>`;
    const head = `<div class="lobby-head"><div><span class="kicker">${t('El casino // la casa siempre gana (tarde o temprano)')}</span>
        <h1>${t('Pierde fichas')}<br><em>${t('con estilo.')}</em></h1><p>${t('Trece juegos. Mínimo {minimo}, sin máximo, y la casa tiene opiniones al respecto. Cada juego tiene un modo de práctica por si quieres ensayar cómo perder primero.', { minimo: money(0.1) })}</p></div>${seg}</div>`;

    const recentIds = [...new Set(histRes.history.map((h) => h.game))];
    let body;
    if (view === 'favorites') {
      const list = GAME_LIST.filter((g) => favs().includes(g.id));
      body = list.length ? `<div class="posters">${list.map((g, i) => poster(g, i, '')).join('')}</div>`
        : emptyState({ art: 'star', tone: 'lime', kicker: t('Sin favoritos'), title: esc(t('Sin favoritos. Sin gusto.')), text: esc(t('Toca la estrella de un póster para fijarlo aquí.')), actions: `<a class="btn btn-primary" href="#/games">${t('Elige unos juegos')}</a>` });
    } else if (view === 'recent') {
      const list = recentIds.map(gameById).filter(Boolean);
      body = list.length ? `<div class="posters">${list.map((g, i) => poster(g, i, '')).join('')}</div>
        <div class="ledger-sec"><h2>${t('Tus últimas apuestas')}</h2><div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>${t('Juego')}</th><th class="r">${t('Apuesta')}</th><th class="r">${t('Pago')}</th><th class="r">${t('Multiplicador')}</th><th class="r">${t('Cuándo')}</th></tr></thead><tbody>
        ${histRes.history.slice(0, 12).map((h) => `<tr><td><b>${esc(gameName(h.game))}</b></td><td class="r">${money(h.bet)}</td><td class="r ${h.profit > 0 ? 'up' : h.profit < 0 ? 'down' : ''}">${money(h.payout)}</td><td class="r">${h.mult ? num(h.mult) + 'x' : '—'}</td><td class="r muted">${ago(h.t)}</td></tr>`).join('')}</tbody></table></div></div>`
        : emptyState({ art: 'snake', tone: 'cream', kicker: t('Nada jugado'), title: esc(t('Ojos de serpiente. Nada de nada.')), text: esc(t('No has hecho ni una apuesta aquí.')), actions: `<a class="btn btn-primary" href="#/games">${t('Elige un juego')}</a>` });
    } else {
      body = `<div class="posters">${GAME_LIST.map((g, i) => poster(g, i)).join('')}</div>
        <div class="ledger-sec"><span class="kicker">${t('Recibos del piso')}</span><h2>${t('Las ganancias más grandes de estos días')}</h2>
        ${feedRes.feed.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>${t('Ganador')}</th><th>${t('Juego')}</th><th class="r">${t('Multiplicador')}</th><th class="r">${t('Ganancia')}</th><th class="r">${t('Cuándo')}</th></tr></thead><tbody>
          ${feedRes.feed.map((w) => `<tr><td><span class="row" style="gap:10px">${avatar(w.user, 26)}<b>${esc(w.user)}</b></span></td><td><span class="row" style="gap:8px">${gameSticker(w.game, 26)}<span>${esc(gameName(w.game))}</span></span></td>
          <td class="r">${num(w.mult)}x</td><td class="r up">${money(w.profit, { plus: true })}</td><td class="r muted">${ago(w.t)}</td></tr>`).join('')}</tbody></table></div>`
          : emptyState({ art: 'trophy', tone: 'lime', tight: true, kicker: t('Sin ganadores'), title: esc(t('Nadie ha ganado en grande. Todavía.')), text: esc(t('Gana algo a 2x o más y tu nombre aparece aquí.')) })}</div>`;
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
