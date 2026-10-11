import { get, post } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, debounce, ICON } from '../util.js';
import { modal, toast } from '../ui.js';
import { emptyState } from './components.js';
import { amt, blindsText, moneyTag, initials } from './pokerfmt.js';
import { t, th, tp } from '../i18n.js';

export default {
  async mount(root) {
    let tables = [], dead = false, busy = false;

    root.innerHTML = `<div class="page pk-lobby">
      <div class="lobby-head"><div><span class="kicker">${t("El salón de póker // Texas Hold'em")}</span>
        <h1>${t('Acerca')}<br><em>${t('una silla.')}</em></h1>
        <p>${t("Hold'em sin límite contra tus amigos, en vivo. Fichas de práctica o de tu saldo: la mesa lo decide antes de la primera mano.")}</p></div>
        <div class="pk-actions"><button class="btn btn-primary btn-lg" id="pk-new">${ICON.plus} ${t('Abrir una mesa')}</button></div></div>
      <div id="pk-mine"></div>
      <div class="pk-cols"><section><div class="pk-sec-head"><h2>${t('Mesas públicas')}</h2><span class="lbl" id="pk-count"></span></div><div class="pk-list" id="pk-list"></div></section>
        <aside class="pk-code card-box paper"><span class="lbl">${t('Mesa privada')}</span><h3>${t('¿Tienes un código?')}</h3>
          <p>${t('Quien abrió la mesa tiene un código de seis caracteres. Escríbelo y ya estás sentado.')}</p>
          <form id="pk-join-code"><input class="input" id="pk-code" maxlength="6" placeholder="ABC123" autocomplete="off" aria-label="${esc(t('Código de la mesa'))}"><button class="btn btn-primary" id="pk-code-go">${t('Sentarme')}</button></form>
          <div class="error-text" id="pk-code-err"></div></aside></div></div>`;
    const $ = (s) => root.querySelector(s);

    const seatsRow = (tb) => `<div class="pk-dots" aria-label="${esc(t('{n} de {total} lugares ocupados', { n: tb.players.length, total: tb.maxSeats }))}">${Array.from({ length: tb.maxSeats }, (_, i) => `<i class="${tb.players[i] ? 'on' : ''}">${tb.players[i] ? initials(tb.players[i]) : ''}</i>`).join('')}</div>`;
    const card = (tb) => `<article class="pk-card ${tb.mine ? 'mine' : ''}" data-id="${tb.id}">
      <div class="pk-card-top"><div><h3>${esc(tb.name)}</h3><div class="pk-sub">${th('La abrió <b>{nombre}</b>', { nombre: tb.hostName || '?' })} · ${tb.visibility === 'private' ? t('Privada') : t('Pública')}</div></div>${moneyTag(tb.money)}</div>
      ${seatsRow(tb)}
      <div class="pk-who">${tb.players.length ? th('<b>{n} de {total}</b> sentados: {nombres}', { n: tb.players.length, total: tb.maxSeats, nombres: tb.players.join(', ') }) : `<b>${t('Vacía.')}</b> ${t('Alguien tiene que ser el primero.')}`}</div>
      <div class="pk-card-foot"><span class="pk-meta"><span>${t('Ciegas')} <b class="num">${blindsText(tb.smallBlind, tb.bigBlind, tb.scale)}</b></span><span>${tb.money === 'real' ? t('Entrada') : t('Fichas iniciales')} <b class="num">${amt(tb.stack, tb.scale)}</b></span>
        <span class="pk-status ${tb.status}">${tb.status === 'playing' ? t('En juego · mano {n}', { n: tb.handNo }) : t('Esperando para empezar')}</span></span>
        <span class="pk-btns">${tb.mine ? `<button class="btn btn-primary btn-sm" data-act="open">${t('Volver a mi mesa')}</button>`
          : `<button class="btn btn-secondary btn-sm" data-act="watch">${t('Mirar')}</button><button class="btn btn-primary btn-sm" data-act="sit" ${tb.full ? 'disabled' : ''}>${tb.full ? t('Llena') : t('Sentarme')}</button>`}</span></div></article>`;

    function draw() {
      const mine = tables.find((x) => x.mine);
      $('#pk-mine').innerHTML = mine ? `<div class="pk-banner"><span class="vb-tag">${t('Estás sentado')}</span><span>${th('Estás en <b>{mesa}</b>. Una mesa a la vez.', { mesa: mine.name })}</span><button class="btn btn-sm vb-btn" data-open="${mine.id}">${t('Volver a la mesa')}</button></div>` : '';
      const pub = tables.filter((x) => x.visibility === 'public' && !x.mine);
      const own = tables.filter((x) => x.mine);
      $('#pk-count').textContent = tp(pub.length, '{n} abierta', '{n} abiertas');
      $('#pk-list').innerHTML = own.concat(pub).length
        ? own.concat(pub).map(card).join('')
        : emptyState({ art: 'poker', tone: 'lime', kicker: t('Sin mesas'), title: esc(t('Nadie está jugando.')), text: esc(t('Abre una mesa y espera a tus amigos. O ábrela y haz como que estás ocupado.')), actions: `<button class="btn btn-primary" data-new>${ICON.plus} ${t('Abrir una mesa')}</button>` });
    }
    async function load() {
      const d = await get('/api/poker/tables');
      if (dead) return;
      tables = d.tables; if (d.user) setUser(d.user);
      draw();
    }

    async function sit(tb) {
      if (busy) return; busy = true;
      try {
        let confirm = false;
        if (tb.money === 'real' && tb.status === 'playing') {
          confirm = await new Promise((res) => {
            const m = modal(`<span class="lbl">${t('Fichas de tu saldo')}</span><h2>${t('¿Entrar con {cantidad}?', { cantidad: amt(tb.stack, tb.scale) })}</h2><p class="lede">${t('Esta mesa juega con fichas de tu saldo. La entrada sale de tu cuenta ahora, se queda frente a ti y regresa a tu cuenta cuando te levantas.')}</p>
              <div class="modal-actions"><button class="btn btn-secondary" data-no>${t('Mejor no')}</button><button class="btn btn-primary" data-yes>${t('Entrar')}</button></div>`);
            m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); res(true); });
            m.el.querySelector('[data-no]').addEventListener('click', () => { m.close(); res(false); });
          });
          if (!confirm) { busy = false; return; }
        }
        const d = await post('/api/poker/join', { id: tb.id, confirm });
        if (d.user) setUser(d.user);
        go(`#/poker/${tb.id}`);
      } catch (ex) { toast(ex.message, 'err'); load().catch(() => {}); }
      busy = false;
    }

    function openCreate() {
      const m = modal(`<span class="lbl">${t('Mesa nueva')}</span><h2>${t('Abrir una mesa')}</h2><p class="lede">${t('Vas a ser quien la abre y elegirás los ajustes después. Todos los que se sienten tienen que aceptarlos.')}</p>
        <div class="field"><label for="nt-name">${t('Nombre')}</label><input class="input" id="nt-name" maxlength="30" placeholder="${esc(t('La mesa de {nombre}', { nombre: S.user.username }))}" autocomplete="off"></div>
        <div class="field"><label>${t('¿Quién se puede sentar?')}</label><div class="seg" id="nt-vis"><button type="button" data-v="public" class="active">${ICON.globe} ${t('Cualquiera')}</button><button type="button" data-v="private">${ICON.lock} ${t('Solo con código')}</button></div>
          <small id="nt-help">${t('Aparece en el salón de póker. Cualquiera puede sentarse o mirar.')}</small></div>
        <div class="field"><label for="nt-seats">${t('Lugares')}</label><select class="select" id="nt-seats">${[2, 3, 4, 5, 6, 7, 8, 9].map((n) => `<option ${n === 6 ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
        <div class="error-text" id="nt-err" style="min-height:18px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn btn-primary" id="nt-go">${t('Abrirla')}</button></div>`);
      let vis = 'public';
      m.el.querySelector('#nt-vis').addEventListener('click', (e) => {
        const b = e.target.closest('[data-v]'); if (!b) return;
        vis = b.dataset.v; m.el.querySelectorAll('#nt-vis button').forEach((x) => x.classList.toggle('active', x === b));
        m.el.querySelector('#nt-help').textContent = vis === 'public' ? t('Aparece en el salón de póker. Cualquiera puede sentarse o mirar.') : t('Oculta. Tus amigos necesitan el código de seis caracteres que te vamos a dar.');
      });
      m.el.querySelector('#nt-go').addEventListener('click', async () => {
        const err = m.el.querySelector('#nt-err'); err.textContent = '';
        try {
          const d = await post('/api/poker/tables', { name: m.el.querySelector('#nt-name').value.trim() || undefined, visibility: vis, maxSeats: +m.el.querySelector('#nt-seats').value });
          m.close(); go(`#/poker/${d.table.id}`);
        } catch (ex) { err.textContent = ex.message; }
      });
    }

    root.addEventListener('click', (e) => {
      if (e.target.closest('#pk-new') || e.target.closest('[data-new]')) return openCreate();
      const open = e.target.closest('[data-open]'); if (open) return go(`#/poker/${open.dataset.open}`);
      const b = e.target.closest('[data-act]'); if (!b) return;
      const tb = tables.find((x) => x.id === b.closest('.pk-card').dataset.id); if (!tb) return;
      if (b.dataset.act === 'sit') sit(tb); else go(`#/poker/${tb.id}`);
    });
    $('#pk-code').addEventListener('input', (e) => { e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''); });
    $('#pk-join-code').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = $('#pk-code-err'); err.textContent = '';
      const code = $('#pk-code').value.trim();
      if (code.length < 6) { err.textContent = t('Los códigos tienen seis caracteres.'); return; }
      try { const d = await post('/api/poker/join', { code }); if (d.user) setUser(d.user); go(`#/poker/${d.table.id}`); }
      catch (ex) { err.textContent = ex.message; }
    });

    await load();
    const poll = setInterval(() => load().catch(() => {}), 6000);
    const reload = debounce(() => load().catch(() => {}), 300);
    return { onEvent(ev) { if (ev.type === 'poker') reload(); }, unmount() { dead = true; clearInterval(poll); } };
  },
};
