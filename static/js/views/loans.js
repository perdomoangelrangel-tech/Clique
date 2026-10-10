/* Loans: pretend money lent into the WEEKLY account and repaid from it. The page shows what the server says (/api/loans) and always
   shows the exact terms (/api/loans/quote) in a confirmation window before anything is borrowed. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, moneyFull, until, dateLong, parseAmount, ago } from '../util.js';
import { toast, modal } from '../ui.js';

const newId = () => 'rq-' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
const PAY_KIND = { repay: 'You repaid', collect: 'Collected at the weekly close', allocation: 'Taken from the new weekly allocation' };

export default {
  async mount(root) {
    let D = await get('/api/loans'), dead = false, amount = '';

    const status = () => {
      if (D.active) return D.active.overdue ? '<div class="ln-over">This loan is overdue. Repay it as soon as you can: you cannot borrow again until it is paid, and part of each new weekly allocation goes to it first.</div>' : '';
      return '';
    };

    const borrowCard = () => {
      if (!D.enabled) return `<section class="card-box ln-card"><h2>Borrow</h2><p class="muted">Loans are switched off.</p></section>`;
      return `<section class="card-box ln-card" aria-label="Borrow"><span class="acct-tag weekly">Lands in your weekly account</span><h2 style="margin-top:12px">Borrow</h2>
        ${D.eligible ? `<p style="margin:0 0 14px">You can borrow up to <b class="num">${money(D.available)}</b> right now. It is <b>${D.fee ? `a fixed fee of ${money(D.fee)}` : 'interest-free'}</b> and must be repaid before the week closes (${dateLong(D.dueAt)}).</p>
          <div class="field"><label for="ln-amt">How much</label><div class="money-in"><span>$</span><input class="input" id="ln-amt" inputmode="decimal" autocomplete="off" placeholder="0.00" value="${esc(amount)}"></div>
            <div class="ln-chips" id="ln-chips">${[25, 50, 100, 250].filter((v) => v >= D.min && v <= D.available).map((v) => `<button type="button" data-v="${v}">${money(v, { noCents: true })}</button>`).join('')}<button type="button" data-v="${D.available}">Max ${money(D.available)}</button></div>
            <small>Between ${money(D.min)} and ${money(D.available)}. You will see everything before you confirm.</small></div>
          <div class="error-text" id="ln-err" style="min-height:18px"></div><button class="btn btn-primary" id="ln-go">Review the loan</button>`
        : `<p style="margin:0 0 12px">You cannot borrow right now, and here is why:</p><ul class="why">${D.reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`}
        <div class="note-box" style="margin-top:16px"><b>How it works.</b> A loan tops your weekly account back up, never past the weekly allocation (${money(D.allocation)}), and at most ${D.rules.maxPct}% of it (${money(D.maxLoan)}). One loan at a time, up to ${D.rules.maxPerWeek} a week, and none in the last ${D.rules.cutoffHours} hours of a week. It is not income: it never counts as winnings, challenge progress, XP or leaderboard performance, and repaying it is not a loss.</div></section>`;
    };

    const activeCard = () => {
      const L = D.active;
      return `<section class="card-box ln-card" aria-label="Your loan"><span class="acct-tag weekly">Repaid from your weekly account</span><h2 style="margin-top:12px">You owe ${money(L.owed)}</h2>${status()}
        <dl class="kv"><dt>Borrowed</dt><dd class="num">${money(L.principal)}</dd>${L.fee ? `<dt>Fixed fee</dt><dd class="num">${money(L.fee)}</dd>` : ''}<dt>Repaid so far</dt><dd class="num">${money(L.repaid)}</dd>
          <dt>Still owed</dt><dd class="num">${money(L.owed)}</dd><dt>Repay before</dt><dd>${dateLong(L.dueAt)} <span class="muted">(${until(L.dueAt)})</span></dd></dl>
        <div class="pbar" style="margin:14px 0" role="progressbar" aria-valuemin="0" aria-valuemax="${L.total}" aria-valuenow="${L.repaid}" aria-label="Repaid"><i style="width:${Math.min(100, Math.round((L.repaid / L.total) * 100))}%"></i></div>
        <div class="field"><label for="rp-amt">Repay</label><div class="money-in"><span>$</span><input class="input" id="rp-amt" inputmode="decimal" autocomplete="off" placeholder="0.00"></div>
          <small>You have ${money(D.weekly)} in your weekly account. Loans are only ever repaid from the weekly account.</small></div>
        <div class="error-text" id="rp-err" style="min-height:18px"></div>
        <div class="btn-row"><button class="btn btn-primary" id="rp-part">Repay this amount</button><button class="btn btn-secondary" id="rp-all">Repay all I can (${money(Math.min(D.weekly, L.owed))})</button></div>
        ${L.payments.length ? `<ul class="pay-list">${L.payments.map((p) => `<li><span>${PAY_KIND[p.kind] || 'Payment'} · ${ago(p.t)}</span><b class="num">${money(p.amount)}</b></li>`).join('')}</ul>` : ''}
        <div class="note-box" style="margin-top:16px">If anything is still owed when the week closes, your weekly funds are collected first. What is left stays owed (it cannot be forgiven by a new week), and ${D.rules.allocationRepayPct}% of the next weekly allocation goes to it before you can spend it. Nothing is taken from your accumulated account.</div></section>`;
    };

    const history = () => (D.history.length ? `<div class="section-head" style="margin-top:36px"><div><span class="kicker">Paid off</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">Loan history</h2></div></div>
      <div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>Borrowed</th><th class="r">Amount</th><th class="r hide-sm">Fee</th><th class="r">Repaid</th><th class="r hide-sm">Payments</th></tr></thead><tbody>
      ${D.history.map((h) => `<tr><td>${dateLong(h.createdAt)}</td><td class="r num">${money(h.principal)}</td><td class="r num hide-sm">${money(h.fee)}</td><td class="r num">${h.closedAt ? dateLong(h.closedAt) : ''}</td><td class="r num hide-sm">${h.payments.length}</td></tr>`).join('')}</tbody></table></div>` : '');

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">Pretend money, real consequences</span><h1 class="page-title">Loans.</h1>
        <p class="gl-sub">Borrow chips for this week when a bad run leaves you short. A loan goes into your <span class="acct-tag weekly">Weekly account</span> and is repaid from it.</p></div></div>
        <div class="gl-tiles"><div class="stat"><small>Weekly account</small><b class="num" title="${moneyFull(D.weekly)}">${money(D.weekly)}</b></div>
          <div class="stat"><small>You owe</small><b class="num ${D.active ? 'down' : ''}">${money(D.active ? D.active.owed : 0)}</b></div>
          <div class="stat"><small>You can borrow</small><b class="num">${money(D.eligible ? D.available : 0)}</b></div>
          <div class="stat"><small>${D.active ? 'Repay before' : 'This week closes in'}</small><b class="num">${until(D.dueAt)}</b></div></div>
        <div class="ln-grid">${D.active ? activeCard() : borrowCard()}
          <div>${D.active ? borrowCard() : `<section class="card-box ln-card"><h2>Terms</h2><dl class="kv"><dt>Interest</dt><dd>${D.fee ? `fixed fee ${money(D.fee)}` : 'None'}</dd><dt>Largest loan</dt><dd class="num">${money(D.maxLoan)}</dd><dt>Smallest loan</dt><dd class="num">${money(D.min)}</dd>
            <dt>Loans a week</dt><dd class="num">${D.rules.maxPerWeek}</dd><dt>Closed in the last</dt><dd class="num">${D.rules.cutoffHours} hours of the week</dd><dt>Unpaid at the close</dt><dd>${D.rules.allocationRepayPct}% of the next allocation</dd></dl></section>`}</div></div>
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
      if (!(v > 0)) { err.textContent = 'Enter how much you want to borrow.'; return; }
      let q;
      try { q = await post('/api/loans/quote', { amount: v }); } catch (ex) { err.textContent = ex.message; return; }
      const requestId = newId();
      const m = modal(`<span class="lbl">Review your loan</span><h2>Borrow ${money(q.amount)}?</h2>
        <dl class="kv" style="margin:12px 0 14px"><dt>You receive</dt><dd class="num">${money(q.amount)}</dd><dt>Into</dt><dd><span class="acct-tag weekly">Weekly account</span></dd><dt>Interest / fee</dt><dd>${q.fee ? money(q.fee) : 'None'}</dd>
          <dt class="total">You owe</dt><dd class="num total">${money(q.total)}</dd><dt>Repay before</dt><dd>${dateLong(q.dueAt)}</dd><dt>Your weekly account after</dt><dd class="num">${money(q.weeklyAfter)}</dd></dl>
        <div class="note-box"><b>What happens to your future weekly funds.</b> ${esc(q.effect)}</div>
        <div class="error-text" id="cf-err" style="min-height:20px;margin-top:8px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>Never mind</button><button class="btn btn-primary" id="cf-go">Yes, borrow ${money(q.amount)}</button></div>`);
      const go = m.el.querySelector('#cf-go');
      go.addEventListener('click', async () => {
        go.disabled = true;
        try {
          const r = await post('/api/loans/borrow', { amount: q.amount, confirm: true, requestId });
          setUser(r.user); m.close(); amount = '';
          toast(`${money(r.received)} is in your weekly account. You owe ${money(r.owed)}.`, 'ok', { ms: 5000 });
          await reload();
        } catch (ex) { m.el.querySelector('#cf-err').textContent = ex.message; go.disabled = false; }
      });
    }

    async function repay(v) {
      const err = root.querySelector('#rp-err'); err.textContent = '';
      if (v !== 'all' && !(v > 0)) { err.textContent = 'Enter how much to repay.'; return; }
      try {
        const r = await post('/api/loans/repay', { amount: v, requestId: newId() });
        setUser(r.user);
        toast(r.closed ? `Paid off. You repaid ${money(r.paid)} and owe nothing.` : `Repaid ${money(r.paid)}. You still owe ${money(r.owed)}.`, 'ok', { ms: 5000 });
        await reload();
      } catch (ex) { err.textContent = ex.message; }
    }

    draw();
    const timer = setInterval(() => { if (!dead && !document.querySelector('#modal-root .modal')) draw(); }, 60000);
    return { onEvent(ev) { if (['inbox', 'week'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
