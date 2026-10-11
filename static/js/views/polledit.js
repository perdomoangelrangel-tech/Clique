/* Editing a published bet: the form, the preview of exactly what will change, the public history, and the exit window.
   The rules themselves (who may edit, what counts as a material change, how long people can walk away) live on the server;
   this only asks the server, shows what it says, and never decides anything. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, dateLong, ago, ICON, money, moneyFull, avatar, slipLabel } from '../util.js';
import { modal, confirmBox, toast } from '../ui.js';
import { saveDraft, loadDraft, clearDraft } from '../viewstate.js';
import { t, th, tp } from '../i18n.js';

const rid = () => 'edit-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const local = (ms) => { if (!ms) return ''; const d = new Date(ms - new Date(ms).getTimezoneOffset() * 60000); return d.toISOString().slice(0, 16); };
const fromLocal = (v) => (v ? new Date(v).getTime() : null);
const when = (ms) => (ms ? dateLong(ms) : t('Sin fecha de cierre'));
const KIND = { created: 'Publicada', clarification: 'Aclaración', material: 'Cambio de fondo', no_participation: 'Editada antes de que alguien apostara' };      // i18n: claves
const kindName = (k) => (KIND[k] ? t(KIND[k]) : k);

/** The "Edited" marker beside a bet's title. */
export const editedTag = (M) => (M.edited ? `<button class="tag edited" id="hist" title="${esc(t('Se cambiaron las reglas o la fecha de cierre de esta apuesta. Mira qué cambió y cuándo.'))}">${ICON.pencil} ${t('Editada · v{n}', { n: M.version })}</button>` : '');

/** The notice shown to people who bet before a material change, while they can still walk away at cost. */
export function exitBanner(M) {
  const e = M.exit;
  if (!e || !e.open || !e.tokens.length) return '';
  const mine = (M.myPositions || []).filter((p) => p.withdrawable);
  if (!mine.length) return '';
  return `<div class="exit-banner" role="status"><div><b>${t('Las reglas o la fecha de cierre cambiaron después de que apostaste.')}</b>
    <p>${th('Puedes retirar lo que apostaste con las reglas viejas y recuperar <b>exactamente lo que pagaste</b>, valga lo que valga ahora, hasta el {fecha}. O no hagas nada y tu apuesta sigue con las reglas nuevas.', { fecha: dateLong(e.until) })}</p></div>
    <div class="exit-acts">${mine.map((p) => `<button class="btn btn-secondary btn-sm" data-withdraw="${esc(p.token)}">${th('Retirar {cantidad} ({opcion})', { cantidad: money(p.invested), opcion: slipLabel(p.label) })}</button>`).join('')}<button class="btn btn-ghost btn-sm" id="hist">${t('Qué cambió')}</button></div></div>`;
}

export async function withdrawFlow(M, token, onDone) {
  const p = (M.myPositions || []).find((x) => x.token === token);
  if (!p) return;
  if (!(await confirmBox({ title: t('¿Retirar tu apuesta?'), text: t('Recuperas exactamente {cantidad}, lo que pagaste por {opcion}, aunque ahora valga otra cantidad. Tus acciones salen del mercado.', { cantidad: moneyFull(p.invested), opcion: slipLabel(p.label) }), confirm: t('Retirar {cantidad}', { cantidad: money(p.invested) }) }))) return;
  try {
    const d = await post(`/api/markets/${M.id}/withdraw`, { token, requestId: rid() });
    setUser(d.user); toast(t('Retirada: {cantidad} regresaron a tu cuenta semanal.', { cantidad: moneyFull(d.refunded) }), 'ok'); onDone(d.market);
  } catch (ex) { toast(ex.message, 'err'); }
}

