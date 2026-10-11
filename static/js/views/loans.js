/* Loans: pretend money lent into the WEEKLY account and repaid from it. The page shows what the server says (/api/loans) and always
   shows the exact terms (/api/loans/quote) in a confirmation window before anything is borrowed. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, moneyFull, until, dateLong, parseAmount, ago } from '../util.js';
import { toast, modal } from '../ui.js';
import { t, th, CHIP_SIGN } from '../i18n.js';

const newId = () => 'rq-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const PAY_KIND = { repay: 'Lo pagaste tú', collect: 'Se cobró al cierre semanal', allocation: 'Se tomó de las fichas de la semana nueva' };      // i18n: claves

export default {
  async mount(root) {
    let D = await get('/api/loans'), dead = false, amount = '';

    const status = () => {
      if (D.active) return D.active.overdue ? `<div class="ln-over">${t('Este préstamo está vencido. Págalo en cuanto puedas: no puedes pedir otro hasta que esté pagado, y parte de las fichas de cada semana nueva se van primero a él.')}</div>` : '';
      return '';
    };

    const borrowCard = () => {
      if (!D.enabled) return `<section class="card-box ln-card"><h2>${t('Pedir prestado')}</h2><p class="muted">${t('Los préstamos están apagados.')}</p></section>`;
      return `<section class="card-box ln-card" aria-label="${esc(t('Pedir prestado'))}"><span class="acct-tag weekly">${t('Llega a tu cuenta semanal')}</span><h2 style="margin-top:12px">${t('Pedir prestado')}</h2>
        ${D.eligible ? `<p style="margin:0 0 14px">${th('Puedes pedir hasta <b class="num">{cantidad}</b> ahora mismo. Es <b>{costo}</b> y tienes que pagarlo antes de que cierre la semana ({fecha}).', { cantidad: money(D.available), costo: D.fee ? t('con una comisión fija de {cantidad}', { cantidad: money(D.fee) }) : t('sin intereses'), fecha: dateLong(D.dueAt) })}</p>
          <div class="field"><label for="ln-amt">${t('¿Cuánto?')}</label><div class="money-in"><span>${CHIP_SIGN}</span><input class="input" id="ln-amt" inputmode="decimal" autocomplete="off" placeholder="0.00" value="${esc(amount)}"></div>
            <div class="ln-chips" id="ln-chips">${[25, 50, 100, 250].filter((v) => v >= D.min && v <= D.available).map((v) => `<button type="button" data-v="${v}">${money(v, { noCents: true })}</button>`).join('')}<button type="button" data-v="${D.available}">${t('Máx. {cantidad}', { cantidad: money(D.available) })}</button></div>
            <small>${t('Entre {min} y {max}. Vas a ver todo antes de confirmar.', { min: money(D.min), max: money(D.available) })}</small></div>
          <div class="error-text" id="ln-err" style="min-height:18px"></div><button class="btn btn-primary" id="ln-go">${t('Revisar el préstamo')}</button>`
        : `<p style="margin:0 0 12px">${t('Ahorita no puedes pedir prestado, y esto es por qué:')}</p><ul class="why">${D.reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`}
        <div class="note-box" style="margin-top:16px">${t('<b>Cómo funciona.</b> Un préstamo rellena tu cuenta semanal, nunca por encima de las fichas de la semana ({semanal}), y como mucho el {pct}% de ellas ({max}). Un préstamo a la vez, hasta {porSemana} por semana, y ninguno en las últimas {horas} horas de la semana. No es una ganancia: nunca cuenta como premio, avance de retos, XP ni rendimiento del ranking, y pagarlo no es una pérdida.', { semanal: money(D.allocation), pct: D.rules.maxPct, max: money(D.maxLoan), porSemana: D.rules.maxPerWeek, horas: D.rules.cutoffHours })}</div></section>`;
    };

    const activeCard = () => {
      const L = D.active;
      return `<section class="card-box ln-card" aria-label="${esc(t('Tu préstamo'))}"><span class="acct-tag weekly">${t('Se paga con tu cuenta semanal')}</span><h2 style="margin-top:12px">${t('Debes {cantidad}', { cantidad: money(L.owed) })}</h2>${status()}
        <dl class="kv"><dt>${t('Te prestaron')}</dt><dd class="num">${money(L.principal)}</dd>${L.fee ? `<dt>${t('Comisión fija')}</dt><dd class="num">${money(L.fee)}</dd>` : ''}<dt>${t('Pagado hasta ahora')}</dt><dd class="num">${money(L.repaid)}</dd>
          <dt>${t('Todavía debes')}</dt><dd class="num">${money(L.owed)}</dd><dt>${t('Págalo antes del')}</dt><dd>${dateLong(L.dueAt)} <span class="muted">(${until(L.dueAt)})</span></dd></dl>
        <div class="pbar" style="margin:14px 0" role="progressbar" aria-valuemin="0" aria-valuemax="${L.total}" aria-valuenow="${L.repaid}" aria-label="${esc(t('Pagado'))}"><i style="width:${Math.min(100, Math.round((L.repaid / L.total) * 100))}%"></i></div>
        <div class="field"><label for="rp-amt">${t('Pagar')}</label><div class="money-in"><span>${CHIP_SIGN}</span><input class="input" id="rp-amt" inputmode="decimal" autocomplete="off" placeholder="0.00"></div>
          <small>${t('Tienes {cantidad} en tu cuenta semanal. Los préstamos solo se pagan con la cuenta semanal.', { cantidad: money(D.weekly) })}</small></div>
        <div class="error-text" id="rp-err" style="min-height:18px"></div>
        <div class="btn-row"><button class="btn btn-primary" id="rp-part">${t('Pagar esta cantidad')}</button><button class="btn btn-secondary" id="rp-all">${t('Pagar todo lo que pueda ({cantidad})', { cantidad: money(Math.min(D.weekly, L.owed)) })}</button></div>
        ${L.payments.length ? `<ul class="pay-list">${L.payments.map((p) => `<li><span>${esc(PAY_KIND[p.kind] ? t(PAY_KIND[p.kind]) : t('Abono'))} · ${ago(p.t)}</span><b class="num">${money(p.amount)}</b></li>`).join('')}</ul>` : ''}
        <div class="note-box" style="margin-top:16px">${t('Si todavía debes algo cuando cierra la semana, primero se cobran tus fichas semanales. Lo que falte sigue debiéndose (una semana nueva no lo perdona), y el {pct}% de las fichas de la siguiente semana se va a él antes de que puedas usarlas. Nunca se toma nada de tu cuenta acumulada.', { pct: D.rules.allocationRepayPct })}</div></section>`;
    };

    const history = () => (D.history.length ? `<div class="section-head" style="margin-top:36px"><div><span class="kicker">${t('Pagados')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Historial de préstamos')}</h2></div></div>
      <div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>${t('Te prestaron')}</th><th class="r">${t('Cantidad')}</th><th class="r hide-sm">${t('Comisión')}</th><th class="r">${t('Pagado')}</th><th class="r hide-sm">${t('Pagos')}</th></tr></thead><tbody>
      ${D.history.map((h) => `<tr><td>${dateLong(h.createdAt)}</td><td class="r num">${money(h.principal)}</td><td class="r num hide-sm">${money(h.fee)}</td><td class="r num">${h.closedAt ? dateLong(h.closedAt) : ''}</td><td class="r num hide-sm">${h.payments.length}</td></tr>`).join('')}</tbody></table></div>` : '');

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">${t('Fichas de mentira, consecuencias de verdad')}</span><h1 class="page-title">${t('Préstamos.')}</h1>
        <p class="gl-sub">${th('Pide fichas para esta semana cuando una mala racha te deja corto. Un préstamo llega a tu <span class="acct-tag weekly">{cuenta}</span> y se paga desde ahí.', { cuenta: t('Cuenta semanal') })}</p></div></div>
        <div class="gl-tiles"><div class="stat"><small>${t('Cuenta semanal')}</small><b class="num" title="${moneyFull(D.weekly)}">${money(D.weekly)}</b></div>
          <div class="stat"><small>${t('Debes')}</small><b class="num ${D.active ? 'down' : ''}">${money(D.active ? D.active.owed : 0)}</b></div>
          <div class="stat"><small>${t('Puedes pedir')}</small><b class="num">${money(D.eligible ? D.available : 0)}</b></div>
          <div class="stat"><small>${D.active ? t('Págalo en') : t('Esta semana cierra en')}</small><b class="num">${until(D.dueAt)}</b></div></div>
        <div class="ln-grid">${D.active ? activeCard() : borrowCard()}
          <div>${D.active ? borrowCard() : `<section class="card-box ln-card"><h2>${t('Condiciones')}</h2><dl class="kv"><dt>${t('Interés')}</dt><dd>${D.fee ? t('comisión fija de {cantidad}', { cantidad: money(D.fee) }) : t('Ninguno')}</dd><dt>${t('Préstamo más grande')}</dt><dd class="num">${money(D.maxLoan)}</dd><dt>${t('Préstamo más chico')}</dt><dd class="num">${money(D.min)}</dd>
            <dt>${t('Préstamos por semana')}</dt><dd class="num">${D.rules.maxPerWeek}</dd><dt>${t('Cerrado en las últimas')}</dt><dd class="num">${t('{n} horas de la semana', { n: D.rules.cutoffHours })}</dd><dt>${t('Si no pagas al cierre')}</dt><dd>${t('el {pct}% de las fichas de la siguiente semana', { pct: D.rules.allocationRepayPct })}</dd></dl></section>`}</div></div>
        ${history()}</div>`;
      bind();
    };

    const reload = async () => { try { D = await get('/api/loans'); if (!dead) draw(); } catch { /* keep what is on screen */ } };

    function bind() {
      const amt = root.querySelector('#ln-amt');
      if (amt) {
        amt.addEventListener('input', () => { amount = amt.value; });
        root.querySelector('#ln-chips').addEventListener('click', (e) => { const b = e.target.closest('[data-v]'); if (b) { amount = String(b.dataset.v); amt.value = amount; amt.focus(); } });
        root.querySelector('#ln-go').addEventListener('click', review);
        amt.addEventListener('keydown', (e) => { if (e.key === 'Enter') review(); });
      }
      root.querySelector('#rp-part')?.addEventListener('click', () => repay(parseAmount(root.querySelector('#rp-amt').value)));
      root.querySelector('#rp-all')?.addEventListener('click', () => repay('all'));
    }

    async function review() {
      const err = root.querySelector('#ln-err'); err.textContent = '';
      const v = parseAmount(amount);
      if (!(v > 0)) { err.textContent = t('Escribe cuánto quieres pedir.'); return; }
      let q;
      try { q = await post('/api/loans/quote', { amount: v }); } catch (ex) { err.textContent = ex.message; return; }
      const requestId = newId();
      const m = modal(`<span class="lbl">${t('Revisa tu préstamo')}</span><h2>${t('¿Pedir {cantidad}?', { cantidad: money(q.amount) })}</h2>
        <dl class="kv" style="margin:12px 0 14px"><dt>${t('Recibes')}</dt><dd class="num">${money(q.amount)}</dd><dt>${t('En')}</dt><dd><span class="acct-tag weekly">${t('Cuenta semanal')}</span></dd><dt>${t('Interés o comisión')}</dt><dd>${q.fee ? money(q.fee) : t('Ninguno')}</dd>
          <dt class="total">${t('Debes')}</dt><dd class="num total">${money(q.total)}</dd><dt>${t('Págalo antes del')}</dt><dd>${dateLong(q.dueAt)}</dd><dt>${t('Tu cuenta semanal después')}</dt><dd class="num">${money(q.weeklyAfter)}</dd></dl>
        <div class="note-box"><b>${t('Qué pasa con tus fichas de las próximas semanas.')}</b> ${esc(q.effect)}</div>
        <div class="error-text" id="cf-err" style="min-height:20px;margin-top:8px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary" id="cf-go">${t('Sí, pedir {cantidad}', { cantidad: money(q.amount) })}</button></div>`);
      const go = m.el.querySelector('#cf-go');
      go.addEventListener('click', async () => {
        go.disabled = true;
        try {
          const r = await post('/api/loans/borrow', { amount: q.amount, confirm: true, requestId });
          setUser(r.user); m.close(); amount = '';
          toast(t('{cantidad} ya están en tu cuenta semanal. Debes {debe}.', { cantidad: money(r.received), debe: money(r.owed) }), 'ok', { ms: 5000 });
          await reload();
        } catch (ex) { m.el.querySelector('#cf-err').textContent = ex.message; go.disabled = false; }
      });
    }

    async function repay(v) {
      const err = root.querySelector('#rp-err'); err.textContent = '';
      if (v !== 'all' && !(v > 0)) { err.textContent = t('Escribe cuánto vas a pagar.'); return; }
      try {
        const r = await post('/api/loans/repay', { amount: v, requestId: newId() });
        setUser(r.user);
        toast(r.closed ? t('Liquidado. Pagaste {cantidad} y ya no debes nada.', { cantidad: money(r.paid) }) : t('Pagaste {cantidad}. Todavía debes {debe}.', { cantidad: money(r.paid), debe: money(r.owed) }), 'ok', { ms: 5000 });
        await reload();
      } catch (ex) { err.textContent = ex.message; }
    }

    draw();
    const timer = setInterval(() => { if (!dead && !document.querySelector('#modal-root .modal')) draw(); }, 60000);
    return { onEvent(ev) { if (['inbox', 'week'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
