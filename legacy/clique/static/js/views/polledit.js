/* Editing a published bet: the form, the preview of exactly what will change, the public history, and the exit window.
   The rules themselves (who may edit, what counts as a material change, how long people can walk away) live on the server;
   this only asks the server, shows what it says, and never decides anything. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, dateLong, ago, ICON, money, moneyFull, avatar } from '../util.js';
import { modal, confirmBox, toast } from '../ui.js';
import { saveDraft, loadDraft, clearDraft } from '../viewstate.js';

const rid = () => 'edit-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const local = (ms) => { if (!ms) return ''; const d = new Date(ms - new Date(ms).getTimezoneOffset() * 60000); return d.toISOString().slice(0, 16); };
const fromLocal = (v) => (v ? new Date(v).getTime() : null);
const when = (ms) => (ms ? dateLong(ms) : 'No end date');
const KIND = { created: 'Posted', clarification: 'Clarification', material: 'Material change', no_participation: 'Edited before anyone bet' };

/** The "Edited" marker beside a bet's title. */
export const editedTag = (M) => (M.edited ? `<button class="tag edited" id="hist" title="This bet's rules or closing time were changed. See what changed and when.">${ICON.pencil} Edited · v${M.version}</button>` : '');

/** The notice shown to people who bet before a material change, while they can still walk away at cost. */
export function exitBanner(M) {
  const e = M.exit;
  if (!e || !e.open || !e.tokens.length) return '';
  const mine = (M.myPositions || []).filter((p) => p.withdrawable);
  if (!mine.length) return '';
  return `<div class="exit-banner" role="status"><div><b>The rules or closing time of this bet changed after you bet.</b>
    <p>You can withdraw what you bet under the old rules and get back <b>exactly what you paid</b>, whatever the price is now, until ${esc(dateLong(e.until))}. Or do nothing, and your bet stands under the new rules.</p></div>
    <div class="exit-acts">${mine.map((p) => `<button class="btn btn-secondary btn-sm" data-withdraw="${esc(p.token)}">Withdraw ${money(p.invested)} (${esc(p.label)})</button>`).join('')}<button class="btn btn-ghost btn-sm" id="hist">What changed</button></div></div>`;
}

export async function withdrawFlow(M, token, onDone) {
  const p = (M.myPositions || []).find((x) => x.token === token);
  if (!p) return;
  if (!(await confirmBox({ title: 'Withdraw your bet?', text: `You get back exactly ${moneyFull(p.invested)}, the amount you paid for ${p.label}, even if it is worth a different amount now. Your shares are removed from the market.`, confirm: `Withdraw ${money(p.invested)}` }))) return;
  try {
    const d = await post(`/api/markets/${M.id}/withdraw`, { token, requestId: rid() });
    setUser(d.user); toast(`Withdrawn: ${moneyFull(d.refunded)} is back in your weekly account.`, 'ok'); onDone(d.market);
  } catch (ex) { toast(ex.message, 'err'); }
}

