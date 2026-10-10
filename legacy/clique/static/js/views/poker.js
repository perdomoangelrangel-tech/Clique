import { get, post } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, debounce, ICON } from '../util.js';
import { modal, toast } from '../ui.js';
import { emptyState } from './components.js';
import { amt, blindsText, moneyTag, initials } from './pokerfmt.js';

export default {
  async mount(root) {
    let tables = [], dead = false, busy = false;

    root.innerHTML = `<div class="page pk-lobby">
      <div class="lobby-head"><div><span class="kicker">The poker room // Texas Hold'em</span>
        <h1>Pull up<br><em>a chair.</em></h1>
        <p>No-limit Hold'em against your friends, live. Fake chips or real cash: the table decides before the first hand.</p></div>
        <div class="pk-actions"><button class="btn btn-primary btn-lg" id="pk-new">${ICON.plus} Open a table</button></div></div>
      <div id="pk-mine"></div>
      <div class="pk-cols"><section><div class="pk-sec-head"><h2>Public tables</h2><span class="lbl" id="pk-count"></span></div><div class="pk-list" id="pk-list"></div></section>
        <aside class="pk-code card-box paper"><span class="lbl">Private table</span><h3>Got a code?</h3>
          <p>Whoever opened the table has a six-letter code. Type it in and you are sitting.</p>
          <form id="pk-join-code"><input class="input" id="pk-code" maxlength="6" placeholder="ABC123" autocomplete="off" aria-label="Table code"><button class="btn btn-primary" id="pk-code-go">Sit down</button></form>
          <div class="error-text" id="pk-code-err"></div></aside></div></div>`;
    const $ = (s) => root.querySelector(s);

    const seatsRow = (t) => `<div class="pk-dots" aria-label="${t.players.length} of ${t.maxSeats} seats taken">${Array.from({ length: t.maxSeats }, (_, i) => `<i class="${t.players[i] ? 'on' : ''}">${t.players[i] ? initials(t.players[i]) : ''}</i>`).join('')}</div>`;
    const card = (t) => `<article class="pk-card ${t.mine ? 'mine' : ''}" data-id="${t.id}">
      <div class="pk-card-top"><div><h3>${esc(t.name)}</h3><div class="pk-sub">Hosted by <b>${esc(t.hostName || '?')}</b> · ${t.visibility === 'private' ? 'Private' : 'Public'}</div></div>${moneyTag(t.money)}</div>
      ${seatsRow(t)}
      <div class="pk-who">${t.players.length ? `<b>${t.players.length} of ${t.maxSeats}</b> seated: ${t.players.map(esc).join(', ')}` : `<b>Empty.</b> Somebody has to go first.`}</div>
      <div class="pk-card-foot"><span class="pk-meta"><span>Blinds <b class="num">${blindsText(t.smallBlind, t.bigBlind, t.scale)}</b></span><span>${t.money === 'real' ? 'Buy-in' : 'Stack'} <b class="num">${amt(t.stack, t.scale)}</b></span>
        <span class="pk-status ${t.status}">${t.status === 'playing' ? `In play · hand ${t.handNo}` : 'Waiting to start'}</span></span>
        <span class="pk-btns">${t.mine ? '<button class="btn btn-primary btn-sm" data-act="open">Back to my table</button>'
          : `<button class="btn btn-secondary btn-sm" data-act="watch">Watch</button><button class="btn btn-primary btn-sm" data-act="sit" ${t.full ? 'disabled' : ''}>${t.full ? 'Full' : 'Sit down'}</button>`}</span></div></article>`;

    function draw() {
      const mine = tables.find((t) => t.mine);
      $('#pk-mine').innerHTML = mine ? `<div class="pk-banner"><span class="vb-tag">You are seated</span><span>You're at <b>${esc(mine.name)}</b>. One table at a time.</span><button class="btn btn-sm vb-btn" data-open="${mine.id}">Back to the table</button></div>` : '';
      const pub = tables.filter((t) => t.visibility === 'public' && !t.mine);
      const own = tables.filter((t) => t.mine);
      $('#pk-count').textContent = `${pub.length} open`;
      $('#pk-list').innerHTML = own.concat(pub).length
        ? own.concat(pub).map(card).join('')
        : emptyState({ art: 'poker', tone: 'lime', kicker: 'No tables', title: 'Nobody is playing.', text: 'Open a table and wait for your friends. Or open one and act like you are busy.', actions: `<button class="btn btn-primary" data-new>${ICON.plus} Open a table</button>` });
    }
    async function load() {
      const d = await get('/api/poker/tables');
      if (dead) return;
      tables = d.tables; if (d.user) setUser(d.user);
      draw();
    }

    async function sit(t) {
      if (busy) return; busy = true;
      try {
        let confirm = false;
        if (t.money === 'real' && t.status === 'playing') {
          confirm = await new Promise((res) => {
            const m = modal(`<span class="lbl">Real cash</span><h2>Buy in for ${amt(t.stack, t.scale)}?</h2><p class="lede">This table is playing for real money. The buy-in comes out of your cash now, sits in front of you, and comes back to your cash when you leave.</p>
              <div class="modal-actions"><button class="btn btn-secondary" data-no>Never mind</button><button class="btn btn-primary" data-yes>Buy in</button></div>`);
            m.el.querySelector('[data-yes]').addEventListener('click', () => { m.close(); res(true); });
            m.el.querySelector('[data-no]').addEventListener('click', () => { m.close(); res(false); });
          });
          if (!confirm) { busy = false; return; }
        }
        const d = await post('/api/poker/join', { id: t.id, confirm });
        if (d.user) setUser(d.user);
        go(`#/poker/${t.id}`);
      } catch (ex) { toast(ex.message, 'err'); load().catch(() => {}); }
      busy = false;
    }

    function openCreate() {
      const m = modal(`<span class="lbl">New table</span><h2>Open a table</h2><p class="lede">You will be the host and pick the settings next. Everyone who sits down has to accept them.</p>
        <div class="field"><label for="nt-name">Name</label><input class="input" id="nt-name" maxlength="30" placeholder="${esc(S.user.username)}'s table" autocomplete="off"></div>
        <div class="field"><label>Who can sit?</label><div class="seg" id="nt-vis"><button type="button" data-v="public" class="active">${ICON.globe} Anyone</button><button type="button" data-v="private">${ICON.lock} Code only</button></div>
          <small id="nt-help">Listed in the poker room. Anyone can sit down or watch.</small></div>
        <div class="field"><label for="nt-seats">Seats</label><select class="select" id="nt-seats">${[2, 3, 4, 5, 6, 7, 8, 9].map((n) => `<option ${n === 6 ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
        <div class="error-text" id="nt-err" style="min-height:18px"></div>
        <div class="modal-actions"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="nt-go">Open it</button></div>`);
      let vis = 'public';
      m.el.querySelector('#nt-vis').addEventListener('click', (e) => {
        const b = e.target.closest('[data-v]'); if (!b) return;
        vis = b.dataset.v; m.el.querySelectorAll('#nt-vis button').forEach((x) => x.classList.toggle('active', x === b));
        m.el.querySelector('#nt-help').textContent = vis === 'public' ? 'Listed in the poker room. Anyone can sit down or watch.' : 'Hidden. Friends need the six-letter code you will get.';
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
      const t = tables.find((x) => x.id === b.closest('.pk-card').dataset.id); if (!t) return;
      if (b.dataset.act === 'sit') sit(t); else go(`#/poker/${t.id}`);
    });
    $('#pk-code').addEventListener('input', (e) => { e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''); });
    $('#pk-join-code').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = $('#pk-code-err'); err.textContent = '';
      const code = $('#pk-code').value.trim();
      if (code.length < 6) { err.textContent = 'Codes are six characters.'; return; }
      try { const d = await post('/api/poker/join', { code }); if (d.user) setUser(d.user); go(`#/poker/${d.table.id}`); }
      catch (ex) { err.textContent = ex.message; }
    });

    await load();
    const poll = setInterval(() => load().catch(() => {}), 6000);
    const reload = debounce(() => load().catch(() => {}), 300);
    return { onEvent(ev) { if (ev.type === 'poker') reload(); }, unmount() { dead = true; clearInterval(poll); } };
  },
};
