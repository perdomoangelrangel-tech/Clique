import { get, post } from '../api.js';
import { S, setUser, refreshMe, balanceNow } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, cardEl, fillFront } from './common.js';
import { money, sleep, parseAmount } from '../util.js';
import { toast } from '../ui.js';

const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
const NAME = { J: 'Jack', Q: 'Queen', K: 'King', A: 'Ace' };
const rank = (c) => NAME[c.r] || c.r;
const SUIT_NAME = { S: 'spades', H: 'hearts', D: 'diamonds', C: 'clubs' };

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const TIE = meta.war.tiePays, CTIE = meta.war.colouredTiePays;
  host.innerHTML = `<div class="gm war">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label for="s-tie">Tie <small class="pays">pays ${TIE} to 1</small></label><div class="gm-input"><span>$</span><input id="s-tie" inputmode="decimal" autocomplete="off" placeholder="0"></div></div>
      <div class="gm-field"><label for="s-col">Coloured tie <small class="pays">pays ${CTIE} to 1</small></label><div class="gm-input"><span>$</span><input id="s-col" inputmode="decimal" autocomplete="off" placeholder="0"></div></div>
      <div class="bp-err" id="side-err"></div>
      <button class="btn-bet" id="go">Deal</button>
      <div class="gm-note">One card each, aces high. Higher card wins even money. A tie goes to war: you match your bet, you each get one more card, and you win if yours is at least as high. Tie pays when the first two cards match in rank. Coloured tie also needs the same colour.</div>
    </div>
    <div class="gm-stage bj-stage wr-stage" id="stage">
      <div class="bj-oval wr-oval">
        <div class="bj-zone"><div class="bj-label">Dealer</div><div class="wr-cards" id="d-cards"></div></div>
        <div class="bj-ribbon" id="ribbon">WIN PAYS 1 TO 1<small>A TIE GOES TO WAR</small></div>
        <div class="bj-zone"><div class="bj-label">You</div><div class="wr-cards" id="p-cards"></div></div>
      </div>
      <div class="wr-sides" id="sides"></div>
      <div class="wr-msg" id="msg">Place a bet. Pray for a king.</div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-war' });
  const stage = $('#stage'), go = $('#go'), dCards = $('#d-cards'), pCards = $('#p-cards'), msg = $('#msg'), ribbon = $('#ribbon'), sides = $('#sides');
  let busy = false, dead = false;

  const sideVal = (id) => { const v = parseAmount($(id).value); return Number.isFinite(v) && v > 0 ? Math.round(v * 100) / 100 : 0; };
  function check() {
    const tie = sideVal('#s-tie'), col = sideVal('#s-col'), main = bp.value();
    let err = '';
    if ((tie && tie < S.minBet - 1e-9) || (col && col < S.minBet - 1e-9)) err = `Side bets start at ${money(S.minBet)}.`;
    else if (Number.isFinite(main) && main + tie + col > balanceNow() + 1e-9) err = 'All those bets add up to more than you have.';
    $('#side-err').textContent = err;
    go.disabled = busy || !bp.valid() || !!err;
    return !err;
  }
  bp.onChange(check);
  ['#s-tie', '#s-col'].forEach((id) => $(id).addEventListener('input', (e) => {
    let v = e.target.value.replace(/[^\d.]/g, ''); const p = v.split('.'); if (p.length > 2) v = p[0] + '.' + p.slice(1).join('');
    if (v.includes('.')) { const [a, b] = v.split('.'); v = a + '.' + b.slice(0, 2); }
    e.target.value = v; check();
  }));

  const say = (t) => { msg.textContent = t; };
  const put = (zone, card, { down = true } = {}) => { const el = cardEl(card, { down }); zone.appendChild(el); return el; };
  const turn = (el, card) => { fillFront(el, card); el.classList.remove('down'); };
  const cardName = (c) => `${rank(c)} of ${SUIT_NAME[c.s]}`;
  const sideChips = (res) => {
    const out = [];
    if (res.bets.tie) out.push(`<span class="wr-side ${res.tiePayout ? 'w' : 'l'}">Tie ${money(res.bets.tie)} ${res.tiePayout ? `· +${money(res.tiePayout - res.bets.tie)}` : '· lost'}</span>`);
    if (res.bets.colouredTie) out.push(`<span class="wr-side ${res.colouredTiePayout ? 'w' : 'l'}">Coloured tie ${money(res.bets.colouredTie)} ${res.colouredTiePayout ? `· +${money(res.colouredTiePayout - res.bets.colouredTie)}` : '· lost'}</span>`);
    return out.join('');
  };

  go.addEventListener('click', async () => {
    if (busy || !check()) return;
    const main = bp.value(), tie = sideVal('#s-tie'), col = sideVal('#s-col');
    busy = true; go.disabled = true; bp.lock(true);
    dCards.innerHTML = ''; pCards.innerHTML = ''; sides.innerHTML = ''; ribbon.innerHTML = 'WIN PAYS 1 TO 1<small>A TIE GOES TO WAR</small>';
    const prev = deduct(main + tie + col); say('Cutting the shoe...');
    try {
      const body = { amount: main }; if (tie) body.tie = tie; if (col) body.colouredTie = col;
      const res = await post('/api/games/war', body);
      const pc = put(pCards, res.player), dc = put(dCards, res.dealer);
      await sleep(520); if (dead) return;
      turn(pc, res.player); await sleep(420); turn(dc, res.dealer); await sleep(650); if (dead) return;
      const net = (res.payout - res.wagered);
      if (res.outcome === 'win' || res.outcome === 'lose') {
        const w = res.outcome === 'win';
        say(w ? `Your ${cardName(res.player)} beats their ${rank(res.dealer)}. Even money.` : `Their ${cardName(res.dealer)} beats your ${rank(res.player)}.`);
        pc.classList.toggle('lost', !w); dc.classList.toggle('lost', w);
        finish(res, net, w);
        return;
      }
      // a tie: both cards are the same rank, so it goes to war
      ribbon.innerHTML = `WAR!<small>${res.outcome === 'surrender' ? 'YOU CAN\'T COVER THE RAISE' : `MATCHING BET ${money(res.war ? res.war.raise : 0)}`}</small>`;
      say(`${rank(res.player)} each. ${res.tie ? 'Tie.' : ''} ${res.outcome === 'surrender' ? 'No money for the raise, so you surrender: half back.' : 'It goes to war.'}`);
      if (res.outcome === 'surrender') { await sleep(900); finish(res, net, false); return; }
      await sleep(900); if (dead) return;
      const pw = put(pCards, res.war.player), dw = put(dCards, res.war.dealer);
      await sleep(520); turn(pw, res.war.player); await sleep(420); turn(dw, res.war.dealer); await sleep(700); if (dead) return;
      const won = res.war.win;
      say(won ? `War won. Your ${rank(res.war.player)} is at least their ${rank(res.war.dealer)}. Raise comes back.` : `War lost. Their ${rank(res.war.dealer)} beats your ${rank(res.war.player)}. Bet and raise gone.`);
      pw.classList.toggle('lost', !won); dw.classList.toggle('lost', won);
      finish(res, net, won);
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); say('Place a bet. Pray for a king.'); busy = false; bp.lock(false); check(); }
  });

  function finish(res, net, won) {
    setUser(res.user); sides.innerHTML = sideChips(res);
    if (net > 0.004) {
      resultPop({ net, label: res.tiePayout || res.colouredTiePayout ? 'Side bet hit' : 'You win' });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.4, { count: 50, power: 320, colors: WIN_COLORS });
    } else if (net < -0.004) {
      resultPop({ net, label: res.outcome === 'surrender' ? 'Surrendered' : 'House wins' });
      shake(stage);
    } else resultPop({ net: 0, label: 'Bet returned' });
    ctx.refreshBets?.(); busy = false; bp.lock(false); check();
  }

  check();
  return { unmount() { dead = true; bp.destroy(); } };
}