export async function openHistory(M) {
  let H;
  try { H = await get(`/api/markets/${M.id}/history`); } catch (ex) { toast(ex.message, 'err'); return; }
  const rows = [...H.edits].reverse().map((e) => `<li class="vh ${esc(e.class)}"><div class="vh-top"><b>Version ${e.v}</b><span class="tag ${e.class === 'material' ? 'bad' : ''}">${esc(KIND[e.class] || e.class)}</span><span class="muted">${esc(dateLong(e.t))} · ${ago(e.t)}</span></div>
      <div class="vh-by">${avatar(e.by.username, 20)} <a href="#/u/${esc(e.by.username)}">${esc(e.by.username)}</a>${e.kind === 'created' ? ' proposed it' : ' edited it'}</div>
      ${e.reason ? `<p class="vh-why"><em>Why:</em> ${esc(e.reason)}</p>` : ''}
      ${e.changes && e.changes.closesAt ? `<div class="vh-ch"><span class="lbl">Closing time</span><span class="from">${esc(when(e.changes.closesAt.from))}</span> ${ICON.arrowR} <span class="to">${esc(when(e.changes.closesAt.to))}</span></div>` : ''}
      ${e.changes && e.changes.description ? `<div class="vh-ch"><span class="lbl">Rules</span><div class="from">${esc(e.changes.description.from) || '<i>(none)</i>'}</div><div class="to">${esc(e.changes.description.to) || '<i>(none)</i>'}</div></div>` : ''}
      ${e.participants ? `<small class="muted">${e.participants} ${e.participants === 1 ? 'person' : 'people'} had bet when this changed.</small>` : ''}
      ${e.exitUntil ? `<small class="muted">Anyone who bet before could withdraw at cost until ${esc(dateLong(e.exitUntil))}.</small>` : ''}</li>`).join('');
  modal(`<span class="lbl">Open to everybody in this bet</span><h2>What changed</h2>
    <p class="lede">Every change to the rules or closing time is kept here: who, when, why, and what it was before. A settled result is never reopened.</p>
    <ol class="vh-list">${rows}</ol><div class="modal-actions"><button class="btn btn-primary" data-close>Close</button></div>`, { wide: true });
}