export async function openHistory(M) {
  let H;
  try { H = await get(`/api/markets/${M.id}/history`); } catch (ex) { toast(ex.message, 'err'); return; }
  const none = `<i>${t('(nada)')}</i>`;
  const rows = [...H.edits].reverse().map((e) => `<li class="vh ${esc(e.class)}"><div class="vh-top"><b>${t('Versión {n}', { n: e.v })}</b><span class="tag ${e.class === 'material' ? 'bad' : ''}">${esc(kindName(e.class))}</span><span class="muted">${esc(dateLong(e.t))} · ${ago(e.t)}</span></div>
      <div class="vh-by">${avatar(e.by.username, 20)} ${e.kind === 'created' ? th('<a href="#/u/{url}">{nombre}</a> la propuso', { url: encodeURIComponent(e.by.username), nombre: e.by.username }) : th('<a href="#/u/{url}">{nombre}</a> la editó', { url: encodeURIComponent(e.by.username), nombre: e.by.username })}</div>
      ${e.reason ? `<p class="vh-why"><em>${t('Por qué:')}</em> ${esc(e.reason)}</p>` : ''}
      ${e.changes && e.changes.closesAt ? `<div class="vh-ch"><span class="lbl">${t('Fecha de cierre')}</span><span class="from">${esc(when(e.changes.closesAt.from))}</span> ${ICON.arrowR} <span class="to">${esc(when(e.changes.closesAt.to))}</span></div>` : ''}
      ${e.changes && e.changes.description ? `<div class="vh-ch"><span class="lbl">${t('Reglas')}</span><div class="from">${esc(e.changes.description.from) || none}</div><div class="to">${esc(e.changes.description.to) || none}</div></div>` : ''}
      ${e.participants ? `<small class="muted">${tp(e.participants, '{n} persona había apostado cuando cambió.', '{n} personas habían apostado cuando cambió.')}</small>` : ''}
      ${e.exitUntil ? `<small class="muted">${t('Quien había apostado antes pudo retirar lo que pagó hasta el {fecha}.', { fecha: dateLong(e.exitUntil) })}</small>` : ''}</li>`).join('');
  modal(`<span class="lbl">${t('Visible para todos en esta apuesta')}</span><h2>${t('Qué cambió')}</h2>
    <p class="lede">${t('Aquí se guarda cada cambio a las reglas o a la fecha de cierre: quién, cuándo, por qué y cómo estaba antes. Un resultado ya decidido nunca se reabre.')}</p>
    <ol class="vh-list">${rows}</ol><div class="modal-actions"><button class="btn btn-primary" data-close>${t('Cerrar')}</button></div>`, { wide: true });
}

