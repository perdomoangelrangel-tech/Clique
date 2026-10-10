/* The Store: cosmetics paid for from the accumulated account. Nothing here changes odds, payouts or outcomes. */
import { get, post } from '../api.js';
import { S, setUser } from '../state.js';
import { esc, money, moneyFull, ICON, avatar } from '../util.js';
import { toast, modal } from '../ui.js';
import { productArt } from '../cosmetics.js';
import { titleHtml } from '../looks.js';
import { emptyState } from './components.js';

const TABS = [['all', 'Everything'], ['avatar', 'Pictures'], ['frame', 'Frames'], ['badge', 'Badges'], ['title', 'Titles'], ['banner', 'Banners'], ['accent', 'Colours'], ['font', 'Fonts'], ['mine', 'What I own']];
const rid = () => 'buy-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);

export default {
  async mount(root, [kind]) {
    let D = await get('/api/store'), tab = TABS.some(([k]) => k === kind) ? kind : 'all', dead = false;

    const card = (it) => {
      let action;
      if (it.owned && it.equipped && it.free) action = '<span class="tag">In use</span>';
      else if (it.owned && it.equipped) action = `<button class="btn btn-secondary btn-sm" data-un="${it.kind}">Take off</button>`;
      else if (it.owned) action = `<button class="btn btn-primary btn-sm" data-eq="${it.id}">Equip</button>`;
      else if (it.state === 'locked') action = `<button class="btn btn-secondary btn-sm" disabled title="${esc(it.requirementText)}">Locked</button>`;
      else if (it.state === 'unavailable') action = '<button class="btn btn-secondary btn-sm" disabled>Not on sale</button>';
      else if (!it.affordable) action = `<button class="btn btn-secondary btn-sm" disabled>Need ${money(it.price - D.accumulated)} more</button>`;
      else action = `<button class="btn btn-primary btn-sm" data-buy="${it.id}">Buy ${money(it.price, { noCents: true })}</button>`;
      return `<article class="prod ${it.owned ? 'owned' : ''} ${it.equipped ? 'on' : ''} ${it.state === 'locked' ? 'locked' : ''}" data-id="${it.id}">
        <div class="prod-art k-${it.kind}">${productArt(it, { name: S.user.username, size: 72, fonts: D.fonts })}</div>
        <div class="prod-body"><div class="prod-top"><b>${esc(it.name)}</b><span class="tag">${esc(D.kinds[it.kind].replace(/ (around|beside|under).*/, '').replace('Profile picture', 'Picture'))}</span></div>
          <p class="muted">${esc(it.desc)}</p>
          ${it.state === 'locked' ? `<div class="prod-req" title="Requirement"><span>${ICON.lock}</span> ${esc(it.requirementText)}${it.progress ? ` <b class="num">(${it.progress.have}/${it.progress.need})</b>` : ''}</div>`
            : it.requirementText && !it.owned ? `<div class="prod-req ok"><span>${ICON.check}</span> ${esc(it.requirementText)}</div>` : ''}
          <div class="prod-foot"><span class="prod-price num">${it.free ? 'Free' : it.owned ? 'Owned' : money(it.price, { noCents: true })}</span>${action}</div></div></article>`;
    };

    const yourLook = () => `<div class="card-box pad-lg yl"><div class="yl-who">${avatar(S.user.username, 72)}<div><b>${esc(S.user.username)}</b>${titleHtml(S.user.username)}
        <a class="muted" href="#/u/${esc(S.user.username)}/edit">Customize your whole profile ${ICON.arrowR}</a></div></div>
      <div class="yl-bal"><span class="lbl">Accumulated account</span><b class="num">${moneyFull(D.accumulated)}</b>
        <small class="muted">Weekly rewards land here. The Store and the Exchange spend from it. Your weekly account (${money(D.weekly)}) can not buy anything.</small></div></div>`;

    function draw() {
      const kept = root.querySelector('#stabs')?.scrollLeft || 0;     // the tab row slides sideways on a phone; a redraw must not snap it back
      const items = D.items.filter((i) => tab === 'all' || (tab === 'mine' ? i.owned && !i.free : i.kind === tab)).map((i, n) => [i, n]).sort((a, b) => (a[0].free - b[0].free) || (a[1] - b[1])).map(([i]) => i);   // things you can buy first, the free ones after
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">Spend what you keep</span><h1 class="page-title">The store.</h1></div></div>
        ${yourLook()}
        <p class="muted" style="margin:14px 2px 0;max-width:70ch">Everything here is for show: pictures, frames, badges, titles, banners, colours and fonts. None of it changes a price, an odd, a payout or a result, anywhere in Clique. Prices are in pretend money.</p>
        <div class="tabs" id="stabs" style="margin-top:20px">${TABS.map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${l}</button>`).join('')}</div>
        ${items.length ? `<div class="prods">${items.map(card).join('')}</div>`
          : emptyState({ art: 'shelf', tone: 'cream', tight: true, kicker: 'Empty shelf', title: tab === 'mine' ? 'You have not bought anything yet.' : 'Nothing here.', text: tab === 'mine' ? 'Earn a weekly reward, then come back and spend it.' : 'Try another shelf.' })}</div>`;
      const strip = root.querySelector('#stabs'), on = strip && strip.querySelector('.active');
      if (strip && on) {
        strip.scrollLeft = kept;
        if (on.offsetLeft < kept || on.offsetLeft + on.offsetWidth > kept + strip.clientWidth) strip.scrollLeft = on.offsetLeft - 12;   // keep the open shelf in view
      }
    }

    function confirmBuy(it) {
      const after = Math.round((D.accumulated - it.price) * 100) / 100;
      const id = rid();                                   // one id for this purchase, however many times the button is pressed
      const m = modal(`<span class="lbl">Confirm purchase</span><h2>${esc(it.name)}</h2>
        <div class="buy-art">${productArt(it, { name: S.user.username, size: 84, fonts: D.fonts })}</div>
        <p class="lede">${esc(it.desc)}</p>
        <div class="buy-lines"><div><span>Price</span><b class="num">${moneyFull(it.price)}</b></div>
          <div><span>Accumulated account now</span><b class="num">${moneyFull(D.accumulated)}</b></div>
          <div class="after"><span>Left after buying</span><b class="num">${moneyFull(after)}</b></div></div>
        <p class="muted" style="font-size:13px">Paid from your <b>accumulated</b> account. Your weekly account is not touched. You can not buy the same thing twice.</p>
        <div class="error-text" id="buy-err" style="min-height:18px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>Not now</button><button class="btn btn-primary" id="buy-go">Buy for ${money(it.price)}</button></div>`);
      m.el.querySelector('#buy-go').addEventListener('click', async (e) => {
        e.target.disabled = true;
        try {
          const d = await post('/api/store/buy', { item: it.id, requestId: id });
          D = d.store; setUser(d.user); m.close(); draw();
          toast(`${it.name} is yours. ${money(d.after)} left.`, 'ok');
        } catch (ex) { m.el.querySelector('#buy-err').textContent = ex.message; e.target.disabled = false; get('/api/store').then((s) => { D = s; draw(); }).catch(() => {}); }
      });
    }

    root.addEventListener('click', async (e) => {
      const b = e.target.closest('button'); if (!b) return;
      try {
        if (b.dataset.t) { tab = b.dataset.t; history.replaceState(null, '', tab === 'all' ? '#/store' : `#/store/${tab}`); draw(); }
        else if (b.dataset.buy) { const fresh = await get('/api/store'); D = fresh; draw(); const it = D.items.find((i) => i.id === b.dataset.buy); if (it && !it.owned && it.affordable && !it.state) confirmBuy(it); else toast('That changed while you were looking. Check it again.', 'err'); }
        else if (b.dataset.eq) { const d = await post('/api/store/equip', { item: b.dataset.eq }); D = d.store; draw(); toast('Equipped. Everybody sees it now.', 'ok'); }
        else if (b.dataset.un) { const d = await post('/api/store/unequip', { kind: b.dataset.un }); D = d.store; draw(); }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    draw();
    return { onEvent(ev) { if (ev.type === 'reward') get('/api/store').then((s) => { if (!dead) { D = s; draw(); } }).catch(() => {}); }, unmount() { dead = true; } };
  },
};
