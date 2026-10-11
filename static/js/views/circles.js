import { post } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, ICON, circleMark } from '../util.js';
import { emptyState } from './components.js';
import { toast, modal } from '../ui.js';
import { t, th, tp } from '../i18n.js';

const EMOJIS = ['👥', '🔥', '🎯', '🍻', '🎮', '⚽', '🏀', '🏠', '🎓', '💼', '🌎', '🐸', '👑', '🦄', '🚀', '🎲'];

export function circleCard(c, joinBtn = false) {
  return `<div class="ccard" data-open="${c.id}">
    <div class="row" style="gap:14px">${circleMark(c, 54)}
      <div class="grow"><h3 class="ellipsis">${esc(c.name)}</h3>
        <div class="row" style="gap:6px;margin-top:3px"><span class="tag">${c.visibility === 'public' ? ICON.globe + ' ' + t('Público') : ICON.lock + ' ' + t('Privado')}</span>
          ${c.isOwner ? `<span class="tag res">${t('Dueño')}</span>` : ''}</div></div></div>
    <p>${esc(c.description) || '&nbsp;'}</p>
    <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px"><span class="mono muted" style="font-size:12px;letter-spacing:.04em;text-transform:uppercase">${tp(c.memberCount, '{n} miembro', '{n} miembros')} · ${esc(c.ownerName)}</span>
      ${joinBtn ? `<button class="btn btn-primary btn-sm" data-join="${c.id}">${t('Unirme')}</button>` : ''}</div></div>`;
}

export function openCreateCircle() {
  let vis = 'private', emoji = '👥';
  const m = modal(`<span class="lbl">${t('Mesa nueva')}</span><h2>${t('Crea un círculo')}</h2><p class="lede">${t('Un círculo es tu grupo. Las apuestas, los castigos y los premios viven dentro. Elige gente contra la que aguantes perder.')}</p>
    <form id="cc-form" autocomplete="off">
      <div class="field"><label>${t('Nombre')}</label><input class="input" id="cc-name" maxlength="40" placeholder="${esc(t('Los de siempre'))}"></div>
      <div class="field"><label>${t('Descripción')} <span class="muted" style="font-weight:400">${t('(opcional)')}</span></label><input class="input" id="cc-desc" maxlength="200" placeholder="${esc(t('Discutiendo desde 2019'))}"></div>
      <div class="field"><label>${t('Ícono')} <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">${t('(o deja la letra)')}</span></label><div class="emoji-pick" id="cc-emoji">${EMOJIS.map((e) => `<button type="button" data-e="${e}" class="${e === emoji ? 'active' : ''}">${e}</button>`).join('')}</div></div>
      <div class="field"><label>${t('¿Quién puede entrar?')}</label>
        <div class="seg" id="cc-vis" style="align-self:flex-start"><button type="button" data-v="private" class="active">${ICON.lock} ${t('Privado')}</button><button type="button" data-v="public">${ICON.globe} ${t('Público')}</button></div>
        <small id="cc-help">${t('Solo con código de invitación. Los desconocidos ni lo ven.')}</small></div>
      <div class="error-text" id="cc-err" style="min-height:18px"></div>
      <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn btn-primary">${t('Crearlo')}</button></div>
    </form>`);
  m.el.querySelector('#cc-emoji').addEventListener('click', (e) => { const b = e.target.closest('[data-e]'); if (!b) return; emoji = b.dataset.e; m.el.querySelectorAll('#cc-emoji button').forEach((x) => x.classList.toggle('active', x === b)); });
  m.el.querySelector('#cc-vis').addEventListener('click', (e) => {
    const b = e.target.closest('[data-v]'); if (!b) return; vis = b.dataset.v;
    m.el.querySelectorAll('#cc-vis button').forEach((x) => x.classList.toggle('active', x === b));
    m.el.querySelector('#cc-help').textContent = vis === 'private' ? t('Solo con código de invitación. Los desconocidos ni lo ven.') : t('Cualquiera en este sitio puede encontrarlo, leer sus apuestas y sentarse.');
  });
  m.el.querySelector('#cc-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = m.el.querySelector('#cc-err'); err.textContent = '';
    try {
      const d = await post('/api/circles', { name: m.el.querySelector('#cc-name').value, description: m.el.querySelector('#cc-desc').value, visibility: vis, emoji });
      await loadCircles(); m.close(); toast(t('Círculo abierto. Comparte el código con gente de confianza (o no).'), 'ok'); go(`#/circle/${d.circle.id}`);
    } catch (ex) { err.textContent = ex.message; }
  });
}

export function openJoinByCode() {
  const m = modal(`<span class="lbl">${t('Contraseña en la puerta')}</span><h2>${t('¿Tienes un código?')}</h2><p class="lede">${t('Seis letras. Las tiene quien administra el círculo.')}</p>
    <form id="jc-form" autocomplete="off"><div class="field"><input class="input" id="jc-code" maxlength="6" placeholder="ABC123" style="text-transform:uppercase;letter-spacing:.3em;font-weight:700;text-align:center;font-size:20px;height:52px"></div>
    <div class="error-text" id="jc-err" style="min-height:18px"></div>
    <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn btn-primary">${t('Pasar')}</button></div></form>`);
  m.el.querySelector('#jc-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const d = await post('/api/circles/join', { code: m.el.querySelector('#jc-code').value });
      await loadCircles(); m.close(); toast(t('Ya estás en {circulo}.', { circulo: d.circle.name }), 'ok'); go(`#/circle/${d.circle.id}`);
    } catch (ex) { m.el.querySelector('#jc-err').textContent = ex.message; }
  });
}

export default {
  async mount(root) {
    let dead = false;
    const draw = async () => {
      const d = await loadCircles();
      if (dead) return;
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">${t('Las mesas donde te sientas')}</span><h1 class="page-title">${t('Tus círculos.')}</h1></div>
          <div class="row"><button class="btn btn-secondary" id="b-join">${t('¿Tienes un código?')}</button><button class="btn btn-primary" id="b-new">${ICON.plus} ${t('Crea un círculo')}</button></div></div>
        ${d.mine.length ? `<div class="circle-grid">${d.mine.map((c) => circleCard(c)).join('')}</div>`
          : emptyState({ art: 'cards', tone: 'cream', kicker: t('Silla vacía'), title: esc(t('Mesa para uno. Qué triste.')), text: esc(t('Crea un círculo y jala a tus amigos, o ruégale a alguien por su código.')) })}
        <div class="section-head" style="margin-top:52px"><div><span class="kicker">${t('Pásele sin reservación')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Círculos públicos.')}</h2></div></div>
        ${d.discover.length ? `<div class="circle-grid">${d.discover.map((c) => circleCard(c, true)).join('')}</div>`
          : `<p class="quiet">${t('Ahorita no hay círculos públicos. Los privados nunca salen aquí. Esa es la idea.')}</p>`}
      </div>`;
    };
    await draw();
    root.addEventListener('click', async (e) => {
      if (e.target.closest('#b-new')) return openCreateCircle();
      if (e.target.closest('#b-join')) return openJoinByCode();
      const j = e.target.closest('[data-join]');
      if (j) { e.stopPropagation(); try { await post(`/api/circles/${j.dataset.join}/join`, {}); toast(t('Acercaste una silla.'), 'ok'); go(`#/circle/${j.dataset.join}`); } catch (ex) { toast(ex.message, 'err'); } return; }
      const c = e.target.closest('[data-open]'); if (c) go(`#/circle/${c.dataset.open}`);
    });
    return { onEvent(ev) { if (ev.type === 'circle') draw(); }, unmount() { dead = true; } };
  },
};