/** The edit form. `onSaved(market)` runs after a successful save. */
export function openEditPoll(M, onSaved) {
  const involved = (M.traders > 0) || (M.holders && M.holders.length > 0);
  const base = { closesAt: M.closesAt || null, description: M.rules || '' };
  const draftKey = 'edit:' + M.id, saved = loadDraft(draftKey);
  let restored = false;
  const init = { end: local(base.closesAt), none: !base.closesAt, rules: base.description, why: '', kind: 'material' };
  if (saved) { Object.assign(init, saved); restored = true; }
  const m = modal(`<span class="lbl">${t('Editar esta apuesta')}</span><h2>${t('Cambia la fecha o las reglas')}</h2>
    <div id="pe-step"></div>`, { wide: true, guard: () => dirty() });
  const box = m.el.querySelector('#pe-step');
  let state = { ...init };
  const dirty = () => state.end !== local(base.closesAt) || state.none !== !base.closesAt || state.rules !== base.description || state.why !== '';
  const values = () => ({ closesAt: state.none ? null : fromLocal(state.end), description: state.rules, reason: state.why, kind: state.kind });
  const changedDate = () => (state.none ? !!base.closesAt : !base.closesAt || state.end !== local(base.closesAt));      // the box has no seconds, so compare what it shows
  function form(err = '') {
    const onlyRules = !changedDate();
    box.innerHTML = `${restored ? `<div class="notice">${t('Recuperamos tu edición anterior que no se guardó.')}</div>` : ''}
      ${involved ? `<div class="notice">${tp(M.traders, '{n} persona ya apostó aquí.', '{n} personas ya apostaron aquí.')} ${t('Los cambios se avisan a todos los involucrados, quedan en un historial público y pueden permitirles retirarse. Vas a ver exactamente qué pasa antes de guardar nada.')}</div>` : `<p class="lede" style="margin-top:0">${t('Nadie ha apostado todavía, así que el cambio no afecta a nadie. Igual se guarda como versión nueva.')}</p>`}
      <div class="field"><label for="pe-end">${t('Fecha y hora de cierre')}</label>
        <div class="row" style="gap:12px;flex-wrap:wrap"><input class="input" type="datetime-local" id="pe-end" value="${esc(state.end)}" ${state.none ? 'disabled' : ''} style="max-width:260px">
          <label class="check"><input type="checkbox" id="pe-none" ${state.none ? 'checked' : ''}> ${t('Sin fecha de cierre')}</label></div></div>
      <div class="field"><label for="pe-rules">${t('Reglas (qué cuenta como ganar y la letra chiquita)')}</label><textarea class="input" id="pe-rules" rows="5" maxlength="1000">${esc(state.rules)}</textarea></div>
      ${involved ? `<div class="field"><label>${t('¿Qué tipo de cambio es?')}</label>
        <div class="seg"><label class="seg-opt"><input type="radio" name="pe-kind" value="clarification" ${state.kind === 'clarification' && onlyRules ? 'checked' : ''} ${onlyRules ? '' : 'disabled'}><span><b>${t('Una aclaración')}</b><small>${t('Mismo significado, palabras más claras. Nadie puede retirarse.')} ${onlyRules ? '' : t('No se puede si cambia la fecha: una fecha nueva puede cambiar la respuesta.')}</small></span></label>
          <label class="seg-opt"><input type="radio" name="pe-kind" value="material" ${state.kind === 'material' || !onlyRules ? 'checked' : ''}><span><b>${t('Un cambio de fondo')}</b><small>${t('Cambia qué cuenta o cuándo termina. Quien apostó puede retirar lo que pagó. Se permite una vez por apuesta después de que alguien apostó.')}</small></span></label></div></div>
        <div class="field"><label for="pe-why">${t('¿Por qué la cambias?')} <span class="muted">${t('(lo ven todos, mínimo 10 caracteres)')}</span></label><textarea class="input" id="pe-why" rows="2" maxlength="200">${esc(state.why)}</textarea></div>` : `<div class="field"><label for="pe-why">${t('Motivo')} <span class="muted">${t('(opcional)')}</span></label><input class="input" id="pe-why" maxlength="200" value="${esc(state.why)}"></div>`}
      <div class="error-text" id="pe-err" style="min-height:20px">${esc(err)}</div>
      <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Cancelar')}</button><button class="btn btn-primary" id="pe-prev">${t('Ver qué va a cambiar')}</button></div>`;
    wire();
  }
  function wire() {
    const sync = () => { saveDraft(draftKey, state); };
    box.querySelector('#pe-end').addEventListener('input', (e) => { state.end = e.target.value; sync(); form_refreshKinds(); });
    box.querySelector('#pe-none').addEventListener('change', (e) => { state.none = e.target.checked; box.querySelector('#pe-end').disabled = state.none; if (!state.none && !state.end) { state.end = local(Date.now() + 86400000); box.querySelector('#pe-end').value = state.end; } sync(); form_refreshKinds(); });
    box.querySelector('#pe-rules').addEventListener('input', (e) => { state.rules = e.target.value; sync(); });
    box.querySelector('#pe-why').addEventListener('input', (e) => { state.why = e.target.value; sync(); });
    box.querySelectorAll('input[name="pe-kind"]').forEach((r) => r.addEventListener('change', () => { state.kind = r.value; sync(); }));
    box.querySelector('#pe-prev').addEventListener('click', preview);
  }
  function form_refreshKinds() {                                                    // a date change can only ever be a material change
    if (!involved) return;
    const onlyRules = !changedDate();
    const clar = box.querySelector('input[value="clarification"]'), mat = box.querySelector('input[value="material"]');
    if (clar) { clar.disabled = !onlyRules; if (!onlyRules) { state.kind = 'material'; mat.checked = true; } }
  }
  async function preview() {
    const err = box.querySelector('#pe-err'); err.textContent = '';
    const btn = box.querySelector('#pe-prev'); btn.disabled = true;
    try {
      const v = values();
      const body = { description: v.description, reason: v.reason, kind: involved ? (changedDate() ? 'material' : v.kind) : undefined };
      if (changedDate()) body.closesAt = v.closesAt;
      const d = await post(`/api/markets/${M.id}/edit/preview`, body);
      confirmStep(d.preview, body);
    } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
  }
  function confirmStep(P, body) {
    const ch = P.changes, id = rid();
    const none = `<i>${t('(nada)')}</i>`;
    box.innerHTML = `<div class="pv"><div class="pv-head"><span class="tag ${P.class === 'material' ? 'bad' : ''}">${esc(kindName(P.class))}</span><b>${t('Se guarda como versión {n}', { n: P.newVersion })}</b></div>
      ${ch.closesAt ? `<div class="vh-ch"><span class="lbl">${t('Fecha de cierre')}</span><span class="from">${esc(when(ch.closesAt.from))}</span> ${ICON.arrowR} <span class="to">${esc(when(ch.closesAt.to))}</span></div>` : ''}
      ${ch.description ? `<div class="vh-ch"><span class="lbl">${t('Reglas')}</span><div class="from">${esc(ch.description.from) || none}</div><div class="to">${esc(ch.description.to) || none}</div></div>` : ''}
      <ul class="pv-notes"><li>${esc(P.note)}</li>
        ${P.notifyCount ? `<li>${P.notifyCount > P.notify.length ? tp(P.notifyCount, 'Se le avisa en la app a <b>{n}</b> persona: {nombres} y otros.', 'Se les avisa en la app a <b>{n}</b> personas: {nombres} y otros.', { nombres: esc(P.notify.join(', ')) }) : tp(P.notifyCount, 'Se le avisa en la app a <b>{n}</b> persona: {nombres}.', 'Se les avisa en la app a <b>{n}</b> personas: {nombres}.', { nombres: esc(P.notify.join(', ')) })}</li>` : ''}${''/* html: seguro (los nombres se escapan al pasarlos) */}
        ${P.exitUntil ? `<li>${th('Quien apostó con las reglas viejas puede retirar lo que pagó hasta el <b>{fecha}</b>.', { fecha: dateLong(P.exitUntil) })}</li>` : ''}
        <li>${t('No cambia nada de las apuestas, saldos ni acciones de nadie. El historial guarda los valores viejos, quién los cambió, cuándo y por qué.')}</li>
        ${body.reason ? `<li>${th('Motivo que verán todos: <i>{motivo}</i>', { motivo: body.reason })}</li>` : ''}</ul>
      <div class="error-text" id="pe-err" style="min-height:20px"></div>
      <div class="modal-actions"><button class="btn btn-secondary" id="pe-back">${t('Volver a editar')}</button><button class="btn btn-primary" id="pe-go">${t('Confirmar y publicar')}</button></div></div>`;
    box.querySelector('#pe-back').addEventListener('click', () => form());
    box.querySelector('#pe-go').addEventListener('click', async (e) => {
      e.target.disabled = true;
      try {
        const d = await post(`/api/markets/${M.id}/edit`, { ...body, requestId: id });
        clearDraft(draftKey); state = { ...init, end: local(base.closesAt), none: !base.closesAt, rules: base.description, why: '' };
        m.close(); toast(t('Guardada como versión {n}.', { n: d.edit.version }) + (d.edit.notified ? ' ' + tp(d.edit.notified, 'Se le avisó a {n} persona.', 'Se les avisó a {n} personas.') : ''), 'ok'); onSaved(d.market);
      } catch (ex) { box.querySelector('#pe-err').textContent = ex.message; e.target.disabled = false; }
    });
  }
  form();
}
