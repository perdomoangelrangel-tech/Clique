/* Weekly challenges: three that pay into the WEEKLY account and three that pay into the ACCUMULATED account. The page only shows
   what the server worked out (/api/challenges) and asks it to claim; it never counts anything itself. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, until, dateShort } from '../util.js';
import { toast } from '../ui.js';
import { gameSticker } from '../art.js';
import { emptyState } from './components.js';
import { t, th, intlLocale } from '../i18n.js';

// i18n: claves ↓
const ACCT = {
  weekly: { cls: 'weekly', tag: 'Cuenta semanal', head: 'Paga a tu cuenta semanal', note: 'Fichas para la semana en que las ganaste: juega con ellas o pagan un préstamo. Lo que sobre se reinicia al cerrar la semana, como todo en la cuenta semanal.', short: 'Semanal' },
  accumulated: { cls: 'accum', tag: 'Cuenta acumulada', head: 'Paga a tu cuenta acumulada', note: 'Fichas que te quedas. Nunca se reinician, y son las que gastan la Tienda y la Bolsa.', short: 'Acum.' },
};
// i18n: fin
const trim = (v) => String(Number(v).toFixed(2)).replace(/\.?0+$/, '');
/** What a number means for this goal: plain count, a multiplier, or chips. */
const show = (c, v) => (c.kind === 'mult' ? `${trim(v)}\u00d7` : c.kind === 'money' ? money(v) : Number(v).toLocaleString(intlLocale()));
const STATUS = { available: 'Sin empezar', in_progress: 'En curso', completed: 'Terminado: reclámalo', claimed: 'Reclamado', expired: 'Vencido' };      // i18n: claves

