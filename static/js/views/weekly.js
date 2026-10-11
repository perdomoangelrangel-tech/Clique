import { get, post, del } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, money, avatar, ICON, until, ago, dateLong, dateShort } from '../util.js';
import { titleHtml } from '../looks.js';
import { recall, remember } from '../viewstate.js';
import { toast, confirmBox } from '../ui.js';
import { sticker, awardSticker, rankTag } from '../art.js';
import { emptyState } from './components.js';
import { t, th, tp, getLang } from '../i18n.js';
import { awardName, awardDesc } from '../awards.js';

export default {
  async mount(root, [cid]) {
    await loadCircles().catch(() => {});
    if (!S.myCircles.length) {
      root.innerHTML = `<div class="page">${emptyState({ art: 'scale', tone: 'cream', kicker: t('Sin círculo'), title: esc(t('Sin círculo no hay drama semanal.')), text: esc(t('Únete a un círculo o crea uno, y cada semana alguien se lleva un castigo. Puedes ser tú.')), actions: `<a class="btn btn-primary" href="#/circles">${ICON.users} ${t('Busca un círculo')}</a>` })}</div>`;
      return;
    }
    let last = null; try { last = localStorage.getItem('clique-weekly-circle'); } catch { /* ignore */ }
    const circleId = cid || (S.myCircles.find((c) => c.id === last) || S.myCircles[0]).id;
    if (!cid) { location.replace(`#/weekly/${circleId}`); return; }
    try { localStorage.setItem('clique-weekly-circle', circleId); } catch { /* ignore */ }

    let rulesOpen = !!recall('weekly-rules').open;                          // the page redraws itself when things happen; it must not close what you were reading
    const MEM = 'weekly:' + circleId;
    let week = recall(MEM).week || '', D = null, dead = false;
    const load = async () => {
      D = await get(`/api/circles/${circleId}/weekly${week ? `?week=${week}` : ''}`);
      if (dead) return; draw();
    };
    const defs = () => Object.fromEntries(D.awardDefs.map((a) => [a.key, a]));
    const DAY = 86400000;
    const wkLabel = () => { const a = new Date(D.week + 'T12:00:00').getTime(); return `${dateShort(a)} – ${dateShort(a + 6 * DAY)}`; };      // (the server's D.label is in English)

    function hotSeat() {
      const rows = D.standings;
      const lead = D.poll[0];
      const risky = D.isCurrent ? rows.filter((r) => r.req && r.req.atRisk) : [];
      const riskNames = risky.slice(0, 6).map((r) => r.user.username).join(', ');
      const riskLine = risky.length ? `<div class="hs-risk">${risky.length > 6 ? th('También pierden la semana si no cumplen el mínimo semanal: {nombres} y {n} más.', { nombres: riskNames, n: risky.length - 6 }) : th('También pierden la semana si no cumplen el mínimo semanal: {nombres}.', { nombres: riskNames })}</div>` : '';
      if (D.isCurrent) {
        if (!D.hotSeat.length) return `<div class="hotseat safe"><span class="lbl">${t('Esta semana')}</span>${sticker('scale', { size: 64, bg: 'cream', rot: 6 })}<div class="who"><b>${t('Nadie va perdiendo todavía.')}</b></div>
          <div class="pun">${t('Todos van parejos. Hagan apuestas para que alguien pase vergüenza. Quien tenga la peor semana se lleva el castigo.')}</div>${riskLine}</div>`;
        const names = D.hotSeat.map((u) => esc(u.username)).join(' &amp; ');
        const val = rows.find((r) => r.user.id === D.hotSeat[0].id);
        return `<div class="hotseat"><span class="lbl">${t('En la silla caliente')}</span>${sticker('flame', { size: 64, bg: 'cream', rot: 6 })}
          <div class="who">${D.hotSeat.slice(0, 3).map((u) => avatar(u.username, 56)).join('')}<div><b>${names}</b>${''/* html: seguro (names se escapó al armarlo) */}<div class="val">${val ? t('{cantidad} esta semana · la peor semana', { cantidad: money(val.delta, { plus: true }) }) : ''}</div></div></div>
          <div class="pun">${lead ? tp(lead.votes, 'Castigo que va ganando: <b>{castigo}</b> ({n} voto)', 'Castigo que va ganando: <b>{castigo}</b> ({n} votos)', { castigo: esc(lead.text) }) : t('Nadie ha propuesto un castigo. Sean creativos. Crueles, pero justos.')}</div>${riskLine}</div>`;
      }
      const r = D.recap;
      if (!r || !D.hotSeat.length) return `<div class="hotseat safe"><span class="lbl">${t('El veredicto')}</span>${sticker('scale', { size: 64, bg: 'cream', rot: 6 })}<div class="who"><b>${t('Nadie paga.')}</b></div><div class="pun">${esc(r?.note || t('No quedó nada registrado esta semana.'))}</div></div>`;
      return `<div class="hotseat"><span class="lbl">${t('El veredicto')}</span>${sticker('paper', { size: 64, bg: 'cream', rot: 6 })}
        <div class="who">${D.hotSeat.slice(0, 3).map((u) => avatar(u.username, 56)).join('')}<div><b>${D.hotSeat.map((u) => esc(u.username)).join(' &amp; ')}</b><div class="val">${r.reason === 'minimum' ? t('no cumplió el mínimo semanal') : t('quedó último')}</div></div></div>
        <div class="pun">${r.punishment ? `${th('Castigo: <b>{castigo}</b>', { castigo: r.punishment.text })}${r.note ? `<div style="color:#BDB19C;font-weight:400;margin-top:4px;font-size:13px">${esc(r.note)}</div>` : ''}` : esc(r.note)}</div>
        ${r.punishment ? `<div class="row" style="margin-top:14px">${r.served ? `<span class="tag" style="background:#0E0C0A;border-color:#0E0C0A;color:var(--lime)">${t('Cumplido')}</span>` : `<span class="tag" style="background:#0E0C0A;border-color:#0E0C0A;color:#F2EADB">${t('Pendiente')}</span>`}
          ${D.canMarkServed ? `<button class="btn btn-sm" id="served">${r.served ? t('Deshacer') : t('Ya lo cumplió')}</button>` : ''}</div>` : ''}</div>`;
    }

    function poll() {
      const max = Math.max(1, ...D.poll.map((p) => p.votes));
      const winnerId = !D.isCurrent && D.recap?.punishment?.id;
      return `<div class="card-box pad-lg"><div class="section-head" style="margin-bottom:4px"><h3 style="font-size:30px;letter-spacing:-.045em">${t('La votación del castigo')}</h3>
          <span class="kicker">${D.isCurrent ? t('Propón uno. Vota por uno.') : t('Votación cerrada')}</span></div>
        <p class="muted" style="margin:0 0 16px">${t('Quien tenga la peor semana (la caída más grande o la ganancia más chica) cumple el castigo ganador, y también quien no cumpla el mínimo semanal.')}</p>
        ${D.isCurrent ? `<form id="pform" class="row" style="margin-bottom:16px"><input class="input" id="ptext" maxlength="120" placeholder="${esc(t('Cantar en el súper. Ponerse el disfraz de pollo.'))}"><button class="btn btn-primary">${t('Agregar')}</button></form>` : ''}
        <div class="stack" style="gap:12px">${D.poll.length ? D.poll.map((p) => `
          <div class="pun-item paper ${p.voted ? 'voted' : ''}" ${D.isCurrent ? `data-vote="${p.id}"` : ''} style="${winnerId === p.id ? 'box-shadow:4px 4px 0 var(--verm-shadow);' : ''}">
            <div class="bar" style="width:${(p.votes / max) * 100}%"></div>
            <span class="votebtn">${ICON.check}</span>
            <div class="grow"><div style="font-weight:600;line-height:1.2">${esc(p.text)} ${winnerId === p.id ? `<span class="tag bad">${t('Ganó')}</span>` : ''}</div>
              <div class="mono muted" style="font-size:11px;margin-top:3px;letter-spacing:.03em;text-transform:uppercase">${esc(p.author.username)}${p.voters.length ? ` · ${p.voters.map(esc).join(', ')}` : ''}</div></div>
            <b class="num" style="font-size:22px">${p.votes}</b>
            ${D.isCurrent ? `<button class="icon-btn" data-delp="${p.id}" title="${esc(t('Quitar'))}" aria-label="${esc(t('Quitar'))}">${ICON.x}</button>` : ''}</div>`).join('')
          : `<p class="quiet">${D.isCurrent ? t('Sin propuestas. Sean creativos. Crueles, pero justos.') : t('Nadie propuso castigo esta semana. Qué suerte.')}</p>`}</div></div>`;
    }

    const wkDate = (key) => dateShort(new Date(key + 'T12:00:00').getTime());
    /** The weekly minimum: bet in a poll and play the casino, or lose the week. Shown as progress, and as the result once the week is settled. */
    function minimum() {
      const R = D.rules.requirements, req = D.me && D.me.req;
      if (!R || !req || !(R.polls || R.casino)) return '';
      const bar = (label, have, need) => need ? `<div class="req-row ${have >= need ? 'done' : ''}"><div class="req-top"><span>${esc(label)}</span><b class="num">${Math.min(have, need)} / ${need}</b></div>
          <div class="req-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${need}" aria-valuenow="${Math.min(have, need)}" aria-label="${esc(label)}"><i style="width:${Math.min(100, (have / need) * 100)}%"></i></div></div>` : '';
      const cur = D.isCurrent;
      let note, tone = '';
      if (req.exempt) note = t('Entraste esta semana, así que el mínimo empieza para ti la próxima.');
      else if (!req.enforced) note = t('El mínimo empieza la semana del {fecha}. Mientras tanto, esto es solo una vista previa.', { fecha: wkDate(R.from) });
      else if (cur) { note = req.met ? t('Ya cumpliste el mínimo. No necesitas nada más esta semana.') : t('Si te falta cualquiera de los dos cuando cierre la semana, la pierdes: te toca el castigo y no ganas premio.'); tone = req.met ? 'ok' : 'warn'; }
      else { note = D.me.out ? t('No cumpliste el mínimo, así que perdiste esta semana: castigo y sin premio.') : t('Cumpliste el mínimo.'); tone = D.me.out ? 'warn' : 'ok'; }
      return `<div class="req ${tone}"><div class="lbl">${t('El mínimo semanal')}</div>
        ${bar(tp(R.polls, '{n} apuesta en mercados', '{n} apuestas en mercados'), req.polls.have, R.polls)}${bar(tp(R.casino, '{n} apuesta en el casino', '{n} apuestas en el casino'), req.casino.have, R.casino)}
        <p>${esc(note)}</p></div>`;
    }
    const place = (n) => (getLang() === 'en' ? `${n}${[, 'st', 'nd', 'rd'][(n % 100 >> 3) ^ 1 && n % 10] || 'th'}` : `${n}.º`);
    function ruleLines() {
      const R = D.rules, pay = R.rewards.map((v, i) => `${place(i + 1)} ${money(v, { noCents: true })}`).join(', ');
      const scale = [2, 3, 4, R.fullAt].map((n) => t('{n} activos = {pct}%', { n: `${n}${n === R.fullAt ? '+' : ''}`, pct: Math.round(Math.min(1, (n - 1) / (R.fullAt - 1)) * 100) })).join(', ');
      const RQ = D.rules.requirements;
      return [
        t('<b>Cómo se ordena.</b> Rendimiento semanal = lo que tienes ahora (la cuenta semanal más lo que está en juego: apuestas abiertas a su valor de venta y rondas sin terminar) menos lo que tenías al empezar la semana, menos lo que te dieron (la recarga semanal, recargas y vales). Cuentan las ganancias y las pérdidas. La cuenta acumulada, la Tienda y la Bolsa no cuentan.'),
        ...(RQ && (RQ.polls || RQ.casino) ? [
          t('<b>El mínimo semanal.</b> Para seguir en el reto tienes que apostar en al menos {mercados} y jugar al menos {rondas} durante la semana. Si al cerrar la semana te falta cualquiera de los dos, <b>pierdes la semana automáticamente</b>: te toca el castigo de la semana (en lugar de quien quedó último, así que pueden ser varios) y no ganas premio, sin importar tu resultado. Las rondas de práctica no cuentan, una ronda cuenta cuando termina, y una cuenta creada durante la semana está exenta esa primera semana.', { mercados: tp(RQ.polls, '{n} mercado', '{n} mercados'), rondas: tp(RQ.casino, '{n} ronda de casino', '{n} rondas de casino') })
            + (RQ.from && RQ.from > D.week && D.isCurrent ? ' ' + t('Empieza la semana del {fecha}.', { fecha: wkDate(RQ.from) }) : '')] : []),
        t('<b>Empates.</b> Primero el mayor rendimiento, luego quien tenga más al final, luego la cuenta más antigua y luego el número de cuenta. Nadie se ordena al azar.'),
        th('<b>Cuándo corre la semana.</b> De lunes 00:00 al siguiente lunes 00:00, {zona} (la semana termina al dar la medianoche del domingo).', { zona: D.timezone }),
        t('<b>Los premios</b> llegan a tu cuenta <b>acumulada</b> cuando cierra la semana: {pagos}; los demás que jugaron ganan {participacion}.', { pagos: pay, participacion: money(R.participation, { noCents: true }) }),
        tp(R.minMoves, '<b>Para ganar uno</b> necesitas al menos {n} apuesta o ronda de casino esta semana (las de práctica no cuentan). Los miembros inactivos aparecen pero no ocupan lugar. Un círculo necesita {activos} miembros activos; los más chicos cobran a escala ({escala}).', '<b>Para ganar uno</b> necesitas al menos {n} apuestas o rondas de casino esta semana (las de práctica no cuentan). Los miembros inactivos aparecen pero no ocupan lugar. Un círculo necesita {activos} miembros activos; los más chicos cobran a escala ({escala}).', { activos: R.minActive, escala: scale }),
        tp(R.maxPerUser, '<b>¿Varios círculos?</b> Solo cobras tu mejor lugar ({n} premio por semana).', '<b>¿Varios círculos?</b> Solo cobras tus mejores lugares ({n} premios por semana).'),
        (R.mode === 'reset' ? t('<b>Tu cuenta semanal</b> se pone en {cantidad} al empezar cada semana; lo que sobra no se acumula.', { cantidad: money(R.allocation, { noCents: true }) }) : t('<b>Tu cuenta semanal</b> recibe {cantidad} al empezar cada semana.', { cantidad: money(R.allocation, { noCents: true }) }))
          + ' ' + t('Las apuestas que sigas teniendo al cerrar la semana siguen siendo tuyas y cuentan con su valor en la siguiente.'),
      ];
    }
    function yourWeek() {
      const me = D.me, cur = D.isCurrent;
      let head;
      if (!me) head = `<p class="muted" style="margin:6px 0 0">${D.standings.length ? t('No estabas en este círculo esa semana.') : t('No hay nada que ordenar esta semana.')}</p>`;
      else {
        const rewardTxt = me.reward > 0
          ? `<b class="num up">${money(me.reward, { plus: true })}</b><small>${cur ? (me.req && me.req.atRisk ? t('estimado, solo si cumples el mínimo semanal') : t('estimado, si la semana terminara ahora')) : me.paid ? t('pagado a tu cuenta acumulada') : t('decidido')}</small>`
          : `<b class="num">${money(0)}</b><small>${esc(me.note || (cur ? t('nada ganado por ahora') : t('sin premio')))}</small>`;
        head = `<div class="yw-stats">
          <div class="stat"><small>${cur ? t('Lugar ahora mismo') : t('Lugar final')}</small><b>${me.position}<span class="muted" style="font-size:.55em"> ${t('de {total}', { total: me.of })}</span></b></div>
          <div class="stat"><small>${t('Rendimiento semanal')}</small><b class="num ${me.delta >= 0 ? 'up' : 'down'}">${money(me.delta, { plus: true })}</b><small>${tp(me.moves, '{n} apuesta o ronda hasta ahora', '{n} apuestas y rondas hasta ahora')}</small></div>
          <div class="stat"><small>${t('Premio')}</small>${rewardTxt}</div></div>`;
      }
      const sc = D.scale ?? 0;
      return `<div class="card-box pad-lg yw"><div class="section-head" style="margin-bottom:6px"><h3 style="font-size:30px;letter-spacing:-.045em">${t('Tu semana')}</h3>
          <span class="kicker">${cur ? th('cierra en <span id="w-left">{tiempo}</span>', { tiempo: until(D.end) }) : t('resuelta {cuando}', { cuando: D.recap ? ago(D.recap.finalizedAt) : '' })}</span></div>
        ${head}
        ${minimum()}
        ${D.activeCount !== undefined ? `<p class="muted" style="margin:14px 0 0;font-size:14px">${cur ? tp(D.activeCount, '{n} miembro activo en este círculo hasta ahora.', '{n} miembros activos en este círculo hasta ahora.') : tp(D.activeCount, '{n} miembro activo en este círculo esa semana.', '{n} miembros activos en este círculo esa semana.')} ${sc >= 1 ? t('Los premios se pagan completos.') : sc > 0 ? t('Los premios se pagan al {pct}% (círculo chico).', { pct: Math.round(sc * 100) }) : t('No se pagan premios si no hay {n} miembros activos.', { n: D.rules.minActive })}</p>` : ''}
        <details style="margin-top:14px" ${rulesOpen ? 'open' : ''}><summary class="lbl" style="cursor:pointer">${t('Las reglas completas')}</summary>
          <ul class="rules">${ruleLines().map((l) => `<li>${l}</li>`).join('')}</ul></details></div>`;
    }

    const missingOf = (req) => [req.polls.have < req.polls.need ? tp(req.polls.need - req.polls.have, '{n} apuesta más en mercados', '{n} apuestas más en mercados') : '',
      req.casino.have < req.casino.need ? tp(req.casino.need - req.casino.have, '{n} apuesta más en el casino', '{n} apuestas más en el casino') : ''].filter(Boolean).join(t(' y '));
    function standings() {
      const rows = D.standings;
      return `<div class="card-box"><div class="pad" style="padding-bottom:8px"><b style="font-family:var(--f-display);font-size:26px;letter-spacing:-.04em">${t('Posiciones')}</b> <span class="kicker" style="margin-left:6px">${D.provisional ? t('en vivo · rendimiento semanal') : t('final · rendimiento semanal')}</span></div>
        ${rows.length ? rows.map((r, i) => `<div class="standing ${D.hotSeat.some((h) => h.id === r.user.id) ? 'last' : ''} ${S.user && r.user.id === S.user.id ? 'me' : ''}"><span class="rk">${r.position || i + 1}</span>${avatar(r.user.username, 36)}
          <div class="grow"><a href="#/u/${esc(r.user.username)}" style="font-weight:600">${esc(r.user.username)}</a>${rankTag(r.user.rank)}${i === 0 && rows.length > 1 && r.delta > rows[rows.length - 1].delta ? ` <span class="up" title="${esc(t('La mejor semana'))}">${ICON.crown}</span>` : ''}${D.hotSeat.some((h) => h.id === r.user.id) ? ` <span class="down" title="${esc(t('Silla caliente'))}">${ICON.flame}</span>` : ''}${titleHtml(r.user.username)}
 ${r.out ? `<span class="tag bad" title="${esc(r.rewardNote)}">${t('perdió la semana')}</span>` : r.req && r.req.atRisk && D.isCurrent ? `<span class="tag warnish" title="${esc(t('Le falta {cosas} antes de que cierre la semana, o la pierde', { cosas: missingOf(r.req) }))}">${t('en riesgo')}</span>` : ''}
            ${r.reward > 0 ? `<span class="tag good" title="${esc(D.provisional ? t('Premio estimado: se paga a la cuenta acumulada al cerrar la semana, si se cumple el mínimo semanal') : r.rewardPaid ? t('Pagado a la cuenta acumulada') : t('Premio'))}">${money(r.reward, { plus: true, noCents: true })}</span>` : r.rewardNote && !r.out ? `<span class="muted rw-note" title="${esc(r.rewardNote)}">${r.active ? t('sin premio') : t('inactivo')}</span>` : ''}</div>
          <div style="text-align:right"><b class="num ${r.delta >= 0 ? 'up' : 'down'}">${money(r.delta, { plus: true })}</b><div class="num muted" style="font-size:12.5px">${t('tiene {cantidad}', { cantidad: money(r.value) })}</div></div></div>`).join('')
          : `<p class="quiet pad">${t('No hay números esta semana.')}</p>`}</div>`;
    }

    function awards() {
      const df = defs();
      const names = Object.fromEntries(D.standings.map((r) => [r.user.id, r.user]));
      const won = new Set(D.awards.map((a) => a.key));
      const cards = D.awards.map((a, i) => {
        const def = df[a.key]; if (!def) return '';
        const tone = a.key === 'topDog' ? 'gold' : a.key === 'hotSeat' ? 'fire' : '';
        return `<div class="award paper ${tone}" style="animation-delay:${i * 45}ms">${awardSticker(a.key, 58)}<h5>${esc(awardName(def))}</h5><p>${esc(awardDesc(def))}</p>
          <div class="win">${a.userIds.map((id) => names[id] ? `${avatar(names[id].username, 26)}<a href="#/u/${esc(names[id].username)}">${esc(names[id].username)}</a>` : '').join('')}</div>
          <div class="val">${esc(a.value)}</div></div>`;
      }).join('');
      const open = D.isCurrent ? D.awardDefs.filter((d) => !won.has(d.key)) : [];
      return `<div class="section-head" style="margin-top:50px"><div><span class="kicker">${D.provisional ? t('No es final hasta que cierre la semana') : t('Final')}</span><h2 class="page-title" style="font-size:clamp(30px,3.6vw,48px)">${D.isCurrent ? t('La carrera por los premios') : t('Los premios')}</h2></div></div>
        ${cards ? `<div class="awards">${cards}</div>` : `<p class="quiet">${t('Todavía no hay premios. Hagan algo memorable.')}</p>`}
        ${open.length ? `<details style="margin-top:26px"><summary class="lbl" style="cursor:pointer;padding:6px 0">${tp(open.length, '{n} premio que nadie ha ganado todavía', '{n} premios que nadie ha ganado todavía')}</summary>
          <div class="badge-row" style="margin-top:14px">${open.map((d) => `<div class="trophy" style="opacity:.62"><span style="filter:grayscale(1)">${awardSticker(d.key, 40)}</span><div><b>${esc(awardName(d))}</b><small>${esc(awardDesc(d))}</small></div></div>`).join('')}</div></details>` : ''}`;
    }

    function draw() {
      const list = [...new Set([S.week || D.week, ...D.weeks])].sort().reverse();
      const idx = list.indexOf(D.week);
      root.innerHTML = `<div class="page">
        <div class="section-head">
          <div><span class="kicker">${t('Alguien va a pagar por esto')}</span><h1 class="page-title">${t('La semana.')}</h1></div>
          <div class="row" style="flex-wrap:wrap;gap:14px">
            <select class="select" id="w-circle" style="height:38px" aria-label="${esc(t('Círculo'))}">${S.myCircles.map((c) => `<option value="${c.id}" ${c.id === circleId ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select>
            <div class="row">
              <button class="icon-btn" id="w-prev" aria-label="${esc(t('Semana anterior'))}" ${idx >= list.length - 1 ? 'disabled style="opacity:.3"' : ''}>${ICON.chevL}</button>
              <div style="text-align:center;min-width:176px"><b class="mono" style="font-size:13px;letter-spacing:.03em;text-transform:uppercase">${esc(wkLabel())}</b>
                <div class="kicker">${D.isCurrent ? t('cierra en {tiempo}', { tiempo: until(D.end) }) : t('resuelta')}</div></div>
              <button class="icon-btn" id="w-next" aria-label="${esc(t('Semana siguiente'))}" ${idx <= 0 ? 'disabled style="opacity:.3"' : ''}>${ICON.chevR}</button></div></div></div>
        <div class="wk"><div class="stack">${yourWeek()}${hotSeat()}${poll()}</div><div class="stack">${standings()}</div></div>
        ${awards()}</div>`;
      root.querySelector('#w-circle').addEventListener('change', (e) => go(`#/weekly/${e.target.value}`));
      root.querySelector('#w-prev').addEventListener('click', () => { if (idx < list.length - 1) { week = list[idx + 1]; remember(MEM, { week }); load(); } });
      root.querySelector('#w-next').addEventListener('click', () => { if (idx > 0) { week = list[idx - 1]; remember(MEM, { week }); load(); } });
    }

    root.addEventListener('toggle', (e) => { if (e.target.matches && e.target.matches('.yw details')) { rulesOpen = e.target.open; remember('weekly-rules', { open: rulesOpen }); } }, true);
    root.addEventListener('click', async (e) => {
      try {
        const del1 = e.target.closest('[data-delp]');
        if (del1) { e.stopPropagation(); if (await confirmBox({ title: t('¿Quitar este castigo?'), text: t('Sus votos se van con él.'), confirm: t('Quitarlo'), danger: true })) { await del(`/api/circles/${circleId}/punishments/${del1.dataset.delp}`); load(); } return; }
        const v = e.target.closest('[data-vote]');
        if (v) { await post(`/api/circles/${circleId}/punishments/${v.dataset.vote}/vote`, {}); load(); return; }
        if (e.target.id === 'served') { await post(`/api/circles/${circleId}/recaps/${D.week}/served`, {}); load(); }
      } catch (ex) { toast(ex.message, 'err'); }
    });
    root.addEventListener('submit', async (e) => {
      if (e.target.id !== 'pform') return; e.preventDefault();
      const input = root.querySelector('#ptext');
      try { await post(`/api/circles/${circleId}/punishments`, { text: input.value }); toast(t('Agregado. Cuenta como tu voto.'), 'ok'); load(); } catch (ex) { toast(ex.message, 'err'); }
    });
    await load();
    const clock = setInterval(() => { const el = root.querySelector('#w-left'); if (el && D) el.textContent = until(D.end); }, 15000);
    return { onEvent(ev) { if (ev.type === 'week' || ev.type === 'reward' || (ev.type === 'weekly' && ev.circleId === circleId) || ev.type === 'market') load().catch(() => {}); }, unmount() { dead = true; clearInterval(clock); } };
  },
};
