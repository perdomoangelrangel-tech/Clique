/* The Store: cosmetics paid for from the accumulated account. Nothing here changes odds, payouts or outcomes. */
import { get, post } from '../api.js';
import { S, setUser } from '../state.js';
import { esc, money, moneyFull, ICON, avatar } from '../util.js';
import { toast, modal } from '../ui.js';
import { productArt } from '../cosmetics.js';
import { titleHtml } from '../looks.js';
import { emptyState } from './components.js';
import { t, th } from '../i18n.js';

const TABS = [['all', 'Todo'], ['avatar', 'Fotos'], ['frame', 'Marcos'], ['badge', 'Insignias'], ['title', 'Títulos'], ['banner', 'Portadas'], ['accent', 'Colores'], ['font', 'Letras'], ['mine', 'Lo que tengo']];      // i18n: claves
const KIND_NAME = { avatar: 'Foto', frame: 'Marco', badge: 'Insignia', title: 'Título', banner: 'Portada', accent: 'Color', font: 'Letra del nombre' };      // i18n: claves
const rid = () => 'buy-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);

export default {
  async mount(root, [kind]) {
    let D = await get('/api/store'), tab = TABS.some(([k]) => k === kind) ? kind : 'all', dead = false;

    const card = (it) => {
      let action;
      if (it.owned && it.equipped && it.free) action = `<span class="tag">${t('En uso')}</span>`;
      else if (it.owned && it.equipped) action = `<button class="btn btn-secondary btn-sm" data-un="${it.kind}">${t('Quitar')}</button>`;
      else if (it.owned) action = `<button class="btn btn-primary btn-sm" data-eq="${it.id}">${t('Usar')}</button>`;
      else if (it.state === 'locked') action = `<button class="btn btn-secondary btn-sm" disabled title="${esc(it.requirementText)}">${t('Bloqueado')}</button>`;
      else if (it.state === 'unavailable') action = `<button class="btn btn-secondary btn-sm" disabled>${t('No está a la venta')}</button>`;
      else if (!it.affordable) action = `<button class="btn btn-secondary btn-sm" disabled>${t('Te faltan {cantidad}', { cantidad: money(it.price - D.accumulated) })}</button>`;
      else action = `<button class="btn btn-primary btn-sm" data-buy="${it.id}">${t('Comprar por {cantidad}', { cantidad: money(it.price, { noCents: true }) })}</button>`;
      return `<article class="prod ${it.owned ? 'owned' : ''} ${it.equipped ? 'on' : ''} ${it.state === 'locked' ? 'locked' : ''}" data-id="${it.id}">
        <div class="prod-art k-${it.kind}">${productArt(it, { name: S.user.username, size: 72, fonts: D.fonts })}</div>
        <div class="prod-body"><div class="prod-top"><b>${esc(it.name)}</b><span class="tag">${esc(KIND_NAME[it.kind] ? t(KIND_NAME[it.kind]) : D.kinds[it.kind])}</span></div>
          <p class="muted">${esc(it.desc)}</p>
          ${it.state === 'locked' ? `<div class="prod-req" title="${esc(t('Requisito'))}"><span>${ICON.lock}</span> ${esc(it.requirementText)}${it.progress ? ` <b class="num">(${it.progress.have}/${it.progress.need})</b>` : ''}</div>`
            : it.requirementText && !it.owned ? `<div class="prod-req ok"><span>${ICON.check}</span> ${esc(it.requirementText)}</div>` : ''}
          <div class="prod-foot"><span class="prod-price num">${it.free ? t('Gratis') : it.owned ? t('Tuyo') : money(it.price, { noCents: true })}</span>${action}</div></div></article>`;
    };

    const yourLook = () => `<div class="card-box pad-lg yl"><div class="yl-who">${avatar(S.user.username, 72)}<div><b>${esc(S.user.username)}</b>${titleHtml(S.user.username)}
        <a class="muted" href="#/u/${esc(S.user.username)}/edit">${t('Personaliza todo tu perfil')} ${ICON.arrowR}</a></div></div>
      <div class="yl-bal"><span class="lbl">${t('Cuenta acumulada')}</span><b class="num">${moneyFull(D.accumulated)}</b>
        <small class="muted">${t('Aquí llegan los premios semanales. La Tienda y la Bolsa gastan de aquí. Tu cuenta semanal ({cantidad}) no puede comprar nada.', { cantidad: money(D.weekly) })}</small></div></div>`;

    function draw() {
      const kept = root.querySelector('#stabs')?.scrollLeft || 0;     // the tab row slides sideways on a phone; a redraw must not snap it back
      const items = D.items.filter((i) => tab === 'all' || (tab === 'mine' ? i.owned && !i.free : i.kind === tab)).map((i, n) => [i, n]).sort((a, b) => (a[0].free - b[0].free) || (a[1] - b[1])).map(([i]) => i);   // things you can buy first, the free ones after
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">${t('Gasta lo que guardas')}</span><h1 class="page-title">${t('La tienda.')}</h1></div></div>
        ${yourLook()}
        <p class="muted" style="margin:14px 2px 0;max-width:70ch">${t('Todo aquí es de adorno: fotos, marcos, insignias, títulos, portadas, colores y letras. Nada cambia un precio, una probabilidad, un pago ni un resultado en ningún lugar de Clique. Los precios son en fichas de juego.')}</p>
        <div class="tabs" id="stabs" style="margin-top:20px">${TABS.map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${esc(t(l))}</button>`).join('')}</div>
        ${items.length ? `<div class="prods">${items.map(card).join('')}</div>`
          : emptyState({ art: 'shelf', tone: 'cream', tight: true, kicker: t('Repisa vacía'), title: esc(tab === 'mine' ? t('Todavía no has comprado nada.') : t('Aquí no hay nada.')), text: esc(tab === 'mine' ? t('Gana un premio semanal y regresa a gastarlo.') : t('Prueba otra repisa.')) })}</div>`;
      const strip = root.querySelector('#stabs'), on = strip && strip.querySelector('.active');
      if (strip && on) {
        strip.scrollLeft = kept;
        if (on.offsetLeft < kept || on.offsetLeft + on.offsetWidth > kept + strip.clientWidth) strip.scrollLeft = on.offsetLeft - 12;   // keep the open shelf in view
      }
    }

    function confirmBuy(it) {
      const after = Math.round((D.accumulated - it.price) * 100) / 100;
      const id = rid();                                   // one id for this purchase, however many times the button is pressed
      const m = modal(`<span class="lbl">${t('Confirma la compra')}</span><h2>${esc(it.name)}</h2>
        <div class="buy-art">${productArt(it, { name: S.user.username, size: 84, fonts: D.fonts })}</div>
        <p class="lede">${esc(it.desc)}</p>
        <div class="buy-lines"><div><span>${t('Precio')}</span><b class="num">${moneyFull(it.price)}</b></div>
          <div><span>${t('Cuenta acumulada ahora')}</span><b class="num">${moneyFull(D.accumulated)}</b></div>
          <div class="after"><span>${t('Te quedan después de comprar')}</span><b class="num">${moneyFull(after)}</b></div></div>
        <p class="muted" style="font-size:13px">${t('Se paga con tu cuenta <b>acumulada</b>. Tu cuenta semanal no se toca. No puedes comprar lo mismo dos veces.')}</p>
        <div class="error-text" id="buy-err" style="min-height:18px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Ahora no')}</button><button class="btn btn-primary" id="buy-go">${t('Comprar por {cantidad}', { cantidad: money(it.price) })}</button></div>`);
      m.el.querySelector('#buy-go').addEventListener('click', async (e) => {
        e.target.disabled = true;
        try {
          const d = await post('/api/store/buy', { item: it.id, requestId: id });
          D = d.store; setUser(d.user); m.close(); draw();
          toast(t('{producto} ya es tuyo. Te quedan {cantidad}.', { producto: it.name, cantidad: money(d.after) }), 'ok');
        } catch (ex) { m.el.querySelector('#buy-err').textContent = ex.message; e.target.disabled = false; get('/api/store').then((s) => { D = s; draw(); }).catch(() => {}); }
      });
    }

    root.addEventListener('click', async (e) => {
      const b = e.target.closest('button'); if (!b) return;
      try {
        if (b.dataset.t) { tab = b.dataset.t; history.replaceState(null, '', tab === 'all' ? '#/store' : `#/store/${tab}`); draw(); }
        else if (b.dataset.buy) { const fresh = await get('/api/store'); D = fresh; draw(); const it = D.items.find((i) => i.id === b.dataset.buy); if (it && !it.owned && it.affordable && !it.state) confirmBuy(it); else toast(t('Eso cambió mientras mirabas. Revísalo otra vez.'), 'err'); }
        else if (b.dataset.eq) { const d = await post('/api/store/equip', { item: b.dataset.eq }); D = d.store; draw(); toast(t('Listo. Ya todos lo ven.'), 'ok'); }
        else if (b.dataset.un) { const d = await post('/api/store/unequip', { kind: b.dataset.un }); D = d.store; draw(); }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    draw();
    return { onEvent(ev) { if (ev.type === 'reward') get('/api/store').then((s) => { if (!dead) { D = s; draw(); } }).catch(() => {}); }, unmount() { dead = true; } };
  },
};
