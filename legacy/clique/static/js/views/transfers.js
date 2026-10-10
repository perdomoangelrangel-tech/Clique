/* Transfers: send pretend money from one of your accounts to the SAME kind of account of a friend: weekly to weekly, or accumulated to
   accumulated. You choose which. The page only asks; the server decides everything (friendship, password, daily limit, funds, the
   weekly safeguards). The transfer password is read from the box when you press Send, sent once, and the box is emptied at once:
   it is never kept in the page, in storage, or in the address. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, moneyFull, until, dateLong, parseAmount } from '../util.js';
import { toast, modal, revealPasswords } from '../ui.js';
import { emptyState } from './components.js';

const newId = () => 'rq-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const ACCT = {
  weekly: { name: 'Weekly account', tag: '<span class="acct-tag weekly">Weekly account</span>', short: '<span class="acct-tag weekly">Weekly</span>' },
  accumulated: { name: 'Accumulated account', tag: '<span class="acct-tag accum">Accumulated account</span>', short: '<span class="acct-tag accum">Accumulated</span>' },
};
const KINDS = ['weekly', 'accumulated'];
const kind = (a) => (a === 'weekly' ? 'weekly' : 'accumulated');          // (older history rows say nothing: they were all accumulated)

export default {
  async mount(root) {
    let D = await get('/api/transfers'), dead = false, tab = 'sent', draft = { to: '', amount: '', note: '', account: '' };

    const lockBanner = () => (D.locked ? `<div class="lock-banner" role="alert">Too many wrong transfer passwords. Transfers are locked for about ${Math.max(1, Math.round(D.locked.seconds / 60))} more minute(s).</div>` : '');

    const enabled = () => KINDS.filter((k) => D.accounts[k].enabled);
    const current = () => { const on = enabled(); return on.includes(draft.account) ? draft.account : (on.includes(D.defaultAccount) ? D.defaultAccount : on[0]); };

    const picker = () => {
      const now = current();
      return `<fieldset class="xf-pick" aria-label="Which account do you want to send from?"><legend class="kicker">Which account do you want to use?</legend>
        ${KINDS.map((k) => { const A = D.accounts[k]; return `<label class="xf-opt ${A.enabled ? '' : 'off'}"><input type="radio" name="xf-acct" value="${k}" ${now === k ? 'checked' : ''} ${A.enabled ? '' : 'disabled'}>
          <span class="xf-face ${k}">${ACCT[k].tag}<b class="num" title="${moneyFull(A.balance)}">${money(A.balance)}</b>
            <small>${A.enabled ? `You can send ${money(A.sendable)}${A.owed > 0 ? ` (you owe ${money(A.owed)} on a loan)` : ''}` : 'Switched off right now'}</small></span></label>`; }).join('')}</fieldset>`;
    };

    const allowance = () => {
      const k = current(), L = D.accounts[k].limit, pct = L.daily ? Math.min(100, Math.round((L.sent / L.daily) * 100)) : 100;
      return `<section class="card-box xf-allow" aria-label="Daily limit"><div class="row-top"><div><span class="kicker">Daily sending limit · ${ACCT[k].short}</span><div class="big num">${money(L.remaining)} <span class="muted" style="font-size:15px;font-weight:500">left today</span></div></div>
          <div style="text-align:right"><div class="muted" style="font-size:13px">Resets at midnight (in ${until(L.resetsAt)})</div><div class="num" style="font-size:14px">Sent today ${money(L.sent)} of ${money(L.daily)}</div></div></div>
        <div class="pbar verm" role="progressbar" aria-valuemin="0" aria-valuemax="${L.daily}" aria-valuenow="${L.sent}" aria-label="Daily limit used"><i style="width:${pct}%"></i></div>
        <p class="muted" style="margin:10px 0 0;font-size:13px">Each account has its own limit, and it counts what you have sent to everybody from that account today. Money you receive does not give you more allowance, and a transfer that is refused does not use any.</p></section>`;
    };

    const setupCard = () => `<section class="card-box ln-card" aria-label="Choose a transfer password"><h2>Choose a transfer password</h2>
      <p style="margin:0 0 14px">Every transfer asks for a separate password, even while you are logged in. It cannot be your login password. Pick something you will remember: it can only be reset with your login password and a code sent to your confirmed email.</p>
      <form id="pw-set" autocomplete="off"><div class="field"><label for="pw-login">Your account (login) password</label><input class="input" id="pw-login" type="password" autocomplete="current-password" required></div>
        <div class="field"><label for="pw-new">New transfer password</label><input class="input" id="pw-new" type="password" autocomplete="new-password" minlength="6" required><small>At least 6 characters.</small></div>
        <div class="field"><label for="pw-new2">Repeat it</label><input class="input" id="pw-new2" type="password" autocomplete="new-password" required></div>
        <div class="error-text" id="pw-err" style="min-height:18px"></div><button class="btn btn-primary">Save transfer password</button></form></section>`;

    const sendCard = () => {
      if (!D.friends.length) return `<section class="card-box ln-card"><h2>Send money</h2>${emptyState({ art: 'chat', tone: 'cream', tight: true, kicker: 'No friends yet', title: 'Nobody to send to.', text: 'You can only send money to people you added as friends who added you back. Circle-mates and pending requests do not count.', actions: '<a class="btn btn-primary" href="#/friends">Find friends</a>' })}</section>`;
      const k = current(), A = D.accounts[k];
      return `<section class="card-box ln-card" aria-label="Send money"><h2>Send money</h2>
        <div class="xf-from"><span>From your</span>${ACCT[k].tag}<span>to their</span>${ACCT[k].tag}<span class="muted">· no fee · you can send <b class="num">${money(A.sendable)}</b></span></div>
        <p class="pw-help" style="margin:-6px 0 14px">${esc(A.rule)}</p>
        ${lockBanner()}
        <form id="xf-form" autocomplete="off"><div class="field"><label for="xf-to">Friend</label><select class="select" id="xf-to" required><option value="">Choose a friend</option>${D.friends.map((f) => `<option value="${esc(f.id)}" ${draft.to === f.id ? 'selected' : ''} ${f.eligible ? '' : 'disabled'}>${esc(f.username)}${f.eligible ? '' : ' (cannot receive)'}</option>`).join('')}</select></div>
          <div class="field"><label for="xf-amt">Amount</label><div class="money-in"><span>$</span><input class="input" id="xf-amt" inputmode="decimal" placeholder="0.00" value="${esc(draft.amount)}" required></div><small>${money(D.min)} or more, up to ${money(Math.min(A.limit.remaining, A.sendable))} right now.</small></div>
          <div class="field"><label for="xf-note">Note (optional)</label><input class="input" id="xf-note" maxlength="${D.noteMax}" placeholder="For the pizza" value="${esc(draft.note)}"></div>
          <div class="error-text" id="xf-err" style="min-height:18px"></div><button class="btn btn-primary" ${D.locked ? 'disabled' : ''}>Review transfer</button></form></section>`;
    };

    const passwordCard = () => `<section class="card-box ln-card" aria-label="Transfer password"><h2>Your transfer password</h2><p class="muted" style="margin:0 0 14px">Set ${D.passwordSetAt ? dateLong(D.passwordSetAt) : ''}. It is stored only as a salted hash and never shown anywhere.</p>
      <div class="btn-row"><button class="btn btn-secondary btn-sm" id="pw-change">Change it</button><button class="btn btn-ghost btn-sm" id="pw-forgot">I forgot it</button></div></section>`;

    const historyCard = () => {
      const rows = D.history.filter((h) => (tab === 'sent' ? h.dir === 'out' : h.dir === 'in'));
      return `<div class="section-head" style="margin-top:36px"><div><span class="kicker">Receipts</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">History</h2></div>
        <div class="tabs" id="xf-tabs" style="margin:0">${[['sent', 'Sent'], ['received', 'Received']].map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${l}</button>`).join('')}</div></div>
        ${rows.length ? `<div class="card-box tbl-wrap xf-hist"><table class="tbl"><thead><tr><th>When</th><th>${tab === 'sent' ? 'To' : 'From'}</th><th>Account</th><th class="r">Amount</th><th class="hide-sm">Note</th><th class="hide-sm">Status</th></tr></thead><tbody>
          ${rows.map((h) => `<tr><td>${dateLong(h.t)}</td><td><b>${esc(h.peer.username)}</b></td><td>${ACCT[kind(h.account)].short}</td><td class="r num"><span class="dir ${h.dir}">${h.dir === 'in' ? '+' : '−'}</span> ${money(h.amount)}</td><td class="hide-sm">${esc(h.note || '')}</td><td class="hide-sm">${esc(h.status)}</td></tr>`).join('')}</tbody></table></div>`
          : `<div class="card-box pad"><p class="muted" style="margin:0">${tab === 'sent' ? 'You have not sent any money yet.' : 'Nobody has sent you money yet.'}</p></div>`}`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">Between friends</span><h1 class="page-title">Transfers.</h1>
        <p class="gl-sub">Send pretend money from one of your accounts to the same kind of account of a friend: <b>weekly to weekly</b>, or <b>accumulated to accumulated</b>. You choose which one, and the two kinds are never mixed. Both of you have to have added each other as friends.</p></div></div>
        ${D.enabled && enabled().length ? `${picker()}${allowance()}
        <div class="ln-grid">${D.passwordSet ? sendCard() : setupCard()}${D.passwordSet ? passwordCard() : `<section class="card-box ln-card"><h2>How it stays safe</h2><ul class="rk-list"><li>Only friends who added each other can receive money.</li><li>A separate password for every transfer.</li><li>A daily limit for each account: ${KINDS.filter((k) => D.accounts[k].enabled).map((k) => `${money(D.accounts[k].limit.daily)} ${k}`).join(' and ')}.</li><li>Weekly chips never count as winnings for anybody, and a loan you owe stays with you.</li><li>A clear receipt, and both of you see it in your history.</li></ul></section>`}</div>
        ${historyCard()}` : '<div class="card-box pad"><p class="muted" style="margin:0">Transfers are switched off right now.</p></div>'}</div>`;
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
      if (a.value !== b.value) { err.textContent = 'The two transfer passwords are not the same.'; return; }
      const body = { loginPassword: login.value, newPassword: a.value };
      login.value = a.value = b.value = '';                                    // never kept: the boxes are emptied as soon as they are read
      try { const r = await post('/api/transfers/password', body); D = r.transfers; toast('Transfer password saved.', 'ok'); draw(); }
      catch (ex) { err.textContent = ex.message; }
    }

    async function onReview(e) {
      e.preventDefault();
      const err = root.querySelector('#xf-err'); err.textContent = '';
      const amountV = parseAmount(draft.amount);
      if (!draft.to) { err.textContent = 'Choose a friend.'; return; }
      if (!(amountV > 0)) { err.textContent = 'Enter an amount.'; return; }
      let p;
      try { p = await post('/api/transfers/preview', { to: draft.to, amount: amountV, note: draft.note, account: current() }); } catch (ex) { err.textContent = ex.message; return; }
      confirmWindow(p);
    }

    function confirmWindow(p) {
      const requestId = newId();
      const m = modal(`<span class="lbl">Review and confirm</span><h2>Send ${money(p.amount)} to ${esc(p.to.username)}?</h2>
        <dl class="kv" style="margin:12px 0 14px"><dt>To</dt><dd>${esc(p.to.username)}</dd><dt>From your</dt><dd>${ACCT[kind(p.account)].tag}</dd><dt>Into their</dt><dd>${ACCT[kind(p.account)].tag}</dd><dt>Amount</dt><dd class="num">${money(p.amount)}</dd><dt>Fee</dt><dd class="num">${money(p.fee)}</dd>
          ${p.note ? `<dt>Note</dt><dd>${esc(p.note)}</dd>` : ''}<dt class="total">Your ${kind(p.account)} balance after</dt><dd class="num total">${money(p.senderBalanceAfter)}</dd><dt>Daily allowance left after</dt><dd class="num">${money(p.remainingAfter)}</dd></dl>
        <p class="pw-help" style="margin:-4px 0 14px">${esc(p.rule)}</p>
        <form id="cf-form" autocomplete="off"><div class="field"><label for="cf-pw">Your transfer password</label><input class="input" id="cf-pw" type="password" autocomplete="off" required></div>
          <div class="error-text" id="cf-err" style="min-height:20px"></div>
          <div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary" id="cf-go">Send ${money(p.amount)}</button></div></form>`);
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
      modal(`<div class="rcpt"><span class="stamp-ok">Sent</span><h2>${money(r.amount)} to ${esc(r.to.username)}</h2>
        <dl class="kv"><dt>Status</dt><dd>${esc(r.status)}</dd><dt>Receipt number</dt><dd>${esc(r.id)}</dd><dt>When</dt><dd>${dateLong(r.t)}</dd><dt>From</dt><dd>${esc(r.from.username)} · ${kind(r.account)}</dd><dt>To</dt><dd>${esc(r.to.username)} · ${kind(r.account)}</dd><dt>Amount</dt><dd>${money(r.amount)}</dd><dt>Fee</dt><dd>${money(r.fee)}</dd>
          ${r.note ? `<dt>Note</dt><dd>${esc(r.note)}</dd>` : ''}<dt>Your ${kind(r.account)} balance now</dt><dd>${money(r.senderBalanceAfter)}</dd><dt>${kind(r.account) === 'weekly' ? 'Weekly' : 'Accumulated'} allowance left today</dt><dd>${money(r.remainingToday)}</dd></dl>
        <div class="modal-actions"><button class="btn btn-primary" data-close>Done</button></div></div>`);
    }

    function openChange() {
      const m = modal(`<span class="lbl">Transfer password</span><h2>Change it</h2><form id="ch-form" autocomplete="off">
        <div class="field"><label for="ch-cur">Current transfer password</label><input class="input" id="ch-cur" type="password" autocomplete="off" required></div>
        <div class="field"><label for="ch-login">Your account (login) password</label><input class="input" id="ch-login" type="password" autocomplete="current-password" required></div>
        <div class="field"><label for="ch-new">New transfer password</label><input class="input" id="ch-new" type="password" autocomplete="new-password" minlength="6" required></div>
        <div class="error-text" id="ch-err" style="min-height:20px"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary">Change it</button></div></form>`);
      revealPasswords(m.el);
      m.el.querySelector('#ch-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const f = (id) => m.el.querySelector(id);
        const body = { currentPassword: f('#ch-cur').value, loginPassword: f('#ch-login').value, newPassword: f('#ch-new').value };
        f('#ch-cur').value = f('#ch-login').value = f('#ch-new').value = '';
        try { const r = await post('/api/transfers/password', body); D = r.transfers; m.close(); toast('Transfer password changed.', 'ok'); draw(); } catch (ex) { f('#ch-err').textContent = ex.message; }
      });
    }

    function openForgot() {
      const m = modal(`<span class="lbl">Forgot your transfer password?</span><h2>Reset it</h2><p class="lede">We send a 6-digit code to the email address confirmed on your account. You also need your login password.</p>
        <form id="fg-form" autocomplete="off"><div class="field"><label for="fg-login">Your account (login) password</label><input class="input" id="fg-login" type="password" autocomplete="current-password" required></div>
        <div class="btn-row" style="margin-bottom:14px"><button type="button" class="btn btn-secondary btn-sm" id="fg-send">Email me a code</button></div>
        <div class="field"><label for="fg-code">The code</label><input class="input" id="fg-code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="123456"></div>
        <div class="field"><label for="fg-new">New transfer password</label><input class="input" id="fg-new" type="password" autocomplete="new-password" minlength="6"></div>
        <div class="error-text" id="fg-err" style="min-height:20px"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary">Reset it</button></div></form>`);
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
        try { const r = await post('/api/transfers/password', body); D = r.transfers; m.close(); toast('Transfer password reset.', 'ok'); draw(); } catch (ex) { f('#fg-err').textContent = ex.message; }
      });
    }

    draw();
    const timer = setInterval(() => { if (!dead && !document.querySelector('#modal-root .modal')) draw(); }, 60000);
    return { onEvent(ev) { if (['inbox'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
