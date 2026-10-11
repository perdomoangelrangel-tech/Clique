/* Rank and milestones. RANK is long-term progression (XP, never reset, never demoted) and is NOT the weekly leaderboard.
   MILESTONES are lifetime goals that pay into the accumulated account when you claim them. Everything shown comes from /api/progress. */
import { get, post } from '../api.js';
import { setUser } from '../state.js';
import { esc, money, ago, num, rankLabel } from '../util.js';
import { rankBadge, gameSticker } from '../art.js';
import { toast } from '../ui.js';
import { t, th, tp } from '../i18n.js';

const n = (x) => num(x, 0);
const trim = (v) => String(Number(v).toFixed(2)).replace(/\.?0+$/, '');

export default {
  async mount(root) {
    let D = await get('/api/progress'), dead = false, busy = null, mtab = 'all';

    const hero = () => {
      const r = D.rank;
      return `<section class="card-box rk-hero" aria-label="${esc(t('Tu rango'))}">
        <div class="rk-big">${rankBadge(r, 112)}</div>
        <div><span class="kicker">${t('Tu rango')}</span><div class="rk-name">${esc(rankLabel(r.label))}</div>
          <p class="rk-xp"><b class="num">${n(D.xp)}</b> XP${r.max ? ' · ' + t('lo más alto de la escalera') : ''}</p>
          ${r.max ? '<div class="pbar" aria-hidden="true"><i style="width:100%"></i></div>'
            : `<div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.pct}" aria-label="${esc(t('Avance a {rango}', { rango: rankLabel(r.nextLabel) }))}"><i style="width:${r.pct}%"></i></div>
               <div class="rk-next"><span>${th('<b class="num">{xp}</b> XP para <b>{rango}</b>', { xp: n(r.toNext), rango: rankLabel(r.nextLabel) })}</span><span class="num">${n(r.floor)} → ${n(r.next)}</span></div>`}
          <div class="rk-next" style="margin-top:12px"><span>${th('Hoy ganaste <b class="num">{xp}</b> de <b class="num">{tope}</b> XP', { xp: D.today.xp, tope: D.today.cap })}</span><span>${t('Se reinicia a medianoche')}</span></div></div></section>`;
    };

    const ladder = () => `<div class="rk-ladder" role="list" aria-label="${esc(t('Todos los rangos'))}">${D.ladder.map((s) => `<div class="rk-step ${s.reached ? 'reached' : ''} ${s.current ? 'current' : ''}" role="listitem" ${s.current ? 'aria-current="true"' : ''}>${rankBadge(s, 34)}<b>${esc(rankLabel(s.label))}</b><small class="num">${n(s.xp)} XP</small></div>`).join('')}</div>`;

    const how = () => `<div class="rk-cols"><div class="card-box pad-lg"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 6px">${t('Cómo se gana XP')}</h3>
        <p class="muted" style="margin:0 0 12px">${t('Lo que cuenta es participar, poco a poco, con un límite diario para que nadie suba a base de repetir. Solo cuentan apuestas de {cantidad} o más en tus cuentas de verdad (no la de práctica), y una apuesta más grande vale exactamente lo mismo.', { cantidad: money(1) })}</p>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>${t('Lo que hiciste')}</th><th class="r">${t('XP cada vez')}</th><th class="r">${t('Máximo al día')}</th><th class="r hide-sm">${t('Hoy')}</th></tr></thead><tbody>
          ${D.sources.map((s) => `<tr><td>${esc(s.text)}</td><td class="r num">+${s.xp}</td><td class="r num">${s.cap}</td><td class="r num hide-sm">${s.usedToday} / ${s.cap}</td></tr>`).join('')}
          ${D.bonuses.map((b) => `<tr><td>${esc(b.text)}</td><td class="r num">+${esc(b.xp)}</td><td class="r muted">${t('una vez')}</td><td class="r hide-sm"></td></tr>`).join('')}
        </tbody></table></div>
        <p class="muted" style="margin:12px 0 0;font-size:13px">${t('Nunca más de {tope} XP al día por participar.', { tope: D.today.cap })}</p></div>
      <div><div class="card-box pad-lg" style="margin-bottom:18px"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 10px">${t('No cuenta')}</h3>
        <ul class="rk-list">${D.notCounted.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>
        <div class="card-box pad-lg"><h3 style="font-family:var(--f-display);font-size:24px;margin:0 0 10px">${t('Ascensos')}</h3>
        ${D.history.length ? `<ul class="rk-hist">${D.history.map((h) => `<li>${rankBadge({ tier: h.tier, division: 0, label: h.to }, 22)}<span><b>${esc(rankLabel(h.to))}</b> <span class="muted">${t('desde {rango}', { rango: rankLabel(h.from) })} · ${ago(h.t)}</span></span></li>`).join('')}</ul>` : `<p class="muted" style="margin:0">${t('Ninguno todavía. Tu primer ascenso no está lejos.')}</p>`}</div></div></div>`;

    const tierRow = (m, tier) => `<div class="ms-tier ${tier.status}"><div><span class="num">${esc(tier.label)}</span><span class="ms-sub">${t('{cantidad} a tu cuenta acumulada', { cantidad: money(tier.money) })}${tier.xp ? ` · +${tier.xp} XP` : ''}</span></div>
      ${tier.status === 'reached' ? `<button class="btn btn-primary btn-sm" data-claim="${esc(tier.id)}" ${busy === tier.id ? 'disabled' : ''}>${t('Reclamar')}</button>` : tier.status === 'claimed' ? `<span class="ch-state">${t('Reclamado')}</span>` : `<span class="ch-state">${t('Próximo')}</span>`}</div>`;

    const milestoneCard = (m) => {
      const nxt = m.next, pct = nxt ? Math.min(100, Math.round((m.value / nxt.target) * 100)) : 100;
      const rank = m.metric === 'rank_tier';
      const now = rank ? th('<b>{rango}</b> ahora', { rango: rankLabel(D.rank.name) }) : m.kind === 'mult' ? th('lo mejor: <b class="num">{x}×</b>', { x: trim(m.value) }) : m.kind === 'money' ? th('<b class="num">{cantidad}</b> ganados', { cantidad: money(m.value) }) : `<b class="num">${n(m.value)}</b> ${esc(m.unit)}`;
      return `<article class="ms-card card-box" aria-label="${esc(m.title)}"><div><h3>${m.group === 'game' ? `<span class="ch-game">${gameSticker(m.game, 30)}</span>` : ''}${esc(m.title)}</h3><p>${esc(m.desc)}</p></div>
        <div><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="${esc(t('Avance de {logro}', { logro: m.title }))}"><i style="width:${pct}%"></i></div>
          <div class="ch-nums" style="margin-top:6px"><span>${now}</span><span>${m.complete ? t('Todos los niveles alcanzados') : th('siguiente: {nivel}', { nivel: nxt.label })}</span></div></div>
        <div class="ms-tiers">${m.tiers.map((tier) => tierRow(m, tier)).join('')}</div>
        ${m.complete ? '' : `<a class="btn btn-ghost btn-sm" href="${esc(m.href)}" style="align-self:flex-start">${t('Ve a hacerlo')}</a>`}</article>`;
    };

    const milestones = () => {
      const M = D.milestones, tot = M.totals;
      const shown = M.milestones.filter((m) => mtab === 'all' || m.group === (mtab === 'games' ? 'game' : 'general'));
      const ready = (g) => M.milestones.filter((m) => g === 'all' || m.group === g).reduce((s, m) => s + m.claimable, 0);
      return `<div class="section-head" style="margin-top:46px"><div><span class="kicker">${t('Metas de siempre')}</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">${t('Logros')}</h2>
          <p class="gl-sub">${th('Nunca se reinician. Cada nivel que alcanzas paga una sola vez a tu <span class="acct-tag accum">{cuenta}</span> cuando lo reclamas, y los premios nunca caducan. La actividad vieja solo cuenta donde los registros viejos son confiables.', { cuenta: t('Cuenta acumulada') })}</p></div></div>
        <div class="ms-sum"><span class="tag good">${tp(tot.claimable, '{n} listo para reclamar · {cantidad}', '{n} listos para reclamar · {cantidad}', { cantidad: money(tot.claimableMoney) })}</span><span class="muted">${t('{hechos} de {total} niveles reclamados', { hechos: tot.claimed, total: tot.tiers })}</span>
          <div class="tabs" id="mtabs" style="margin:0 0 0 auto">${[['all', t('Todos')], ['general', t('Generales')], ['games', t('Juegos')]].map(([k, l]) => `<button data-t="${k}" class="${mtab === k ? 'active' : ''}">${esc(l)}${ready(k === 'games' ? 'game' : k) ? ` <span class="num">(${ready(k === 'games' ? 'game' : k)})</span>` : ''}</button>`).join('')}</div></div>
        <div class="ms-grid">${shown.map(milestoneCard).join('')}</div>`;
    };

    const draw = () => {
      root.innerHTML = `<div class="page"><div class="section-head"><div><span class="kicker">${t('Avance a largo plazo')}</span><h1 class="page-title">${t('Rango y logros.')}</h1>
        <p class="gl-sub">${t('Tu rango crece según cuánto participas, a lo largo de semanas y meses. Es <b>aparte del ranking semanal</b> (que es una semana de resultados), no depende de tus fichas y nunca baja.')}</p></div></div>
        ${hero()}${ladder()}${how()}${milestones()}</div>`;
    };
    draw();

    const reload = async () => { try { D = await get('/api/progress'); if (!dead) draw(); } catch { /* keep what is on screen */ } };
    root.addEventListener('click', async (e) => {
      const tb = e.target.closest('#mtabs [data-t]');
      if (tb) { mtab = tb.dataset.t; draw(); return; }
      const b = e.target.closest('[data-claim]'); if (!b || busy) return;
      busy = b.dataset.claim; draw();
      try {
        const r = await post('/api/milestones/claim', { id: busy });
        setUser(r.user);
        toast(r.xp ? t('Reclamaste {cantidad} a tu cuenta acumulada (+{xp} XP).', { cantidad: money(r.amount), xp: r.xp }) : t('Reclamaste {cantidad} a tu cuenta acumulada.', { cantidad: money(r.amount) }), 'ok', { ms: 5000 });
      } catch (ex) { toast(ex.message, 'err'); }
      busy = null; await reload();
    });
    return { onEvent(ev) { if (['inbox'].includes(ev.type)) reload(); }, unmount() { dead = true; } };
  },
};