export default {
  async mount(root) {
    let D = await get('/api/challenges'), dead = false, busy = null;

    const card = (c, past = false) => {
      const a = ACCT[c.account], pct = Math.round((c.progress / c.target) * 100);
      const done = c.status === 'completed', claimed = c.status === 'claimed', expired = c.status === 'expired';
      return `<article class="ch-card card-box ${c.status} ${a.cls}-c" data-id="${esc(c.id)}" aria-label="${esc(c.title)}">
        <div class="ch-top"><h3>${c.game ? `<span class="ch-game">${gameSticker(c.game, 30)}</span>` : ''}${esc(c.title)}</h3><span class="acct-tag ${a.cls}">${t(a.tag)}</span></div>
        <p class="ch-desc">${esc(c.desc)}</p>
        <div><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="${c.target}" aria-valuenow="${c.progress}" aria-label="${esc(t('Avance de {reto}', { reto: c.title }))}"><i style="width:${pct}%"></i></div>
          <div class="ch-nums" style="margin-top:6px"><span><b>${show(c, c.progress)}</b> / ${show(c, c.target)}${c.kind === 'count' ? ' ' + esc(c.unit) : c.kind === 'mult' ? ' ' + t('en una ronda') : ' ' + t('ganados')}</span><span class="ch-state">${t(STATUS[c.status])}</span></div></div>
        <div class="ch-reward"><span class="amt">${money(c.reward)}</span><span>${th('a tu <b>{cuenta}</b>', { cuenta: t(a.tag).toLowerCase() })}</span>${c.xp ? `<span class="tag">+${c.xp} XP</span>` : ''}</div>
        <p class="ch-rule">${esc(c.rule)}</p>
        <div class="ch-actions">
          ${claimed ? `<span class="muted" style="font-size:13px">${c.claim && c.claim.auto ? t('Se abonó solo cuando cerró la semana.') : t('Premio reclamado.')}</span>`
            : expired ? `<span class="muted" style="font-size:13px">${t('No se terminó antes de que cerrara la semana, así que venció.')}</span>`
            : done && !past ? `<button class="btn btn-primary" data-claim="${esc(c.id)}" ${busy === c.id ? 'disabled' : ''}>${t('Reclamar {cantidad}', { cantidad: money(c.reward) })}</button>`
            : `<a class="btn btn-secondary btn-sm" href="${esc(c.href)}">${esc(c.cta)}</a>`}
          ${past ? '' : `<span class="muted num" style="font-size:12px">${t('quedan {tiempo}', { tiempo: until(D.end) })}</span>`}
        </div></article>`;
    };

    const column = (key, rows) => `<section aria-label="${esc(t(ACCT[key].head))}"><div class="gl-colhead ${ACCT[key].cls}"><h2>${esc(t(ACCT[key].tag))}</h2><p><b>${esc(t(ACCT[key].head))}.</b> ${esc(t(ACCT[key].note))}</p></div>${rows.map((c) => card(c)).join('')}</section>`;

    const history = () => {
      if (!D.history.length) return '';
      return `<div class="ch-hist"><div class="section-head"><div><span class="kicker">${t('Semanas anteriores')}</span><h2 class="page-title" style="font-size:clamp(26px,3vw,38px)">${t('Historial')}</h2></div></div>
        <p class="muted" style="margin:-8px 0 16px;max-width:70ch">${t('Un reto que terminaste pero no reclamaste se te abonó cuando cerró su semana. Uno que no terminaste simplemente venció.')}</p>
        ${D.history.map((h) => `<details><summary><span>${t('Semana del {fecha}', { fecha: dateShort(new Date(h.week + 'T12:00:00').getTime()) })}</span><span class="muted">${t('{pagados} pagados · {vencidos} vencidos', { pagados: h.items.filter((i) => i.status === 'claimed').length, vencidos: h.items.filter((i) => i.status === 'expired').length })}</span></summary>
          ${h.items.map((i) => `<div class="hrow"><span class="acct-tag ${ACCT[i.account].cls}">${t(ACCT[i.account].short)}</span><span>${esc(i.title)}<br><small class="muted">${show(i, i.progress)} / ${show(i, i.target)}${i.kind === 'count' ? ' ' + esc(i.unit) : ''}</small></span><b class="num">${money(i.reward)}</b><span class="ch-state">${t(STATUS[i.status])}</span></div>`).join('')}</details>`).join('')}</div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page">
        <div class="section-head"><div><span class="kicker">${t('Nuevos cada lunes')}</span><h1 class="page-title">${t('Retos de la semana.')}</h1>
          <p class="gl-sub">${t('Ocho metas cada semana. Cuatro pagan a tu <b>cuenta semanal</b>, cuatro a tu <b>cuenta acumulada</b>, y cada tarjeta dice cuál. Unas piden variedad o constancia; otras son de un juego (juega tantas manos, llega a un multiplicador, gana algunas fichas). Ninguna premia perder, pedir prestado ni apostar más.')} ${esc(D.rules.claimRule)}</p></div>
          <div class="stat" style="min-width:150px"><small>${t('Esta semana cierra en')}</small><b class="num">${until(D.end)}</b></div></div>
        <div class="gl-grid2">${column('weekly', D.weekly)}${column('accumulated', D.accumulated)}</div>
        <p class="muted" style="font-size:13px;max-width:78ch;margin:6px 2px 0">${t('Solo cuentan las jugadas con fichas de verdad del juego (una apuesta de al menos {cantidad}). Las rondas de práctica, los préstamos, los pagos, los envíos y las compras en la Tienda nunca cuentan. Los premios de retos vienen de fuera del juego, así que nunca mueven tu resultado en el ranking semanal.', { cantidad: money(D.rules.minStake) })}</p>
        ${history()}</div>`;
    };
    draw();

    const reload = async () => { try { D = await get('/api/challenges'); if (!dead) draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-claim]'); if (!b || busy) return;
      busy = b.dataset.claim; draw();
      try {
        const r = await post('/api/challenges/claim', { id: busy });
        setUser(r.user);
        const into = { cantidad: money(r.amount), cuenta: r.account === 'weekly' ? t('semanal') : t('acumulada'), xp: r.xp };
        toast(r.xp ? t('Reclamaste {cantidad} a tu cuenta {cuenta} (+{xp} XP).', into) : t('Reclamaste {cantidad} a tu cuenta {cuenta}.', into), 'ok', { ms: 5000 });
      } catch (ex) { toast(ex.message, 'err'); }
      busy = null; await reload();
    });
    const timer = setInterval(() => { if (!dead) draw(); }, 60000);          // the clock counts down
    return { onEvent(ev) { if (['inbox', 'week'].includes(ev.type)) reload(); }, unmount() { dead = true; clearInterval(timer); } };
  },
};
