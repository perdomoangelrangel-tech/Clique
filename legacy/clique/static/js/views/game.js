import { get, post } from '../api.js';
import { S, bus, setUser } from '../state.js';
import { esc, detailText, money, ago, ICON } from '../util.js';
import { modal, toast } from '../ui.js';
import { gameById } from '../gamelist.js';
import { gameSticker } from '../art.js';
import { emptyState } from './components.js';

const LOADERS = {
  limbo: () => import('../games/limbo.js'),
  roulette: () => import('../games/roulette.js'),
  blackjack: () => import('../games/blackjack.js'),
  chicken: () => import('../games/chicken.js'),
  coinflip: () => import('../games/coinflip.js'),
  war: () => import('../games/war.js'),
  dice: () => import('../games/dice.js'),
  mines: () => import('../games/mines.js'),
  moles: () => import('../games/moles.js'),
  tower: () => import('../games/tower.js'),
  hilo: () => import('../games/hilo.js'),
  wheel: () => import('../games/wheel.js'),
  rps: () => import('../games/rps.js'),
};

export default {
  async mount(root, [name]) {
    const g = gameById(name);
    if (!g || !LOADERS[name]) { root.innerHTML = `<div class="page">${emptyState({ art: 'wheel', tone: 'verm', kicker: 'No such game', title: 'We do not have that one.', text: 'Thirteen games. Pick one of the thirteen.', actions: '<a class="btn btn-primary" href="#/games">Back to the lobby</a>' })}</div>`; return; }
    root.innerHTML = `<div class="page">
      <div class="cg" id="cg">
        <div class="cg-head"><button id="g-info" title="How to play" aria-label="How to play">${ICON.info}</button><span class="nm">${gameSticker(name, 36)}${esc(g.name)}</span>
          <div class="demo-ctl"><div class="acct-switch" id="g-acct" role="group" aria-label="Play with which account"><button type="button" data-a="weekly" class="weekly"><span>Weekly</span><b class="num"></b></button><button type="button" data-a="accumulated" class="accum"><span><i class="full">Accumulated</i><i class="short">Saved</i></span><b class="num"></b></button></div>
            <button class="demo-switch" id="g-demo" role="switch" aria-checked="false" title="Practice with pretend chips. Nothing counts."><i></i><span>Demo bets</span></button>
            <span class="demo-bal hidden" id="demo-bal" title="Your demo balance"></span><button class="demo-reset hidden" id="demo-reset" title="Refill the demo balance to $1,000">Refill</button></div>
          <button class="fair" id="g-fair">${ICON.shield} Fair play</button></div>
        <div class="cg-body" id="game-host"></div>
        <div class="cg-foot"><button id="g-full" title="Fullscreen" aria-label="Fullscreen">${ICON.expand}</button><div class="wm">clique</div></div>
      </div>
      <div class="cg-tabs"><button class="active" data-t="mine">My bets</button><button data-t="wins">Big wins</button></div>
      <div id="bets"></div></div>`;

    root.querySelector('#g-info').addEventListener('click', () => {
      modal(`<span class="lbl">How it works</span><h2>${esc(g.name)}</h2><p class="lede">${esc(g.info)}</p><div class="modal-actions"><button class="btn btn-primary" data-close>Got it</button></div>`);
    });
    root.querySelector('#g-fair').addEventListener('click', () => modal(`<span class="lbl">No funny business</span><h2>Fair play</h2>
      <p class="lede">Every card, roll and spin comes from the server's secure random number generator, and the game state lives on the server too. Nobody can change an outcome from their browser.</p>
      <p style="margin-top:-6px;color:var(--text-2)">Return to player on ${esc(g.name)} is <b class="num">${esc(g.rtp)}</b>. That's the long-run average. Tonight is a different story.</p>
      <div class="modal-actions"><button class="btn btn-primary" data-close>Fine</button></div>`));
    root.querySelector('#g-full').addEventListener('click', () => {
      const el = root.querySelector('#cg');
      if (document.fullscreenElement) document.exitFullscreen(); else el.requestFullscreen?.().catch(() => {});
    });

    // my bets / big wins under the game
    let mode = 'mine', dead = false;
    const drawBets = async () => {
      const box = root.querySelector('#bets'); if (!box || dead) return;
      if (mode === 'mine') {
        const d = await get('/api/games/history'); const rows = d.history.filter((h) => h.game === name).slice(0, 12);
        box.innerHTML = rows.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th class="r">Bet</th><th class="r">Payout</th><th class="r">Multiplier</th><th>Result</th><th class="r">When</th></tr></thead><tbody>
          ${rows.map((h) => `<tr><td class="r">${money(h.bet)}</td><td class="r ${h.profit > 0 ? 'up' : h.profit < 0 ? 'down' : ''}">${money(h.payout)}</td><td class="r">${h.mult ? h.mult.toLocaleString() + 'x' : '—'}</td><td class="muted mono" style="font-size:12px">${detailText(h.detail)}</td><td class="r muted">${ago(h.t)}</td></tr>`).join('')}</tbody></table></div>`
          : emptyState({ art: 'snake', tone: 'cream', tight: true, kicker: 'No bets', title: 'Nothing here yet.', text: 'Your bets on this game show up here. Both kinds.' });
      } else {
        const d = await get('/api/games/feed'); const rows = d.feed.filter((w) => w.game === name);
        box.innerHTML = rows.length ? `<div class="card-box pad">${rows.map((w) => `<div class="list-row"><div class="grow"><b>${esc(w.user)}</b></div><span class="tag good">${w.mult.toLocaleString()}x</span><b class="num up" style="width:120px;text-align:right">${money(w.profit, { plus: true })}</b><span class="muted mono" style="width:80px;text-align:right;font-size:12px">${ago(w.t)}</span></div>`).join('')}</div>`
          : emptyState({ art: 'trophy', tone: 'lime', tight: true, kicker: 'No big wins', title: 'Nobody has hit it big here.', text: 'Wins of 2x or more land on this board.' });
      }
    };
    root.querySelector('.cg-tabs').addEventListener('click', (e) => {
      const b = e.target.closest('[data-t]'); if (!b) return;
      mode = b.dataset.t; root.querySelectorAll('.cg-tabs button').forEach((x) => x.classList.toggle('active', x === b)); drawBets();
    });

    // ---- the game itself, on the real wallet or the practice one
    const host = root.querySelector('#game-host'), cg = root.querySelector('#cg');
    const demoBtn = root.querySelector('#g-demo'), demoBal = root.querySelector('#demo-bal'), refillBtn = root.querySelector('#demo-reset');
    const ctx = { refreshBets: () => { if (mode === 'mine') drawBets().catch(() => {}); } };
    let inst = null;
    async function boot() {
      try { inst?.unmount?.(); } catch { /* the old round is going away anyway */ }
      inst = null; host.innerHTML = '';
      const mod = await LOADERS[name]();
      const made = await mod.default(host, ctx);
      if (dead) { made?.unmount?.(); return; }
      inst = made;
    }
    // which account the chips come from: the weekly one (the default) or the accumulated one. The choice is kept for this browser tab, and every game page opens on it.
    const acctBox = root.querySelector('#g-acct');
    const paintAcct = () => {
      acctBox.classList.toggle('hidden', S.demo);                       // practice chips have a wallet of their own
      acctBox.querySelectorAll('button').forEach((b) => {
        const on = b.dataset.a === S.acct;
        b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
        b.querySelector('b').textContent = money(b.dataset.a === 'weekly' ? (S.user?.weekly ?? S.user?.balance ?? 0) : (S.user?.accum ?? 0));
      });
      cg.classList.toggle('on-accum', S.acct === 'accumulated' && !S.demo);
    };
    async function setAcct(a) {
      if (a === S.acct) return;
      S.acct = a; try { sessionStorage.setItem('clique-acct', a); } catch { /* the choice is just not kept */ }
      paintAcct(); await boot(); drawBets().catch(() => {});             // the game starts again on the other account (a round in progress stays where it was)
    }
    acctBox.addEventListener('click', (e) => { const b = e.target.closest('[data-a]'); if (b) setAcct(b.dataset.a); });
    const onUserAcct = () => paintAcct();
    bus.addEventListener('user', onUserAcct);
    const paintDemo = () => {
      cg.classList.toggle('is-demo', S.demo);
      demoBtn.setAttribute('aria-checked', String(S.demo));
      demoBal.classList.toggle('hidden', !S.demo); refillBtn.classList.toggle('hidden', !S.demo);
      if (S.demo && S.demoUser) demoBal.textContent = 'Demo ' + money(S.demoUser.balance);
      paintAcct();
    };
    const onWallet = (e) => { if (e.detail?.demo) paintDemo(); };
    bus.addEventListener('user', onWallet);
    async function setDemo(on) {
      demoBtn.disabled = true; refillBtn.disabled = true;
      try {
        if (on) { const d = await get('/api/games/demo'); S.demo = true; setUser(d.user); } else S.demo = false;
        paintDemo(); await boot(); drawBets().catch(() => {});
      } catch (ex) { S.demo = false; paintDemo(); toast(ex.message, 'err'); }
      demoBtn.disabled = false; refillBtn.disabled = false;
    }
    demoBtn.addEventListener('click', () => setDemo(!S.demo));
    refillBtn.addEventListener('click', async () => {
      demoBtn.disabled = true; refillBtn.disabled = true;
      try { const d = await post('/api/games/demo/reset', {}); setUser(d.user); paintDemo(); await boot(); drawBets().catch(() => {}); toast('Demo chips refilled. Lose them again.', 'ok'); }
      catch (ex) { toast(ex.message, 'err'); }
      demoBtn.disabled = false; refillBtn.disabled = false;
    });

    S.demo = false;
    try { S.acct = sessionStorage.getItem('clique-acct') === 'accumulated' ? 'accumulated' : 'weekly'; } catch { S.acct = 'weekly'; }
    paintAcct();
    await boot();
    drawBets().catch(() => {});
    return {
      onEvent: (ev) => inst?.onEvent?.(ev),
      unmount() { dead = true; S.demo = false; bus.removeEventListener('user', onWallet); bus.removeEventListener('user', onUserAcct); inst?.unmount?.(); },
    };
  },
};
