/* Transfers: send pretend money from one of your accounts to the SAME kind of account of a friend: weekly to weekly, or accumulated to
   accumulated. You choose which. The page only asks; the server decides everything (friendship, password, daily limit, funds, the
   weekly safeguards). The transfer password is read from the box when you press Send, sent once, and the box is emptied at once:
   it is never kept in the page, in storage, or in the address. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, moneyFull, until, dateLong, parseAmount } from '../util.js';
import { toast, modal, revealPasswords } from '../ui.js';
import { emptyState } from './components.js';
import { t, th, CHIP_SIGN } from '../i18n.js';

const newId = () => 'rq-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const ACCT_NAME = { weekly: 'Cuenta semanal', accumulated: 'Cuenta acumulada' };      // i18n: claves
const ACCT_SHORT = { weekly: 'Semanal', accumulated: 'Acumulada' };      // i18n: claves
const ACCT_LOW = { weekly: 'semanal', accumulated: 'acumulada' };      // i18n: claves
const ACCT_CLS = { weekly: 'weekly', accumulated: 'accum' };
const acctTag = (k) => `<span class="acct-tag ${ACCT_CLS[k]}">${t(ACCT_NAME[k])}</span>`;
const acctShort = (k) => `<span class="acct-tag ${ACCT_CLS[k]}">${t(ACCT_SHORT[k])}</span>`;
const acctLow = (k) => t(ACCT_LOW[k]);
const KINDS = ['weekly', 'accumulated'];
const kind = (a) => (a === 'weekly' ? 'weekly' : 'accumulated');          // (older history rows say nothing: they were all accumulated)

export default {
  async mount(root) {
    let D = await get('/api/transfers'), dead = false, tab = 'sent', draft = { to: '', amount: '', note: '', account: '' };

    const lockBanner = () => (D.locked ? `<div class="lock-banner" role="alert">${t('Demasiadas contraseñas de envío equivocadas. Los envíos están bloqueados unos {n} min más.', { n: Math.max(1, Math.round(D.locked.seconds / 60)) })}</div>` : '');

    const enabled = () => KINDS.filter((k) => D.accounts[k].enabled);
    const current = () => { const on = enabled(); return on.includes(draft.account) ? draft.account : (on.includes(D.defaultAccount) ? D.defaultAccount : on[0]); };

    const picker = () => {
      const now = current();
      return `<fieldset class="xf-pick" aria-label="${esc(t('¿Desde qué cuenta quieres enviar?'))}"><legend class="kicker">${t('¿Qué cuenta quieres usar?')}</legend>
        ${KINDS.map((k) => { const A = D.accounts[k]; return `<label class="xf-opt ${A.enabled ? '' : 'off'}"><input type="radio" name="xf-acct" value="${k}" ${now === k ? 'checked' : ''} ${A.enabled ? '' : 'disabled'}>
          <span class="xf-face ${k}">${acctTag(k)}<b class="num" title="${moneyFull(A.balance)}">${money(A.balance)}</b>
            <small>${A.enabled ? (A.owed > 0 ? t('Puedes enviar {cantidad} (debes {debe} de un préstamo)', { cantidad: money(A.sendable), debe: money(A.owed) }) : t('Puedes enviar {cantidad}', { cantidad: money(A.sendable) })) : t('Apagada por ahora')}</small></span></label>`; }).join('')}</fieldset>`;
    };

    const allowance = () => {
      const k = current(), L = D.accounts[k].limit, pct = L.daily ? Math.min(100, Math.round((L.sent / L.daily) * 100)) : 100;
      return `<section class="card-box xf-allow" aria-label="${esc(t('Límite diario'))}"><div class="row-top"><div><span class="kicker">${t('Límite diario de envío')} · ${acctShort(k)}</span><div class="big num">${money(L.remaining)} <span class="muted" style="font-size:15px;font-weight:500">${t('te quedan hoy')}</span></div></div>
          <div style="text-align:right"><div class="muted" style="font-size:13px">${t('Se reinicia a medianoche (en {tiempo})', { tiempo: until(L.resetsAt) })}</div><div class="num" style="font-size:14px">${t('Enviado hoy: {enviado} de {limite}', { enviado: money(L.sent), limite: money(L.daily) })}</div></div></div>
        <div class="pbar verm" role="progressbar" aria-valuemin="0" aria-valuemax="${L.daily}" aria-valuenow="${L.sent}" aria-label="${esc(t('Límite diario usado'))}"><i style="width:${pct}%"></i></div>
        <p class="muted" style="margin:10px 0 0;font-size:13px">${t('Cada cuenta tiene su propio límite, y cuenta lo que has enviado hoy a todos desde esa cuenta. Lo que recibes no te da más margen, y un envío rechazado no gasta nada.')}</p></section>`;
    };

    const setupCard = () => `<section class="card-box ln-card" aria-label="${esc(t('Elige una contraseña de envío'))}"><h2>${t('Elige una contraseña de envío')}</h2>
      <p style="margin:0 0 14px">${t('Cada envío pide una contraseña aparte, aunque ya hayas entrado. No puede ser tu contraseña para entrar. Elige algo que recuerdes: solo se puede cambiar con tu contraseña para entrar y un código que llega a tu correo confirmado.')}</p>
      <form id="pw-set" autocomplete="off"><div class="field"><label for="pw-login">${t('Tu contraseña para entrar')}</label><input class="input" id="pw-login" type="password" autocomplete="current-password" required></div>
        <div class="field"><label for="pw-new">${t('Contraseña de envío nueva')}</label><input class="input" id="pw-new" type="password" autocomplete="new-password" minlength="6" required><small>${t('Mínimo 6 caracteres.')}</small></div>
        <div class="field"><label for="pw-new2">${t('Repítela')}</label><input class="input" id="pw-new2" type="password" autocomplete="new-password" required></div>
        <div class="error-text" id="pw-err" style="min-height:18px"></div><button class="btn btn-primary">${t('Guardar contraseña de envío')}</button></form></section>`;

    const sendCard = () => {
      if (!D.friends.length) return `<section class="card-box ln-card"><h2>${t('Enviar fichas')}</h2>${emptyState({ art: 'chat', tone: 'cream', tight: true, kicker: t('Todavía sin amigos'), title: esc(t('No hay a quién enviarle.')), text: esc(t('Solo puedes enviar fichas a quienes agregaste como amigos y te agregaron de vuelta. Los de tus círculos y las solicitudes pendientes no cuentan.')), actions: `<a class="btn btn-primary" href="#/friends">${t('Buscar amigos')}</a>` })}</section>`;
      const k = current(), A = D.accounts[k];
      return `<section class="card-box ln-card" aria-label="${esc(t('Enviar fichas'))}"><h2>${t('Enviar fichas')}</h2>
        <div class="xf-from"><span>${t('De tu')}</span>${acctTag(k)}<span>${t('a su')}</span>${acctTag(k)}<span class="muted">${th('· sin comisión · puedes enviar <b class="num">{cantidad}</b>', { cantidad: money(A.sendable) })}</span></div>
        <p class="pw-help" style="margin:-6px 0 14px">${esc(A.rule)}</p>
        ${lockBanner()}
        <form id="xf-form" autocomplete="off"><div class="field"><label for="xf-to">${t('Amigo')}</label><select class="select" id="xf-to" required><option value="">${t('Elige a un amigo')}</option>${D.friends.map((f) => `<option value="${esc(f.id)}" ${draft.to === f.id ? 'selected' : ''} ${f.eligible ? '' : 'disabled'}>${esc(f.username)}${f.eligible ? '' : ' ' + esc(t('(no puede recibir)'))}</option>`).join('')}</select></div>
          <div class="field"><label for="xf-amt">${t('Cantidad')}</label><div class="money-in"><span>${CHIP_SIGN}</span><input class="input" id="xf-amt" inputmode="decimal" placeholder="0.00" value="${esc(draft.amount)}" required></div><small>${t('{min} o más, hasta {max} ahora mismo.', { min: money(D.min), max: money(Math.min(A.limit.remaining, A.sendable)) })}</small></div>
          <div class="field"><label for="xf-note">${t('Nota (opcional)')}</label><input class="input" id="xf-note" maxlength="${D.noteMax}" placeholder="${esc(t('Para la pizza'))}" value="${esc(draft.note)}"></div>
          <div class="error-text" id="xf-err" style="min-height:18px"></div><button class="btn btn-primary" ${D.locked ? 'disabled' : ''}>${t('Revisar el envío')}</button></form></section>`;
    };

    const passwordCard = () => `<section class="card-box ln-card" aria-label="${esc(t('Contraseña de envío'))}"><h2>${t('Tu contraseña de envío')}</h2><p class="muted" style="margin:0 0 14px">${D.passwordSetAt ? t('Creada el {fecha}.', { fecha: dateLong(D.passwordSetAt) }) + ' ' : ''}${t('Solo se guarda como un hash con sal y nunca se muestra en ningún lado.')}</p>
      <div class="btn-row"><button class="btn btn-secondary btn-sm" id="pw-change">${t('Cambiarla')}</button><button class="btn btn-ghost btn-sm" id="pw-forgot">${t('La olvidé')}</button></div></section>`;

    const historyCard = () => {
      const rows = D.history.filter((h) => (tab === 'sent' ? h.dir === 'out' : h.dir === 'in'));
      return `<div class="section-head" style="margin-top:36px"><div><span class="kicker">${t('Comprobantes')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Historial')}</h2></div>
        <div class="tabs" id="xf-tabs" style="margin:0">${[['sent', t('Enviados')], ['received', t('Recibidos')]].map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${esc(l)}</button>`).join('')}</div></div>
        ${rows.length ? `<div class="card-box tbl-wrap xf-hist"><table class="tbl"><thead><tr><th>${t('Cuándo')}</th><th>${tab === 'sent' ? t('Para') : t('De')}</th><th>${t('Cuenta')}</th><th class="r">${t('Cantidad')}</th><th class="hide-sm">${t('Nota')}</th><th class="hide-sm">${t('Estado')}</th></tr></thead><tbody>
          ${rows.map((h) => `<tr><td>${dateLong(h.t)}</td><td><b>${esc(h.peer.username)}</b></td><td>${acctShort(kind(h.account))}</td><td class="r num"><span class="dir ${h.dir}">${h.dir === 'in' ? '+' : '−'}</span> ${money(h.amount)}</td><td class="hide-sm">${esc(h.note || '')}</td><td class="hide-sm">${esc(h.status)}</td></tr>`).join('')}</tbody></table></div>`
          : `<div class="card-box pad"><p class="muted" style="margin:0">${tab === 'sent' ? t('Todavía no has enviado fichas.') : t('Nadie te ha enviado fichas todavía.')}</p></div>`}`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">${t('Entre amigos')}</span><h1 class="page-title">${t('Envíos.')}</h1>
        <p class="gl-sub">${t('Envía fichas de juego desde una de tus cuentas a la misma cuenta de un amigo: <b>semanal a semanal</b>, o <b>acumulada a acumulada</b>. Tú eliges cuál, y las dos nunca se mezclan. Los dos tienen que haberse agregado como amigos.')}</p></div></div>
        ${D.enabled && enabled().length ? `${picker()}${allowance()}
        <div class="ln-grid">${D.passwordSet ? sendCard() : setupCard()}${D.passwordSet ? passwordCard() : `<section class="card-box ln-card"><h2>${t('Cómo se cuida')}</h2><ul class="rk-list"><li>${t('Solo pueden recibir fichas los amigos que se agregaron mutuamente.')}</li><li>${t('Una contraseña aparte para cada envío.')}</li><li>${t('Un límite diario por cuenta: {limites}.', { limites: KINDS.filter((k) => D.accounts[k].enabled).map((k) => `${money(D.accounts[k].limit.daily)} ${acctLow(k)}`).join(` ${t('y')} `) })}</li><li>${t('Las fichas semanales nunca cuentan como premio para nadie, y un préstamo que debes se queda contigo.')}</li><li>${t('Un comprobante claro, y los dos lo ven en su historial.')}</li></ul></section>`}</div>
        ${historyCard()}` : `<div class="card-box pad"><p class="muted" style="margin:0">${t('Los envíos están apagados por ahora.')}</p></div>`}</div>`;
      bind();
    };
    const reload = async () => { try { D = await get('/api/transfers'); if (!dead) draw(); } catch { /* keep what is on screen */ } };

    function bind() {
      revealPasswords(root);
      root.querySelector('#pw-set')?.addEventListener('submit', onSetPassword);
      root.querySelector('#xf-form')?.addEventListener('submit', onReview);
      root.querySelectorAll('input[name="xf-acct"]').forEach((r) => r.addEventListener('change', () => { draft.account = r.value; draw(); root.querySelector('input[name="xf-acct"]:checked')?.focus(); }));
      for (const id of ['to', 'amt', 'note']) root.querySelector('#xf-' + id)?.addEventListener('input', (e) => { draft[{ to: 'to', amt: 'amount', note: 'note' }[id]] = e.target.value; });
      root.querySelector('#xf-tabs')?.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) { tab = b.dataset.t; draw(); } });
      root.querySelector('#pw-change')?.addEventListener('click', openChange);
      root.querySelector('#pw-forgot')?.addEventListener('click', openForgot);
    }

    async function onSetPassword(e) {
      e.preventDefault();
      const err = root.querySelector('#pw-err'), login = root.querySelector('#pw-login'), a = root.querySelector('#pw-new'), b = root.querySelector('#pw-new2');
      err.textContent = '';
      if (a.value !== b.value) { err.textContent = t('Las dos contraseñas de envío no son iguales.'); return; }
      const body = { loginPassword: login.value, newPassword: a.value };
      login.value = a.value = b.value = '';                                    // never kept: the boxes are emptied as soon as they are read
      try { const r = await post('/api/transfers/password', body); D = r.transfers; toast(t('Contraseña de envío guardada.'), 'ok'); draw(); }
      catch (ex) { err.textContent = ex.message; }
    }

    async function onReview(e) {
      e.preventDefault();
      const err = root.querySelector('#xf-err'); err.textContent = '';
      const amountV = parseAmount(draft.amount);
      if (!draft.to) { err.textContent = t('Elige a un amigo.'); return; }
      if (!(amountV > 0)) { err.textContent = t('Escribe una cantidad.'); return; }
      let p;
      try { p = await post('/api/transfers/preview', { to: draft.to, amount: amountV, note: draft.note, account: current() }); } catch (ex) { err.textContent = ex.message; return; }
      confirmWindow(p);
    }

    function confirmWindow(p) {
      const requestId = newId();
      const m = modal(`<span class="lbl">${t('Revisa y confirma')}</span><h2>${th('¿Enviar {cantidad} a {nombre}?', { cantidad: money(p.amount), nombre: p.to.username })}</h2>
        <dl class="kv" style="margin:12px 0 14px"><dt>${t('Para')}</dt><dd>${esc(p.to.username)}</dd><dt>${t('De tu')}</dt><dd>${acctTag(kind(p.account))}</dd><dt>${t('A su')}</dt><dd>${acctTag(kind(p.account))}</dd><dt>${t('Cantidad')}</dt><dd class="num">${money(p.amount)}</dd><dt>${t('Comisión')}</dt><dd class="num">${money(p.fee)}</dd>
          ${p.note ? `<dt>${t('Nota')}</dt><dd>${esc(p.note)}</dd>` : ''}<dt class="total">${t('Saldo de tu cuenta {cuenta} después', { cuenta: acctLow(kind(p.account)) })}</dt><dd class="num total">${money(p.senderBalanceAfter)}</dd><dt>${t('Límite diario que te queda después')}</dt><dd class="num">${money(p.remainingAfter)}</dd></dl>
        <p class="pw-help" style="margin:-4px 0 14px">${esc(p.rule)}</p>
        <form id="cf-form" autocomplete="off"><div class="field"><label for="cf-pw">${t('Tu contraseña de envío')}</label><input class="input" id="cf-pw" type="password" autocomplete="off" required></div>
          <div class="error-text" id="cf-err" style="min-height:20px"></div>
          <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary" id="cf-go">${t('Enviar {cantidad}', { cantidad: money(p.amount) })}</button></div></form>`);
      revealPasswords(m.el);
      m.el.querySelector('#cf-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const box = m.el.querySelector('#cf-pw'), go = m.el.querySelector('#cf-go'), err = m.el.querySelector('#cf-err');
        const password = box.value; box.value = ''; go.disabled = true; err.textContent = '';
        try {
          const r = await post('/api/transfers', { to: draft.to, amount: p.amount, note: p.note, account: p.account, password, confirm: true, requestId });
          setUser(r.user); m.close(); draft = { to: '', amount: '', note: '', account: p.account };
          receipt(r.receipt); await reload();
        } catch (ex) { err.textContent = ex.message; go.disabled = false; box.focus(); if (ex.status === 429 || ex.status === 409) await reload(); }
      });
    }

    function receipt(r) {
      modal(`<div class="rcpt"><span class="stamp-ok">${t('Enviado')}</span><h2>${th('{cantidad} para {nombre}', { cantidad: money(r.amount), nombre: r.to.username })}</h2>
        <dl class="kv"><dt>${t('Estado')}</dt><dd>${esc(r.status)}</dd><dt>${t('Número de comprobante')}</dt><dd>${esc(r.id)}</dd><dt>${t('Cuándo')}</dt><dd>${dateLong(r.t)}</dd><dt>${t('De')}</dt><dd>${esc(r.from.username)} · ${acctLow(kind(r.account))}</dd><dt>${t('Para')}</dt><dd>${esc(r.to.username)} · ${acctLow(kind(r.account))}</dd><dt>${t('Cantidad')}</dt><dd>${money(r.amount)}</dd><dt>${t('Comisión')}</dt><dd>${money(r.fee)}</dd>
          ${r.note ? `<dt>${t('Nota')}</dt><dd>${esc(r.note)}</dd>` : ''}<dt>${t('Saldo de tu cuenta {cuenta} ahora', { cuenta: acctLow(kind(r.account)) })}</dt><dd>${money(r.senderBalanceAfter)}</dd><dt>${t('Límite diario {cuenta} que te queda hoy', { cuenta: acctLow(kind(r.account)) })}</dt><dd>${money(r.remainingToday)}</dd></dl>
        <div class="modal-actions"><button class="btn btn-primary" data-close>${t('Listo')}</button></div></div>`);
    }

    function openChange() {
      const m = modal(`<span class="lbl">${t('Contraseña de envío')}</span><h2>${t('Cambiarla')}</h2><form id="ch-form" autocomplete="off">
        <div class="field"><label for="ch-cur">${t('Contraseña de envío actual')}</label><input class="input" id="ch-cur" type="password" autocomplete="off" required></div>
        <div class="field"><label for="ch-login">${t('Tu contraseña para entrar')}</label><input class="input" id="ch-login" type="password" autocomplete="current-password" required></div>
        <div class="field"><label for="ch-new">${t('Contraseña de envío nueva')}</label><input class="input" id="ch-new" type="password" autocomplete="new-password" minlength="6" required></div>
        <div class="error-text" id="ch-err" style="min-height:20px"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary">${t('Cambiarla')}</button></div></form>`);
      revealPasswords(m.el);
      m.el.querySelector('#ch-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const f = (id) => m.el.querySelector(id);
        const body = { currentPassword: f('#ch-cur').value, loginPassword: f('#ch-login').value, newPassword: f('#ch-new').value };
        f('#ch-cur').value = f('#ch-login').value = f('#ch-new').value = '';
        try { const r = await post('/api/transfers/password', body); D = r.transfers; m.close(); toast(t('Contraseña de envío cambiada.'), 'ok'); draw(); } catch (ex) { f('#ch-err').textContent = ex.message; }
      });
    }

    function openForgot() {
      const m = modal(`<span class="lbl">${t('¿Olvidaste tu contraseña de envío?')}</span><h2>${t('Crear una nueva')}</h2><p class="lede">${t('Te mandamos un código de 6 dígitos al correo confirmado de tu cuenta. También necesitas tu contraseña para entrar.')}</p>
        <form id="fg-form" autocomplete="off"><div class="field"><label for="fg-login">${t('Tu contraseña para entrar')}</label><input class="input" id="fg-login" type="password" autocomplete="current-password" required></div>
        <div class="btn-row" style="margin-bottom:14px"><button type="button" class="btn btn-secondary btn-sm" id="fg-send">${t('Mándame un código')}</button></div>
        <div class="field"><label for="fg-code">${t('El código')}</label><input class="input" id="fg-code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="123456"></div>
        <div class="field"><label for="fg-new">${t('Contraseña de envío nueva')}</label><input class="input" id="fg-new" type="password" autocomplete="new-password" minlength="6"></div>
        <div class="error-text" id="fg-err" style="min-height:20px"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>${t('Mejor no')}</button><button class="btn btn-primary">${t('Crear una nueva')}</button></div></form>`);
      revealPasswords(m.el);
      const f = (id) => m.el.querySelector(id);
      f('#fg-send').addEventListener('click', async () => {
        f('#fg-err').textContent = '';
        try { const r = await post('/api/transfers/password/code', { loginPassword: f('#fg-login').value }); toast(r.message, 'ok', { ms: 5000 }); f('#fg-code').focus(); } catch (ex) { f('#fg-err').textContent = ex.message; }
      });
      f('#fg-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const body = { loginPassword: f('#fg-login').value, code: f('#fg-code').value.trim(), newPassword: f('#fg-new').value };
        f('#fg-login').value = f('#fg-new').value = '';
        try { const r = await post('/api/transfers/password', body); D = r.transfers; m.close(); toast(t('Ya tienes una contraseña de envío nueva.'), 'ok'); draw(); } catch (ex) { f('#fg-err').textContent = ex.message; }
      });
    }

    draw();
    const timer = setInterval(() => { if (!dead && !document.querySelector('#modal-root .modal')) draw(); }, 60000);
    return { onEvent(ev) { if (['inbox'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
