import { get, post } from '../api.js';
import { S, setUser, refreshMe, balanceNow } from '../state.js';
import { betPanel } from './betpanel.js';
import { deduct, burst, resultPop, shake, cardEl, fillFront } from './common.js';
import { money, sleep, parseAmount } from '../util.js';
import { toast } from '../ui.js';
import { t, th, CHIP_SIGN } from '../i18n.js';

const WIN_COLORS = ['#C6F432', '#EFE6D2', '#FF4B2B'];
const NAME = { J: 'Jota', Q: 'Reina', K: 'Rey', A: 'As' };                                      // i18n: claves
const rank = (c) => (NAME[c.r] ? t(NAME[c.r]) : c.r);
const SUIT_NAME = { S: 'espadas', H: 'corazones', D: 'diamantes', C: 'tréboles' };               // i18n: claves

export default async function mount(host, ctx = {}) {
  const meta = await get('/api/games/meta');
  const TIE = meta.war.tiePays, CTIE = meta.war.colouredTiePays;
  const ribbonText = () => `${t('GANAR PAGA 1 A 1')}<small>${t('UN EMPATE VA A LA GUERRA')}</small>`;
  host.innerHTML = `<div class="gm war">
    <div class="gm-panel">
      <div id="bet"></div>
      <div class="gm-field"><label for="s-tie">${t('Empate')} <small class="pays">${t('paga {n} a 1', { n: TIE })}</small></label><div class="gm-input"><span>${CHIP_SIGN}</span><input id="s-tie" inputmode="decimal" autocomplete="off" placeholder="0"></div></div>
      <div class="gm-field"><label for="s-col">${t('Empate de color')} <small class="pays">${t('paga {n} a 1', { n: CTIE })}</small></label><div class="gm-input"><span>${CHIP_SIGN}</span><input id="s-col" inputmode="decimal" autocomplete="off" placeholder="0"></div></div>
      <div class="bp-err" id="side-err"></div>
      <button class="btn-bet" id="go">${t('Repartir')}</button>
      <div class="gm-note">${t('Una carta cada quien; el as es la más alta. La carta más alta gana a la par. Un empate va a la guerra: igualas tu apuesta, cada quien recibe otra carta y ganas si la tuya es igual o más alta. Empate paga cuando las dos primeras cartas son del mismo valor. Empate de color además necesita el mismo color.')}</div>
    </div>
    <div class="gm-stage bj-stage wr-stage" id="stage">
      <div class="bj-oval wr-oval">
        <div class="bj-zone"><div class="bj-label">${t('Crupier')}</div><div class="wr-cards" id="d-cards"></div></div>
        <div class="bj-ribbon" id="ribbon">${ribbonText()}</div>
        <div class="bj-zone"><div class="bj-label">${t('Tú')}</div><div class="wr-cards" id="p-cards"></div></div>
      </div>
      <div class="wr-sides" id="sides"></div>
      <div class="wr-msg" id="msg">${t('Haz una apuesta. Pídele al cielo un rey.')}</div>
    </div></div>`;
  const $ = (s) => host.querySelector(s);
  const bp = betPanel($('#bet'), { key: 'bet-war' });
  const stage = $('#stage'), go = $('#go'), dCards = $('#d-cards'), pCards = $('#p-cards'), msg = $('#msg'), ribbon = $('#ribbon'), sides = $('#sides');
  let busy = false, dead = false;

  const sideVal = (id) => { const v = parseAmount($(id).value); return Number.isFinite(v) && v > 0 ? Math.round(v * 100) / 100 : 0; };
  function check() {
    const tie = sideVal('#s-tie'), col = sideVal('#s-col'), main = bp.value();
    let err = '';
    if ((tie && tie < S.minBet - 1e-9) || (col && col < S.minBet - 1e-9)) err = t('Las apuestas laterales empiezan en {cantidad}.', { cantidad: money(S.minBet) });
    else if (Number.isFinite(main) && main + tie + col > balanceNow() + 1e-9) err = t('Todas esas apuestas suman más de lo que tienes.');
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

  const say = (text) => { msg.textContent = text; };
  const put = (zone, card, { down = true } = {}) => { const el = cardEl(card, { down }); zone.appendChild(el); return el; };
  const turn = (el, card) => { fillFront(el, card); el.classList.remove('down'); };
  const cardName = (c) => t('{carta} de {palo}', { carta: rank(c), palo: t(SUIT_NAME[c.s]) });
  const sideChips = (res) => {
    const out = [];
    if (res.bets.tie) out.push(`<span class="wr-side ${res.tiePayout ? 'w' : 'l'}">${t('Empate')} ${money(res.bets.tie)} ${res.tiePayout ? `· +${money(res.tiePayout - res.bets.tie)}` : '· ' + t('perdida')}</span>`);
    if (res.bets.colouredTie) out.push(`<span class="wr-side ${res.colouredTiePayout ? 'w' : 'l'}">${t('Empate de color')} ${money(res.bets.colouredTie)} ${res.colouredTiePayout ? `· +${money(res.colouredTiePayout - res.bets.colouredTie)}` : '· ' + t('perdida')}</span>`);
    return out.join('');
  };

  go.addEventListener('click', async () => {
    if (busy || !check()) return;
    const main = bp.value(), tie = sideVal('#s-tie'), col = sideVal('#s-col');
    busy = true; go.disabled = true; bp.lock(true);
    dCards.innerHTML = ''; pCards.innerHTML = ''; sides.innerHTML = ''; ribbon.innerHTML = ribbonText();
    const prev = deduct(main + tie + col); say(t('Cortando el zapato...'));
    try {
      const body = { amount: main }; if (tie) body.tie = tie; if (col) body.colouredTie = col;
      const res = await post('/api/games/war', body);
      const pc = put(pCards, res.player), dc = put(dCards, res.dealer);
      await sleep(520); if (dead) return;
      turn(pc, res.player); await sleep(420); turn(dc, res.dealer); await sleep(650); if (dead) return;
      const net = (res.payout - res.wagered);
      if (res.outcome === 'win' || res.outcome === 'lose') {
        const w = res.outcome === 'win';
        say(w ? t('Tu {carta} le gana a su {otra}. Paga a la par.', { carta: cardName(res.player), otra: rank(res.dealer) }) : t('Su {carta} le gana a tu {otra}.', { carta: cardName(res.dealer), otra: rank(res.player) }));
        pc.classList.toggle('lost', !w); dc.classList.toggle('lost', w);
        finish(res, net, w);
        return;
      }
      // a tie: both cards are the same rank, so it goes to war
      ribbon.innerHTML = `${t('¡GUERRA!')}<small>${res.outcome === 'surrender' ? t('NO TE ALCANZA PARA LA SUBIDA') : th('IGUALAS LA APUESTA: {cantidad}', { cantidad: money(res.war ? res.war.raise : 0) })}</small>`;
      say([t('{carta} cada quien.', { carta: rank(res.player) }), res.tie ? t('Empate.') : '', res.outcome === 'surrender' ? t('No tienes fichas para la subida, así que te rindes: recuperas la mitad.') : t('Se va a la guerra.')].filter(Boolean).join(' '));
      if (res.outcome === 'surrender') { await sleep(900); finish(res, net, false); return; }
      await sleep(900); if (dead) return;
      const pw = put(pCards, res.war.player), dw = put(dCards, res.war.dealer);
      await sleep(520); turn(pw, res.war.player); await sleep(420); turn(dw, res.war.dealer); await sleep(700); if (dead) return;
      const won = res.war.win;
      say(won ? t('Guerra ganada. Tu {carta} es igual o más alta que su {otra}. La subida regresa.', { carta: rank(res.war.player), otra: rank(res.war.dealer) }) : t('Guerra perdida. Su {carta} le gana a tu {otra}. Se van la apuesta y la subida.', { carta: rank(res.war.dealer), otra: rank(res.war.player) }));
      pw.classList.toggle('lost', !won); dw.classList.toggle('lost', won);
      finish(res, net, won);
    } catch (ex) { toast(ex.message, 'err'); setUser(prev); refreshMe().catch(() => {}); say(t('Haz una apuesta. Pídele al cielo un rey.')); busy = false; bp.lock(false); check(); }
  });

  function finish(res, net, won) {
    setUser(res.user); sides.innerHTML = sideChips(res);
    if (net > 0.004) {
      resultPop({ net, label: res.tiePayout || res.colouredTiePayout ? t('Pegó la apuesta lateral') : t('Ganas') });
      const r = stage.getBoundingClientRect(); burst(stage, r.width / 2, r.height * 0.4, { count: 50, power: 320, colors: WIN_COLORS });
    } else if (net < -0.004) {
      resultPop({ net, label: res.outcome === 'surrender' ? t('Te rendiste') : t('Gana la casa') });
      shake(stage);
    } else resultPop({ net: 0, label: t('Apuesta devuelta') });
    ctx.refreshBets?.(); busy = false; bp.lock(false); check();
  }

  check();
  return { unmount() { dead = true; bp.destroy(); } };
}
