/* The statement: every movement in both accounts, newest first, from the server's ledger. */
import { get } from '../api.js';
import { S } from '../state.js';
import { esc, money, moneyFull, dateLong, ago, ICON } from '../util.js';
import { emptyState } from './components.js';
import { recall, remember } from '../viewstate.js';
import { t } from '../i18n.js';
import { gameName } from '../gamelist.js';

// i18n: claves ↓
const REASONS = {
  welcome: 'Fichas de bienvenida', opening: 'Saldo que pasó cuando empezaron las dos cuentas', voucher: 'Vale de rescate', deposit: 'Fichas agregadas (por votación)', 'weekly.midweek': 'Bono del miércoles',
  'weekly.allocation': 'Semana nueva: se rellenó la cuenta semanal', 'weekly.expired': 'Semana nueva: vencieron las fichas semanales que sobraron', 'weekly.reward': 'Premio semanal',
  'market.buy': 'Compraste acciones de una apuesta', 'market.sell': 'Vendiste acciones de una apuesta', 'market.payout': 'Apuesta ganada', 'market.refund': 'Apuesta devuelta', 'market.withdraw': 'Te saliste de una apuesta al costo',
  'stocks.buy': 'Compraste acciones en la Bolsa', 'stocks.sell': 'Vendiste acciones en la Bolsa', 'store.buy': 'Compra en la Tienda', poker: 'Póker',
  'casino.horses': 'Carreras de caballos', other: 'Otro',
  'loan.borrow': 'Préstamo recibido', 'loan.repay': 'Pago de préstamo', 'loan.collect': 'Préstamo cobrado de la cuenta semanal',
  'challenge.weekly': 'Premio de reto semanal', 'challenge.accumulated': 'Premio de reto semanal', milestone: 'Premio por logro',
  'transfer.out': 'Enviado a un amigo', 'transfer.in': 'Recibido de un amigo',
};
// i18n: fin
const label = (r) => (REASONS[r] ? t(REASONS[r]) : r.startsWith('casino.') ? t('Casino: {juego}', { juego: gameName(r.slice(7)) }) : r);
const acctShort = (a) => (a === 'weekly' ? t('Semanal') : t('Acumulada'));

export default {
  async mount(root) {
    let account = recall('statement').account || '', data = null, more = [], busy = false;
    const draw = () => {
      const rows = [...data.entries, ...more].filter((e) => !account || e.account === account);
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">${t('Cada ficha, anotada')}</span><h1 class="page-title">${t('Estado de cuenta.')}</h1></div></div>
        <div class="acct-cards">
          <div class="card-box pad-lg acct ${account === 'weekly' ? 'sel' : ''}"><span class="lbl">${t('Cuenta semanal')}</span><b class="num">${moneyFull(data.balances.weekly)}</b>
            <p class="muted">${t('Fichas para esta semana: apuestas, casino y póker. Se arma otra vez cada lunes y nunca se vuelve fichas acumuladas.')}</p></div>
          <div class="card-box pad-lg acct ${account === 'accumulated' ? 'sel' : ''}"><span class="lbl">${t('Cuenta acumulada')}</span><b class="num">${moneyFull(data.balances.accumulated)}</b>
            <p class="muted">${t('Lo que te quedas. Aquí llegan los premios semanales, y la Tienda y la Bolsa gastan de aquí.')}</p></div></div>
        <div class="tabs" id="stabs"><button data-a="" class="${!account ? 'active' : ''}">${t('Las dos')}</button><button data-a="weekly" class="${account === 'weekly' ? 'active' : ''}">${t('Semanal')}</button><button data-a="accumulated" class="${account === 'accumulated' ? 'active' : ''}">${t('Acumulada')}</button></div>
        ${rows.length ? `<div class="card-box tbl-wrap"><table class="tbl st-tbl"><thead><tr><th>${t('Cuándo')}</th><th>${t('Qué')}</th><th>${t('Cuenta')}</th><th class="r">${t('Cantidad')}</th><th class="r">${t('Saldo después')}</th><th class="id-col">${t('Movimiento')}</th></tr></thead><tbody>
          ${rows.map((e) => `<tr><td class="muted" title="${esc(dateLong(e.t))}">${esc(dateLong(e.t))}</td>
            <td><b>${esc(label(e.reason))}</b>${e.note ? `<div class="muted" style="font-size:12px">${esc(e.note)}</div>` : ''}${e.external ? ` <span class="tag" title="${esc(t('Fichas que llegaron de fuera del juego o salieron de él. Nunca cuentan como premio.'))}">${t('fuera del juego')}</span>` : ''}</td>
            <td><span class="tag ${e.account === 'accumulated' ? 'good' : ''}">${acctShort(e.account)}</span></td>
            <td class="r num ${e.amount > 0 ? 'up' : e.amount < 0 ? 'down' : ''}">${money(e.amount, { plus: true })}</td><td class="r num">${money(e.balance)}</td>
            <td class="id-col mono muted" style="font-size:11px">${esc(e.id)}</td></tr>`).join('')}</tbody></table></div>
          ${rows.length >= 60 ? `<div style="text-align:center;margin-top:14px"><button class="btn btn-secondary" id="st-more">${t('Ver anteriores')}</button></div>` : ''}`
          : emptyState({ art: 'paper', tone: 'cream', tight: true, kicker: t('Aquí no hay nada'), title: esc(t('Todavía no hay movimientos.')), text: esc(t('En cuanto apuestes, ganes, compres o te paguen, se anota aquí.')) })}
        ${data.older.length ? `<details style="margin-top:28px"><summary class="lbl" style="cursor:pointer">${t('Actividad anterior, sumada por semana')}</summary>
          <div class="card-box tbl-wrap" style="margin-top:10px"><table class="tbl"><thead><tr><th>${t('Semana del')}</th><th>${t('Qué')}</th><th>${t('Cuenta')}</th><th class="r">${t('Movimientos')}</th><th class="r">${t('Total')}</th></tr></thead><tbody>
          ${data.older.filter((o) => !account || o.account === account).map((o) => `<tr><td>${esc(o.week)}</td><td>${esc(label(o.reason))}</td><td>${acctShort(o.account)}</td><td class="r num">${o.count}</td><td class="r num ${o.amount >= 0 ? 'up' : 'down'}">${money(o.amount, { plus: true })}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
      </div>`;
    };
    data = await get('/api/ledger?limit=60');
    draw();
    root.addEventListener('click', async (e) => {
      const btn = e.target.closest('button'); if (!btn || busy) return;
      if (btn.dataset.a !== undefined && btn.closest('#stabs')) { account = btn.dataset.a; remember('statement', { account }); draw(); }
      else if (btn.id === 'st-more') {
        busy = true;
        try {
          const all = [...data.entries, ...more];
          const d = await get(`/api/ledger?limit=60&before=${all[all.length - 1].t}`);
          more.push(...d.entries); draw();
        } finally { busy = false; }
      }
    });
    return { onEvent(ev) { if (ev.type !== 'chat' && ev.type !== 'presence' && ev.type !== 'voice') get('/api/ledger?limit=60').then((d) => { data = d; more = []; draw(); }).catch(() => {}); } };
  },
};