/** The edit form. `onSaved(market)` runs after a successful save. */
export function openEditPoll(M, onSaved) {
  const involved = (M.traders > 0) || (M.holders && M.holders.length > 0);
  const base = { closesAt: M.closesAt || null, description: M.rules || '' };
  const draftKey = 'edit:' + M.id, saved = loadDraft(draftKey);
  let restored = false;
  const init = { end: local(base.closesAt), none: !base.closesAt, rules: base.description, why: '', kind: 'material' };
  if (saved) { Object.assign(init, saved); restored = true; }
  const m = modal(`<span class="lbl">Edit this bet</span><h2>Change the date or the rules</h2>
    <div id="pe-step"></div>`, { wide: true, guard: () => dirty() });
  const box = m.el.querySelector('#pe-step');
  let state = { ...init };
  const dirty = () => state.end !== local(base.closesAt) || state.none !== !base.closesAt || state.rules !== base.description || state.why !== '';
  const values = () => ({ closesAt: state.none ? null : fromLocal(state.end), description: state.rules, reason: state.why, kind: state.kind });
  const changedDate = () => (state.none ? !!base.closesAt : !base.closesAt || state.end !== local(base.closesAt));      // the box has no seconds, so compare what it shows
  function form(err = '') {
    const onlyRules = !changedDate();
    box.innerHTML = `${restored ? '<div class="notice">Your earlier, unsaved edit was put back.</div>' : ''}
      ${involved ? `<div class="notice">${M.traders} ${M.traders === 1 ? 'person has' : 'people have'} bet on this. Changes are announced to everybody involved, kept in a public history, and may let them withdraw. You will see exactly what happens before anything is saved.</div>` : '<p class="lede" style="margin-top:0">Nobody has bet on this yet, so a change affects nobody. It is still saved as a new version.</p>'}
      <div class="field"><label for="pe-end">Closing date and time</label>
        <div class="row" style="gap:12px;flex-wrap:wrap"><input class="input" type="datetime-local" id="pe-end" value="${esc(state.end)}" ${state.none ? 'disabled' : ''} style="max-width:260px">
          <label class="check"><input type="checkbox" id="pe-none" ${state.none ? 'checked' : ''}> No end date</label></div></div>
      <div class="field"><label for="pe-rules">Rules (what counts as a win, and any fine print)</label><textarea class="input" id="pe-rules" rows="5" maxlength="1000">${esc(state.rules)}</textarea></div>
      ${involved ? `<div class="field"><label>What kind of change is this?</label>
        <div class="seg"><label class="seg-opt"><input type="radio" name="pe-kind" value="clarification" ${state.kind === 'clarification' && onlyRules ? 'checked' : ''} ${onlyRules ? '' : 'disabled'}><span><b>A clarification</b><small>Same meaning, clearer words. Nobody can withdraw. ${onlyRules ? '' : 'Not available when the date changes: a new date can change the answer.'}</small></span></label>
          <label class="seg-opt"><input type="radio" name="pe-kind" value="material" ${state.kind === 'material' || !onlyRules ? 'checked' : ''}><span><b>A material change</b><small>It changes what counts or when it ends. Everyone who bet can withdraw what they paid. Allowed once per bet after people have bet.</small></span></label></div></div>
        <div class="field"><label for="pe-why">Why are you changing it? <span class="muted">(shown to everybody, at least 10 characters)</span></label><textarea class="input" id="pe-why" rows="2" maxlength="200">${esc(state.why)}</textarea></div>` : `<div class="field"><label for="pe-why">Reason <span class="muted">(optional)</span></label><input class="input" id="pe-why" maxlength="200" value="${esc(state.why)}"></div>`}
      <div class="error-text" id="pe-err" style="min-height:20px">${esc(err)}</div>
      <div class="modal-actions"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="pe-prev">See what will change</button></div>`;
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
    box.innerHTML = `<div class="pv"><div class="pv-head"><span class="tag ${P.class === 'material' ? 'bad' : ''}">${esc(KIND[P.class] || P.class)}</span><b>Saved as version ${P.newVersion}</b></div>
      ${ch.closesAt ? `<div class="vh-ch"><span class="lbl">Closing time</span><span class="from">${esc(when(ch.closesAt.from))}</span> ${ICON.arrowR} <span class="to">${esc(when(ch.closesAt.to))}</span></div>` : ''}
      ${ch.description ? `<div class="vh-ch"><span class="lbl">Rules</span><div class="from">${esc(ch.description.from) || '<i>(none)</i>'}</div><div class="to">${esc(ch.description.to) || '<i>(none)</i>'}</div></div>` : ''}
      <ul class="pv-notes"><li>${esc(P.note)}</li>
        ${P.notifyCount ? `<li><b>${P.notifyCount}</b> ${P.notifyCount === 1 ? 'person is' : 'people are'} told in the app: ${esc(P.notify.join(', '))}${P.notifyCount > P.notify.length ? ' and others' : ''}.</li>` : ''}
        ${P.exitUntil ? `<li>Anyone who bet under the old rules can withdraw what they paid until <b>${esc(dateLong(P.exitUntil))}</b>.</li>` : ''}
        <li>Nothing about anybody's bets, balances or shares changes. The history keeps the old values, who changed them, when and why.</li>
        ${body.reason ? `<li>Reason shown to everybody: <i>${esc(body.reason)}</i></li>` : ''}</ul>
      <div class="error-text" id="pe-err" style="min-height:20px"></div>
      <div class="modal-actions"><button class="btn btn-secondary" id="pe-back">Back to editing</button><button class="btn btn-primary" id="pe-go">Confirm and publish</button></div></div>`;
    box.querySelector('#pe-back').addEventListener('click', () => form());
    box.querySelector('#pe-go').addEventListener('click', async (e) => {
      e.target.disabled = true;
      try {
        const d = await post(`/api/markets/${M.id}/edit`, { ...body, requestId: id });
        clearDraft(draftKey); state = { ...init, end: local(base.closesAt), none: !base.closesAt, rules: base.description, why: '' };
        m.close(); toast(`Saved as version ${d.edit.version}. ${d.edit.notified ? `${d.edit.notified} ${d.edit.notified === 1 ? 'person was' : 'people were'} told.` : ''}`, 'ok'); onSaved(d.market);
      } catch (ex) { box.querySelector('#pe-err').textContent = ex.message; e.target.disabled = false; }
    });
  }
  form();
}
