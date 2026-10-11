import { get } from '../api.js';
import { S, bus, go, loadCircles } from '../state.js';
import { esc, ICON, debounce, vol, cents, circleMark, roll, pctOf, catName, sideName } from '../util.js';
import { marketCard, wireCards, isYesNo, slipChoices, slipNo, emptyState, whereHtml } from './components.js';
import { drawChart, COLORS } from './chart.js';
import { bookmarks } from '../bookmarks.js';
import { poster } from '../art.js';
import { gameName, gameById } from '../gamelist.js';
import { recall, remember } from '../viewstate.js';
import { t, th, tp } from '../i18n.js';

const SORTS = [['trending', 'En tendencia'], ['new', 'Más nuevos'], ['ending', 'Cierran pronto'], ['volume', 'Más volumen']];      // i18n: claves

export default {
  async mount(root, _p, query) {
    const tab = query.get('tab') || 'trending';
    const st = {
      circle: query.get('circle') || '', category: query.get('cat') || '', q: S.search || query.get('q') || '', bm: false,
      sort: tab === 'new' ? 'new' : tab === 'ending' ? 'ending' : 'trending', status: tab === 'resolved' ? 'resolved' : 'open',
    };
    const MEM = `markets:${tab}:${st.category}`;                                   // how you left this list: its sort, bookmarks and search come back with you
    const mem = recall(MEM);
    if (!query.get('circle') && typeof mem.circle === 'string') st.circle = mem.circle;
    if (mem.sort && st.status === 'open' && tab === 'trending') st.sort = mem.sort;
    if (mem.bm) st.bm = true;
    if (!st.q && typeof mem.q === 'string') { st.q = mem.q; S.search = mem.q; }
    const keep = () => remember(MEM, { circle: st.circle, sort: st.sort, bm: st.bm, q: st.q });
    let list = [], known = new Set(), first = true, lastJson = '', dead = false, featIdx = 0;
    const details = {};
    await loadCircles().catch(() => {});

    const heading = esc(st.status === 'resolved' ? t('Resueltos y cerrados') : st.category ? catName(st.category) : tab === 'new' ? t('Recién salidos') : tab === 'ending' ? t('Se acaba el tiempo') : t('Todas las apuestas de la sala'));
    root.innerHTML = `<div class="page home">
      <div id="home-top"></div>
      <div class="all-head" id="all-markets"><div><span class="kicker" id="count"></span><h2>${heading}</h2></div>
        <div class="all-icons"><button class="icon-btn" id="i-search" title="${esc(t('Buscar'))}" aria-label="${esc(t('Buscar'))}">${ICON.search}</button>
          <button class="icon-btn" id="i-filter" title="${esc(t('Ordenar y filtrar'))}" aria-label="${esc(t('Ordenar y filtrar'))}">${ICON.sliders}</button>
          <button class="icon-btn" id="i-bm" title="${esc(t('Guardados'))}" aria-label="${esc(t('Guardados'))}">${ICON.bookmark}</button><div class="pop-menu hidden" id="pop"></div></div></div>
      <div class="chip-row" id="chips"></div>
      <div id="grid-host"></div></div>`;
    const host = root.querySelector('#grid-host'), top = root.querySelector('#home-top');
    wireCards(host);
    wireCards(top);

    const drawChips = () => {
      root.querySelector('#chips').innerHTML = `<button class="${!st.circle ? 'active' : ''}" data-c="">${t('Todos')}</button><button class="${st.circle === 'site' ? 'active' : ''}" data-c="site">${ICON.globe} ${t('Públicos')}</button>` +
        S.myCircles.map((c) => `<button class="${st.circle === c.id ? 'active' : ''}" data-c="${c.id}">${circleMark(c, 15)} ${esc(c.name)}</button>`).join('');
    };
    drawChips();

    const isHome = () => tab === 'trending' && !st.category && !st.circle && !st.q && !st.bm && st.status === 'open' && st.sort === 'trending';

    // ---------------------------------------------------------------- headline slip + the board
    function drawTop() {
      if (!isHome() || !list.length) { top.innerHTML = ''; return; }
      const feats = list.slice(0, 5);
      featIdx = Math.min(featIdx, feats.length - 1);
      const m = feats[featIdx], O = m.outcomes, yn = isYesNo(m);
      const link = (o, s) => `#/market/${m.id}?o=${o}&s=${s}`;
      const prev = feats[(featIdx - 1 + feats.length) % feats.length], next = feats[(featIdx + 1) % feats.length];
      const short = (s) => (s.length > 22 ? s.slice(0, 21) + '…' : s);
      const lead = O.reduce((a, b) => (b.yes > a.yes ? b : a));
      const hot = [...list].sort((a, b) => (b.volume24h - a.volume24h) || (b.volume - a.volume)).slice(0, 5);
      top.innerHTML = `<section class="hero">
        <div>
          <div class="headline" data-id="${m.id}">
            <div class="headline-slip paper">
              <div class="slip-top"><span>${t('La estelar de la noche')} · ${slipNo(m)}</span></div>
              <h2>${esc(m.question)}</h2>
              <div class="slip-pick big">${slipChoices(m, link)}</div>
              <div class="slip-foot"><span>${t('Vol.')} <b class="num">${vol(m.volume)}</b></span><span>${tp(m.traders, '{n} apostador', '{n} apostadores')}</span><span class="where ellipsis">${whereHtml(m)}</span></div>
            </div>
            <div class="headline-chart">
              <div class="hc-head"><span class="lbl">${yn ? t('Probabilidad de sí') : th('Va ganando: {opcion}', { opcion: lead.name })}</span><b class="num hc-big" id="hc-big">${pctOf(yn ? O[0] : lead)}</b></div>
              <div id="feat-chart"></div>
            </div>
          </div>
          ${feats.length > 1 ? `<div class="feat-nav"><div class="dots">${feats.map((_, i) => `<i class="${i === featIdx ? 'on' : ''}" data-d="${i}"></i>`).join('')}</div>
            <button class="navpill" data-step="-1">${ICON.chevL}<span>${esc(short(prev.question))}</span></button><button class="navpill" data-step="1"><span>${esc(short(next.question))}</span>${ICON.chevR}</button></div>` : ''}
        </div>
        <aside class="board">
          <div class="board-head"><h3>${t('La pizarra')}</h3><span class="lbl">${t('Lo más caliente')}</span></div>
          ${hot.map((h, i) => `<a class="hot-row" href="#/market/${h.id}"><span class="rk">${i + 1}</span><span class="t">${esc(h.question)}</span>
            <span class="v num">${h.volume24h > 0 ? vol(h.volume24h) + ' ' + ICON.flame : vol(h.volume)}</span></a>`).join('')}
          <a class="tape" href="#/create"><span class="tape-main">${t('Ponle fichas')} ${ICON.arrowR}</span><span class="tape-sub">${t('Propón una apuesta. Para tu círculo o para todo el sitio.')}</span></a>
          <a class="poster-tile" href="#/games/chicken">${poster('chicken')}<div><b>${esc(gameName('chicken'))}</b><span>${esc(t(gameById('chicken').tag))}</span></div></a>
        </aside></section>`;
      const target = top.querySelector('#feat-chart');
      const paint = (d) => {
        if (dead || !top.contains(target)) return;
        const series = m.binary ? [{ idx: 0, name: sideName(O[0].name), color: COLORS[0] }]
          : O.map((o, i) => ({ idx: i, name: o.name })).sort((a, b) => O[b.idx].yes - O[a.idx].yes).slice(0, 3).map((s, k) => ({ ...s, color: COLORS[k] }));
        drawChart(target, d.history, series, 'ALL', undefined, { height: 230 });
      };
      if (details[m.id] && details[m.id].v === m.volume) paint(details[m.id].d);
      else get(`/api/markets/${m.id}`).then((r) => { details[m.id] = { v: m.volume, d: r.market }; paint(r.market); }).catch(() => {});
    }

    top.addEventListener('click', (e) => {
      const step = e.target.closest('[data-step]'), dot = e.target.closest('[data-d]');
      if (step) { e.stopPropagation(); const n = Math.min(5, list.length); featIdx = (featIdx + Number(step.dataset.step) + n) % n; drawTop(); return; }
      if (dot) { e.stopPropagation(); featIdx = Number(dot.dataset.d); drawTop(); return; }
      const f = e.target.closest('.headline');
      if (f && !e.target.closest('button,a')) go(`#/market/${f.dataset.id}`);
    });

    // ---------------------------------------------------------------- the grid
    async function load() {
      const p = new URLSearchParams({ status: st.status, sort: st.sort });
      if (st.circle) p.set('circle', st.circle);
      if (st.category) p.set('category', st.category);
      if (st.q) p.set('q', st.q);
      const d = await get('/api/markets?' + p);
      if (dead) return;
      let rows = d.markets;
      if (st.bm) { const b = bookmarks(); rows = rows.filter((m) => b.has(m.id)); }
      const json = JSON.stringify(rows);
      if (json === lastJson) return;
      lastJson = json; list = rows;
      drawTop();
      root.querySelector('#count').textContent = tp(rows.length, '{n} boleto', '{n} boletos');
      const ids = new Set(rows.map((m) => m.id));
      if (!rows.length) {
        const noCircles = !S.myCircles.length;
        host.innerHTML = st.bm ? emptyState({ art: 'bookmark', tone: 'lime', kicker: t('Nada guardado'), title: esc(t('Sin guardados.')), text: esc(t('Toca el marcador de un boleto para fijarlo aquí. Haremos como que eres ordenado.')) })
          : st.q || st.category || st.circle || st.status === 'resolved'
            ? emptyState({ art: 'lens', tone: 'cream', kicker: t('Sin resultados'), title: esc(t('Nada coincide.')), text: esc(t('Prueba con otras palabras u otro círculo. O acepta que nadie se ha animado a apostar por eso todavía.')) })
            : noCircles
              ? emptyState({ art: 'chip', tone: 'verm', kicker: t('Lo primero es lo primero'), title: esc(t('Sin círculo no hay contra quién perder.')), text: esc(t('Las apuestas privadas viven dentro de los círculos. Crea uno para tus amigos, únete a uno con un código o propón una apuesta pública para todo el sitio.')), actions: `<a class="btn btn-primary" href="#/circles">${ICON.users} ${t('Crear o unirte a un círculo')}</a><a class="btn btn-secondary" href="#/create?scope=site">${ICON.globe} ${t('Proponer una apuesta pública')}</a>` })
              : emptyState({ art: 'slip', tone: 'cream', kicker: t('Libro vacío'), title: esc(t('Muy tranquilo por aquí.')), text: esc(t('Nadie ha puesto una mala idea sobre la mesa todavía. Di algo tonto y ponle fichas.')), actions: `<a class="btn btn-primary" href="#/create">${ICON.plus} ${t('Proponer una apuesta')}</a>` });
      } else {
        host.innerHTML = `<div class="slips">${rows.map((m) => marketCard(m, { fresh: !first && !known.has(m.id) })).join('')}</div>`;
      }
      known = ids; first = false;
    }

    const reload = debounce(() => load().catch(() => {}), 150);
    root.querySelector('#chips').addEventListener('click', (e) => { const b = e.target.closest('[data-c]'); if (b) { st.circle = b.dataset.c; keep(); lastJson = ''; drawChips(); load(); } });
    root.querySelector('#i-search').addEventListener('click', () => (document.getElementById('gsearch') || document.getElementById('gsearch-m'))?.focus());
    root.querySelector('#i-bm').addEventListener('click', (e) => { st.bm = !st.bm; keep(); e.currentTarget.classList.toggle('on', st.bm); lastJson = ''; load(); });
    host.addEventListener('bookmark', () => { if (st.bm) { lastJson = ''; load(); } });

    const pop = root.querySelector('#pop');
    const drawPop = () => {
      pop.innerHTML = `<h6>${t('Ordenar por')}</h6>${SORTS.map(([k, l]) => `<button data-s="${k}" class="${st.sort === k ? 'on' : ''}">${esc(t(l))}</button>`).join('')}
        <h6>${t('Mostrar')}</h6><button data-t="open" class="${st.status === 'open' ? 'on' : ''}">${t('Apuestas abiertas')}</button><button data-t="resolved" class="${st.status === 'resolved' ? 'on' : ''}">${t('Apuestas resueltas')}</button>`;
    };
    root.querySelector('#i-filter').addEventListener('click', (e) => { e.stopPropagation(); drawPop(); pop.classList.toggle('hidden'); if (!pop.classList.contains('hidden')) pop.scrollIntoView({ block: 'nearest' }); });      // opening near the bottom of the screen scrolls the menu fully into view
    pop.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.s) { st.sort = b.dataset.s; keep(); } if (b.dataset.t) st.status = b.dataset.t;
      pop.classList.add('hidden'); lastJson = ''; load();
    });
    const closePop = () => pop.classList.add('hidden');
    document.addEventListener('click', closePop);

    const onSearch = () => { st.q = S.search; keep(); lastJson = ''; reload(); };
    bus.addEventListener('search', onSearch);
    const gs = document.getElementById('gsearch'); if (gs && st.q) gs.value = st.q;
    await load();

    const tick = setInterval(() => { lastJson = ''; load().catch(() => {}); }, 60000);   // keeps "ends in 3h" fresh
    return {
      onEvent(ev) { if (ev.type === 'market' || ev.type === 'circle') { if (ev.type === 'circle') loadCircles().then(drawChips).catch(() => {}); reload(); } },
      unmount() { dead = true; clearInterval(tick); bus.removeEventListener('search', onSearch); document.removeEventListener('click', closePop); },
    };
  },
};
