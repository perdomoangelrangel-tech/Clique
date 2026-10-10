import { get } from '../api.js';
import { S, bus, go, loadCircles } from '../state.js';
import { esc, ICON, debounce, vol, cents, circleMark, roll, pctOf } from '../util.js';
import { marketCard, wireCards, isYesNo, slipChoices, slipNo, emptyState, whereHtml } from './components.js';
import { drawChart, COLORS } from './chart.js';
import { bookmarks } from '../bookmarks.js';
import { poster } from '../art.js';
import { recall, remember } from '../viewstate.js';

const SORTS = [['trending', 'Trending'], ['new', 'Newest'], ['ending', 'Ending soon'], ['volume', 'Top volume']];

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

    const heading = st.status === 'resolved' ? 'Settled and done' : st.category ? esc(st.category) : tab === 'new' ? 'Fresh off the press' : tab === 'ending' ? 'Running out of time' : 'Every bet in the room';
    root.innerHTML = `<div class="page home">
      <div id="home-top"></div>
      <div class="all-head" id="all-markets"><div><span class="kicker" id="count"></span><h2>${heading}</h2></div>
        <div class="all-icons"><button class="icon-btn" id="i-search" title="Search" aria-label="Search">${ICON.search}</button>
          <button class="icon-btn" id="i-filter" title="Sort and filter" aria-label="Sort and filter">${ICON.sliders}</button>
          <button class="icon-btn" id="i-bm" title="Bookmarks" aria-label="Bookmarks">${ICON.bookmark}</button><div class="pop-menu hidden" id="pop"></div></div></div>
      <div class="chip-row" id="chips"></div>
      <div id="grid-host"></div></div>`;
    const host = root.querySelector('#grid-host'), top = root.querySelector('#home-top');
    wireCards(host);
    wireCards(top);

    const drawChips = () => {
      root.querySelector('#chips').innerHTML = `<button class="${!st.circle ? 'active' : ''}" data-c="">Everyone</button><button class="${st.circle === 'site' ? 'active' : ''}" data-c="site">${ICON.globe} Public</button>` +
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
      const short = (t) => (t.length > 22 ? t.slice(0, 21) + '…' : t);
      const lead = O.reduce((a, b) => (b.yes > a.yes ? b : a));
      const hot = [...list].sort((a, b) => (b.volume24h - a.volume24h) || (b.volume - a.volume)).slice(0, 5);
      top.innerHTML = `<section class="hero">
        <div>
          <div class="headline" data-id="${m.id}">
            <div class="headline-slip paper">
              <div class="slip-top"><span>Tonight's main event · ${slipNo(m)}</span></div>
              <h2>${esc(m.question)}</h2>
              <div class="slip-pick big">${slipChoices(m, link)}</div>
              <div class="slip-foot"><span>Vol. <b class="num">${vol(m.volume)}</b></span><span>${m.traders} trader${m.traders === 1 ? '' : 's'}</span><span class="where ellipsis">${whereHtml(m)}</span></div>
            </div>
            <div class="headline-chart">
              <div class="hc-head"><span class="lbl">${yn ? 'Chance of yes' : 'Leading: ' + esc(lead.name)}</span><b class="num hc-big" id="hc-big">${pctOf(yn ? O[0] : lead)}</b></div>
              <div id="feat-chart"></div>
            </div>
          </div>
          ${feats.length > 1 ? `<div class="feat-nav"><div class="dots">${feats.map((_, i) => `<i class="${i === featIdx ? 'on' : ''}" data-d="${i}"></i>`).join('')}</div>
            <button class="navpill" data-step="-1">${ICON.chevL}<span>${esc(short(prev.question))}</span></button><button class="navpill" data-step="1"><span>${esc(short(next.question))}</span>${ICON.chevR}</button></div>` : ''}
        </div>
        <aside class="board">
          <div class="board-head"><h3>The board</h3><span class="lbl">Hot right now</span></div>
          ${hot.map((h, i) => `<a class="hot-row" href="#/market/${h.id}"><span class="rk">${i + 1}</span><span class="t">${esc(h.question)}</span>
            <span class="v num">${h.volume24h > 0 ? vol(h.volume24h) + ' ' + ICON.flame : vol(h.volume)}</span></a>`).join('')}
          <a class="tape" href="#/create"><span class="tape-main">Put money on it ${ICON.arrowR}</span><span class="tape-sub">Propose a bet. Your circle or the whole site.</span></a>
          <a class="poster-tile" href="#/games/chicken">${poster('chicken')}<div><b>Chicken</b><span>Cross the road. Cash out before a car does.</span></div></a>
        </aside></section>`;
      const target = top.querySelector('#feat-chart');
      const paint = (d) => {
        if (dead || !top.contains(target)) return;
        const series = m.binary ? [{ idx: 0, name: O[0].name, color: COLORS[0] }]
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
      root.querySelector('#count').textContent = `${rows.length} slip${rows.length === 1 ? '' : 's'}`;
      const ids = new Set(rows.map((m) => m.id));
      if (!rows.length) {
        const noCircles = !S.myCircles.length;
        host.innerHTML = st.bm ? emptyState({ art: 'bookmark', tone: 'lime', kicker: 'Nothing saved', title: 'No bookmarks.', text: "Tap the bookmark on a slip to pin it here. We'll pretend you're organized." })
          : st.q || st.category || st.circle || st.status === 'resolved'
            ? emptyState({ art: 'lens', tone: 'cream', kicker: 'No results', title: 'Nothing matches that.', text: "Try other words, or another circle. Or accept that nobody's been dumb enough to bet on it yet." })
            : noCircles
              ? emptyState({ art: 'chip', tone: 'verm', kicker: 'First things first', title: 'No circle, no one to lose to.', text: 'Private bets live inside circles. Start one for your friends, join one with a code, or put up a public bet for the whole site.', actions: `<a class="btn btn-primary" href="#/circles">${ICON.users} Make or join a circle</a><a class="btn btn-secondary" href="#/create?scope=site">${ICON.globe} Propose a public bet</a>` })
              : emptyState({ art: 'slip', tone: 'cream', kicker: 'Empty book', title: 'Quiet in here.', text: 'Nobody has put a bad idea on the table yet. Say something dumb and put money on it.', actions: `<a class="btn btn-primary" href="#/create">${ICON.plus} Propose a bet</a>` });
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
      pop.innerHTML = `<h6>Sort by</h6>${SORTS.map(([k, l]) => `<button data-s="${k}" class="${st.sort === k ? 'on' : ''}">${l}</button>`).join('')}
        <h6>Show</h6><button data-t="open" class="${st.status === 'open' ? 'on' : ''}">Open bets</button><button data-t="resolved" class="${st.status === 'resolved' ? 'on' : ''}">Settled bets</button>`;
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
