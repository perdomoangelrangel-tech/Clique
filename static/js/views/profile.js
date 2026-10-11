import { get, post, del, api } from '../api.js';
import { S, go, setUser } from '../state.js';
import { esc, detailText, money, moneyFull, num, cents, avatar, ago, dateShort, ICON, circleMark, rankLabel, slipLabel } from '../util.js';
import { awardSticker, rankBadge } from '../art.js';
import { gameName } from '../gamelist.js';
import { bannerCss, setLook, titleHtml } from '../looks.js';
import { productArt, plainAvatar } from '../cosmetics.js';
import { toast, modal } from '../ui.js';
import { guardForm, recall, remember } from '../viewstate.js';
import { emptyState } from './components.js';
import { t, th, tp, LANGS, getLang, setLang } from '../i18n.js';
import { awardName } from '../awards.js';
import { mountSpread } from './spread.js';

const KIND = { buy: ['Compra', '−'], sell: ['Venta', '+'], win: ['Ganancia', '+'], loss: ['Pérdida', ''], refund: ['Devolución', '+'], deposit: ['Fichas agregadas', '+'], game: ['Juego', ''], start: ['Bono de bienvenida', '+'], go: ['Semana nueva', '+'], voucher: ['Vale', '+'], poker: ['Póker', ''], reward: ['Premio semanal', '+'], warn: ['Recordatorio', ''] };      // i18n: claves

export default {
  async mount(root, [name, edit]) {
    const prof = await get(`/api/users/${encodeURIComponent(name)}`);
    const mine = prof.user.username.toLowerCase() === S.user.username.toLowerCase();
    const P = mine ? await get('/api/portfolio') : null;
    const defs = Object.fromEntries(prof.awardDefs.map((a) => [a.key, a]));
    const tot = prof.totals;
    const trophyTotal = Object.values(prof.trophies).reduce((a, b) => a + b, 0);
    const MEM = 'profile:' + prof.user.username.toLowerCase();
    let tab = ['positions', 'closed', 'activity', 'games'].includes(recall(MEM).tab) ? recall(MEM).tab : 'positions';

    const PF = prof.user.profile || { slots: {}, art: {}, bg: 'ink', bio: '', style: {}, upload: null };
    const pfHead = (p, who, can) => {
      const banner = (p.art && p.art.banner) || {};
      const accent = (p.art && p.art.accent && p.art.accent.color) || '#C6F432';
      const bgc = ((prof.user.backgrounds || p.backgrounds || DEFAULT_BGS)[p.bg] || DEFAULT_BGS[p.bg] || DEFAULT_BGS.ink).color;
      const light = p.bg === 'paper';
      const fam = (p.fonts || FONT_STACKS)[(p.art && p.art.font && p.art.font.family) || 'display'] || FONT_STACKS.display;
      const title = (p.art && p.art.title && p.art.title.text) || '';
      const look = p.style || {};
      return `<section class="pf" style="--pf-bg:${bgc};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-mute:${light ? '#5A5246' : '#BDB19C'};--pf-accent:${accent};--pf-font:${fam}">
        <div class="pf-banner" style="${bannerCss(banner)}"></div>
        <div class="pf-main"><div class="pf-av">${plainAvatar(who, 104, look)}</div>
          <div class="pf-id"><h1 class="pf-name">${esc(who)}</h1>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}
            ${prof.rank ? `<div class="pf-rank" title="${esc(t('El rango es tu avance a largo plazo, aparte del ranking semanal'))}">${rankBadge(prof.rank, 30)}<span><b>${esc(rankLabel(prof.rank.label))}</b> · ${num(prof.rank.xp, 0)} XP${mine ? ` · <a href="#/progress">${t('Rango y logros')}</a>` : ''}</span></div>` : ''}
            ${p.bio ? `<p class="pf-bio">${esc(p.bio)}</p>` : ''}
            <div class="pf-meta">${t('Desde el {fecha}', { fecha: dateShort(prof.user.createdAt) })} · ${prof.circles.length ? prof.circles.map((c) => esc(c.name)).join(', ') : t('sin círculos todavía')}</div></div>
          ${can}</div><i class="pf-rule"></i></section>`;
    };
    const DEFAULT_BGS = { ink: { color: '#14110F' }, felt: { color: '#1E3B2C' }, wine: { color: '#3A1A16' }, slate: { color: '#22262B' }, paper: { color: '#EFE6D2' } };
    const FONT_STACKS = { display: "'Bricolage Grotesque', 'Helvetica Neue', Arial, sans-serif", body: "'Instrument Sans', Arial, sans-serif", mono: "'JetBrains Mono', ui-monospace, monospace", serif: "'Fraunces', Georgia, serif", marker: "'Rubik Mono One', 'Arial Black', sans-serif" };
    const editBtn = mine ? `<a class="btn btn-secondary pf-edit" href="#/u/${esc(prof.user.username)}/edit">${ICON.pencil} ${t('Personalizar')}</a>` : '';

    if (mine && edit) return openEditor(root, prof, PF);

    root.innerHTML = `<div class="page">
      ${pfHead(PF, prof.user.username, editBtn)}${''/* html: seguro (pfHead escapa el nombre por dentro) */}
      ${mine ? `<div class="acct-cards" style="margin-top:22px"><div class="card-box pad-lg acct"><span class="lbl">${t('Cuenta semanal')}</span><b class="num" title="${moneyFull(P.balance)}">${money(P.balance)}</b><p class="muted">${t('Las fichas de esta semana. Arrancan otra vez cada lunes.')} <a href="#/portfolio">${t('¿Dónde están?')}</a></p></div>
        <div class="card-box pad-lg acct"><span class="lbl">${t('Cuenta acumulada')}</span><b class="num" title="${moneyFull(prof.accounts.accumulated)}">${money(prof.accounts.accumulated)}</b><p class="muted">${t('Lo que conservas.')} <a href="#/portfolio">${t('Portafolio')}</a> · <a href="#/store">${t('Tienda')}</a> · <a href="#/exchange">${t('Bolsa')}</a> · <a href="#/statement">${t('Estado de cuenta')}</a></p></div></div>` : ''}
      ${mine ? `<div class="card-box pad lang-pick" style="margin-top:16px"><div class="field" style="margin:0"><label for="pf-lang">${t('Idioma de la app')}</label>
        <select class="input" id="pf-lang">${Object.entries(LANGS).map(([code, name]) => `<option value="${code}" ${code === getLang() ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></div></div>` : ''}
      <div class="stats">
        <div class="stat"><small>${t('En el juego semanal')}</small><b title="${moneyFull(prof.netWorth)}">${money(prof.netWorth)}</b></div>
        <div class="stat"><small>${t('Premios ganados')}</small><b>${trophyTotal}</b></div>
        <div class="stat"><small>${t('Apuestas propuestas')}</small><b>${num(tot.marketsCreated || 0, 0)}</b></div>
        <div class="stat"><small>${t('Ganadas / perdidas')}</small><b>${num(tot.betsWon || 0, 0)} / ${num(tot.betsLost || 0, 0)}</b></div>
        <div class="stat"><small>${t('Casino: ganancia o pérdida')}</small><b class="${(tot.gamePnl || 0) >= 0 ? 'up' : 'down'}" title="${moneyFull(tot.gamePnl || 0)}">${money(tot.gamePnl || 0, { plus: true })}</b></div>
      </div>
      ${mine ? '<div id="spread" style="margin-top:28px"></div>' : ''}
      ${mine && prof.rewards && prof.rewards.length ? `<div class="section-head" style="margin-top:44px"><div><span class="kicker">${t('Pagados a tu cuenta acumulada')}</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">${t('Premios semanales')}</h2></div></div>
        <div class="card-box pad">${prof.rewards.slice(0, 12).map((r) => `<div class="list-row"><div class="grow">${th('<b>#{lugar}</b> en {circulo}', { lugar: r.position, circulo: r.circle })} <span class="muted">· ${th('semana del {semana}', { semana: r.week })}</span></div><b class="num up">${money(r.amount, { plus: true })}</b><span class="tag ${r.paid ? 'good' : ''}">${r.paid ? t('pagado') : t('pendiente')}</span></div>`).join('')}</div>` : ''}
      <div class="section-head" style="margin-top:44px"><div><span class="kicker">${t('Trofeos de la semana')}</span><h2 class="page-title" style="font-size:clamp(28px,3.4vw,44px)">${t('Vitrina de trofeos')}</h2></div></div>
      ${trophyTotal ? `<div class="badge-row">${Object.entries(prof.trophies).sort((a, b) => b[1] - a[1]).map(([k, n]) => defs[k] ? `<div class="trophy">${awardSticker(k, 48)}<div><b>${esc(awardName(defs[k]))}</b><small>x${n}</small></div></div>` : '').join('')}</div>
        ${prof.recent.length ? `<details style="margin-top:18px"><summary class="lbl" style="cursor:pointer">${t('Premios recientes')}</summary>
          <div style="margin-top:8px">${prof.recent.map((r) => `<div class="list-row"><span style="line-height:0">${awardSticker(r.key, 32)}</span><div class="grow"><b>${esc(defs[r.key] ? awardName(defs[r.key]) : r.key)}</b> <span class="muted">· ${esc(r.circle)}</span></div><span class="mono muted" style="font-size:12px">${esc(r.value)} · ${th('semana del {semana}', { semana: r.week })}</span></div>`).join('')}</div></details>` : ''}`
        : emptyState({ art: 'shelf', tone: 'cream', tight: true, kicker: t('Repisa vacía'), title: esc(t('No hay nada en la repisa.')), text: esc(t('Los premios se reparten cuando cierra la votación semanal. Ve a ganarte algo. O pierde de manera espectacular. Las dos cuentan.')) })}
      <div id="own"></div></div>`;

    if (!mine) return {};
    root.querySelector('#pf-lang').addEventListener('change', (e) => setLang(e.target.value));      // the whole app repaints in place (app.js)
    mountSpread(root.querySelector('#spread'), P.distribution, { go });
    const own = root.querySelector('#own');
    const draw = () => {
      const tabs = [['positions', t('Boletos abiertos ({n})', { n: P.open.length })], ['closed', t('Resueltos')], ['activity', t('Recibos')], ['games', t('Historial del casino')]];
      own.innerHTML = `<div class="tabs" id="ptabs" style="margin-top:44px">${tabs.map(([k, l]) => `<button data-t="${k}" class="${tab === k ? 'active' : ''}">${esc(l)}</button>`).join('')}</div><div id="pbody"></div>`;
      const body = own.querySelector('#pbody');
      const posTable = (rows, closed) => rows.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>${t('Mercado')}</th><th>${t('Posición')}</th><th class="r">${t('Acciones')}</th><th class="r">${t('Prom.')}</th><th class="r">${closed ? t('Cobró') : t('Valor')}</th><th class="r">${t('Ganancia o pérdida')}</th></tr></thead><tbody>
        ${rows.map((r) => `<tr style="cursor:pointer" data-m="${r.market}"><td style="max-width:340px"><b>${esc(r.question)}</b></td><td><span class="tag ${r.side === 'yes' ? 'good' : 'bad'}">${esc(slipLabel(r.label))}</span></td>
          <td class="r num">${num(r.shares)}</td><td class="r num">${cents(r.avgPrice)}</td><td class="r num">${money(r.value ?? 0)}</td>
          <td class="r num ${(r.pnl || 0) >= 0 ? 'up' : 'down'}">${r.refunded ? t('devuelto') : money(r.pnl || 0, { plus: true })}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: closed ? 'paper' : 'slip', tone: 'cream', tight: true, kicker: closed ? t('Nada resuelto') : t('Sin boletos abiertos'), title: esc(closed ? t('No hay nada que cobrar.') : t('No tienes nada en juego.')), text: esc(closed ? t('Las apuestas resueltas llegan aquí.') : t('Busca una apuesta y respalda lo que dices con fichas.')), actions: closed ? '' : `<a class="btn btn-primary" href="#/">${t('Ver la pizarra')}</a>` });
      if (tab === 'positions') body.innerHTML = `<div class="muted" style="margin-bottom:12px">${th('Tus boletos abiertos valen <b class="num">{cantidad}</b> si los vendieras ahora mismo.', { cantidad: money(P.positionsValue) })}</div>` + posTable(P.open, false);
      else if (tab === 'closed') body.innerHTML = posTable(P.closed, true);
      else if (tab === 'activity') body.innerHTML = P.activity.length ? `<div class="card-box pad">${P.activity.map((a) => {
        const lbl = KIND[a.kind] ? t(KIND[a.kind][0]) : a.kind; const pos = a.amount > 0;
        return `<div class="list-row"><div class="grow"><b>${esc(lbl)}</b> <span class="muted">${esc(a.text)}</span></div><span class="muted">${ago(a.t)}</span><b class="num ${pos ? 'up' : a.amount < 0 ? 'down' : ''}" style="width:110px;text-align:right">${a.amount ? money(a.amount, { plus: true }) : '—'}</b></div>`;
      }).join('')}</div>` : `<p class="quiet">${t('Nada todavía.')}</p>`;
      else body.innerHTML = P.history.length ? `<div class="card-box tbl-wrap"><table class="tbl"><thead><tr><th>${t('Juego')}</th><th class="r">${t('Apuesta')}</th><th class="r">${t('Pago')}</th><th class="r">${t('Multiplicador')}</th><th>${t('Resultado')}</th><th class="r">${t('Cuándo')}</th></tr></thead><tbody>
        ${P.history.map((h) => `<tr><td><b>${esc(gameName(h.game))}</b></td><td class="r num">${money(h.bet)}</td><td class="r num ${h.profit > 0 ? 'up' : h.profit < 0 ? 'down' : ''}">${money(h.payout)}</td><td class="r num">${h.mult ? num(h.mult) + '×' : '—'}</td><td class="muted">${detailText(h.detail)}</td><td class="r muted">${ago(h.t)}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState({ art: 'snake', tone: 'cream', tight: true, kicker: t('Sin apuestas'), title: esc(t('Ojos de serpiente. Nada de nada.')), text: esc(t('No has jugado ni una mano.')), actions: `<a class="btn btn-primary" href="#/games">${t('Abrir el casino')}</a>` });
    };
    draw();
    own.addEventListener('click', (e) => {
      const b = e.target.closest('[data-t]'); if (b) { tab = b.dataset.t; remember(MEM, { tab }); draw(); return; }
      const r = e.target.closest('[data-m]'); if (r) go(`#/market/${r.dataset.m}`);
    });
    return {};
  },
};

// ---------------------------------------------------------------------------------------------------------------------------
// The editor: choose how your profile looks, see it live, then save. Free options are always there; the rest must be owned.
// ---------------------------------------------------------------------------------------------------------------------------
const SLOT_LABEL = { avatar: 'Foto', frame: 'Marco', badge: 'Insignia', title: 'Título', banner: 'Portada', accent: 'Color', font: 'Letra del nombre' };      // i18n: claves
const SLOT_ORDER = ['avatar', 'frame', 'badge', 'title', 'banner', 'accent', 'font'];

async function openEditor(root, prof, startProfile) {
  const [store, mineP] = await Promise.all([get('/api/store'), get('/api/profile')]);
  let P = mineP.profile;                                                        // what is saved
  const sel = { ...P.slots, bg: P.bg, bio: P.bio };                             // what is chosen right now
  let upload = P.upload;                                                        // the saved uploaded picture (a url), if any
  const items = store.items, byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const dirty = () => SLOT_ORDER.some((k) => sel[k] !== P.slots[k]) || sel.bg !== P.bg || sel.bio !== P.bio;
  const guard = guardForm(() => dirty(), t('Los cambios de tu perfil no se han guardado. ¿Salir sin guardar?'));

  const lookOfSel = () => {
    const look = {};
    if (sel.avatar === 'upload' && upload) look.u = upload.split('/').pop();
    else if (byId[sel.avatar] && byId[sel.avatar].art.icon) look.a = { icon: byId[sel.avatar].art.icon, bg: byId[sel.avatar].art.bg };
    const f = byId[sel.frame] && byId[sel.frame].art; if (f && f.style !== 'none') look.f = f;
    const b = byId[sel.badge] && byId[sel.badge].art; if (b && b.glyph) look.b = b.glyph;
    return look;
  };
  const preview = () => {
    const art = {}; for (const k of SLOT_ORDER) art[k] = byId[sel[k]] ? byId[sel[k]].art : {};
    const p = { art, bg: sel.bg, bio: sel.bio, style: lookOfSel(), fonts: store.fonts, backgrounds: P.backgrounds };
    return p;
  };
  const optionHtml = (kind) => {
    const list = items.filter((i) => i.kind === kind).sort((a, b) => (b.free - a.free) || (a.price - b.price));
    const opts = list.map((i) => {
      const usable = i.owned, on = sel[kind] === i.id;
      const note = usable ? (i.free ? t('Gratis') : t('Tuyo')) : i.state === 'locked' ? t('Bloqueado') : t('Tienda · {cantidad}', { cantidad: money(i.price, { noCents: true }) });
      return `<button type="button" class="pick ${on ? 'on' : ''} ${usable ? '' : 'na'}" data-slot="${kind}" data-id="${i.id}" ${usable ? '' : 'data-store="1"'} title="${esc(i.name)}${usable ? '' : ' ' + esc(t('(todavía no es tuyo)'))}" aria-pressed="${on}">
        <span class="pick-art">${productArt(i, { name: S.user.username, size: 40, fonts: store.fonts })}</span><span class="pick-name">${esc(i.name)}</span><span class="pick-note ${usable ? '' : 'buy'}">${esc(note)}</span></button>`;
    });
    if (kind === 'avatar') {
      opts.unshift(`<button type="button" class="pick ${sel.avatar === 'upload' ? 'on' : ''} ${upload ? '' : 'na'}" data-slot="avatar" data-id="upload" ${upload ? '' : 'disabled'} aria-pressed="${sel.avatar === 'upload'}">
        <span class="pick-art">${upload ? plainAvatar(S.user.username, 40, { u: upload.split('/').pop() }) : `<span class="pa-none">${t('ninguna')}</span>`}</span><span class="pick-name">${t('Tu foto')}</span><span class="pick-note">${upload ? t('Gratis') : t('Sube una')}</span></button>`);
    }
    return opts.join('');
  };
  const bgHtml = () => Object.entries(P.backgrounds).map(([id, b]) => `<button type="button" class="pick ${sel.bg === id ? 'on' : ''}" data-bg="${id}" aria-pressed="${sel.bg === id}"><span class="pick-art"><i class="bg-chip" style="background:${b.color}"></i></span><span class="pick-name">${esc(b.name)}</span><span class="pick-note">${t('Gratis')}</span></button>`).join('');

  function paintPreview() {
    const p = preview();
    root.querySelector('#ed-preview').innerHTML = pfPreview(p);
    const mini = root.querySelector('#ed-mini');
    mini.innerHTML = pfMini(p);
    root.querySelector('#ed-save').disabled = !dirty();
    root.querySelector('#bio-n').textContent = String(140 - sel.bio.length);
  }
  /* On a phone the big preview scrolls out of sight while you pick things, so a one-line copy of it stays pinned above the options. */
  const pfMini = (p) => {
    const accent = (p.art.accent && p.art.accent.color) || '#C6F432', light = p.bg === 'paper';
    const fam = store.fonts[(p.art.font && p.art.font.family) || 'display'], title = (p.art.title && p.art.title.text) || '';
    return `<section class="pf pf-mini" style="--pf-bg:${p.backgrounds[p.bg].color};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-accent:${accent};--pf-font:${fam}">
      <span class="pf-av">${plainAvatar(S.user.username, 44, p.style)}</span>
      <span class="pm-id"><b class="pf-name">${esc(S.user.username)}</b>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}</span>
      <button type="button" class="btn btn-primary btn-sm" id="ed-mini-save" ${dirty() ? '' : 'disabled'}>${t('Guardar')}</button><i class="pf-rule"></i></section>`;
  };
  const pfPreview = (p) => {
    const banner = p.art.banner || {}, accent = (p.art.accent && p.art.accent.color) || '#C6F432', light = p.bg === 'paper';
    const bgc = p.backgrounds[p.bg].color, fam = store.fonts[(p.art.font && p.art.font.family) || 'display'];
    const title = (p.art.title && p.art.title.text) || '';
    return `<section class="pf" style="--pf-bg:${bgc};--pf-ink:${light ? '#14110F' : '#F2EADB'};--pf-mute:${light ? '#5A5246' : '#BDB19C'};--pf-accent:${accent};--pf-font:${fam}">
      <div class="pf-banner" style="${bannerCss(banner)}"></div><div class="pf-main"><div class="pf-av">${plainAvatar(S.user.username, 104, p.style)}</div>
      <div class="pf-id"><h1 class="pf-name">${esc(S.user.username)}</h1>${title ? `<span class="pf-title">${esc(title)}</span>` : ''}${p.bio ? `<p class="pf-bio">${esc(p.bio)}</p>` : ''}</div></div><i class="pf-rule"></i></section>`;
  };

  function draw() {
    root.innerHTML = `<div class="page">
      <div class="section-head"><div><span class="kicker">${t('Hazlo tuyo')}</span><h1 class="page-title">${t('Personaliza tu perfil.')}</h1></div>
        <a class="btn btn-ghost" href="#/u/${esc(S.user.username)}" id="ed-back">${ICON.chevL} ${t('Volver a tu perfil')}</a></div>
      <p class="muted" style="max-width:68ch;margin:0 0 6px">${t('Elige lo que te guste y mira cómo cambia la vista previa. No se guarda nada hasta que presiones Guardar. Las opciones <b>Gratis</b> siempre son tuyas, las <b>Tuyas</b> las compraste, y las de <b>Tienda</b> las consigues en la Tienda con tu cuenta acumulada. Solo tu foto, marco e insignia aparecen en las listas del sitio; lo demás vive en tu perfil.')}</p>
      <div class="ed">
        <div class="ed-prev"><div class="lbl" style="margin-bottom:8px">${t('Vista previa')}</div><div id="ed-preview"></div>
          <div class="ed-actions"><button class="btn btn-primary" id="ed-save" disabled>${t('Guardar cambios')}</button><button class="btn btn-secondary" id="ed-reset" title="${esc(t('Regresar todo a lo básico'))}">${icon_('arrow-counter-clockwise')} ${t('Volver a lo básico')}</button></div>
          <p class="muted" id="ed-msg" style="min-height:20px;margin:8px 0 0;font-size:13px" role="status"></p></div>
        <div class="ed-ctl"><div class="ed-mini" id="ed-mini"></div>
          <div class="card-box pad ed-sec"><h3>${t('Foto')}</h3>
            <div class="upl"><label class="btn btn-secondary btn-sm" for="up-file">${icon_('upload-simple')} ${t('Subir una foto')}</label><input type="file" id="up-file" accept="image/png,image/jpeg,image/webp" hidden>
              ${upload ? `<button type="button" class="btn btn-ghost btn-sm" id="up-del">${t('Quitar mi foto')}</button>` : ''}<span class="muted" style="font-size:12.5px">${t('PNG, JPEG o WebP. Primero se recorta y se achica en tu dispositivo; luego el servidor revisa qué hay de verdad dentro del archivo.')}</span></div>
            <div class="picks" id="o-avatar">${optionHtml('avatar')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Marco')}</h3><div class="picks" id="o-frame">${optionHtml('frame')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Insignia')}</h3><div class="picks" id="o-badge">${optionHtml('badge')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Título')}</h3><div class="picks" id="o-title">${optionHtml('title')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Portada')}</h3><div class="picks" id="o-banner">${optionHtml('banner')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Color de acento')}</h3><div class="picks" id="o-accent">${optionHtml('accent')}</div><p class="muted" style="margin:8px 0 0;font-size:12.5px">${t('Algunos colores se leen muy mal en algunos fondos. Clique te lo dirá en vez de guardar un perfil que nadie puede leer.')}</p></div>
          <div class="card-box pad ed-sec"><h3>${t('Fondo del perfil')}</h3><div class="picks" id="o-bg">${bgHtml()}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Letra del nombre')}</h3><div class="picks" id="o-font">${optionHtml('font')}</div></div>
          <div class="card-box pad ed-sec"><h3>${t('Sobre ti')}</h3><textarea class="input" id="ed-bio" rows="3" maxlength="140" placeholder="${esc(t('Una línea sobre ti. Solo texto.'))}">${esc(sel.bio)}</textarea><div class="muted" style="text-align:right;font-size:12px">${th('quedan <span id="bio-n">{n}</span>', { n: 140 - sel.bio.length })}</div></div>
        </div></div></div>`;
    paintPreview();
  }
  const icon_ = (n) => (ICON[n] || '');

  const flash = (text, bad) => { const m = root.querySelector('#ed-msg'); if (m) { m.textContent = text; m.className = bad ? 'error-text' : 'muted'; } };
  const refreshAll = async () => { const [a, b] = await Promise.all([get('/api/profile'), get('/api/store')]); P = a.profile; Object.assign(store, b); items.length = 0; items.push(...b.items); for (const i of items) byId[i.id] = i; upload = P.upload; };

  root.addEventListener('click', async (e) => {
    const o = e.target.closest('.pick');
    if (o) {
      if (o.dataset.store) { toast(t('Eso todavía no es tuyo. Lo puedes conseguir en la Tienda.'), '', { onClick: () => go(`#/store/${byId[o.dataset.id].kind}`), ms: 5000 }); return; }
      if (o.dataset.slot) { sel[o.dataset.slot] = o.dataset.id; }
      else if (o.dataset.bg) { sel.bg = o.dataset.bg; }
      else return;
      const parent = o.parentElement; parent.querySelectorAll('.pick').forEach((x) => { const on = x === o; x.classList.toggle('on', on); x.setAttribute('aria-pressed', String(on)); });
      paintPreview(); flash(''); return;
    }
    const b = e.target.closest('button'); if (!b) return;
    if (b.id === 'ed-mini-save') { root.querySelector('#ed-save').click(); return; }     // the pinned bar's Save is the same Save
    try {
      if (b.id === 'ed-save') {
        b.disabled = true;
        const body = { ...Object.fromEntries(SLOT_ORDER.map((k) => [k, sel[k]])), bg: sel.bg, bio: sel.bio };
        const d = await post('/api/profile', body);
        P = d.profile; sel.bg = P.bg; setLook(S.user.username, P.style); await refreshAll();
        flash(t('Guardado. Así te ven todos ahora.')); paintPreview(); setUser({ ...S.user });
      } else if (b.id === 'ed-reset') {
        const d = await post('/api/profile', { reset: true });
        P = d.profile; Object.assign(sel, P.slots, { bg: P.bg, bio: P.bio }); setLook(S.user.username, P.style); await refreshAll(); draw(); flash(t('De vuelta a lo básico. Todo lo que compraste sigue siendo tuyo.')); setUser({ ...S.user });
      } else if (b.id === 'up-del') {
        const d = await del('/api/profile/avatar'); P = d.profile; setLook(S.user.username, P.style); await refreshAll(); if (sel.avatar === 'upload') sel.avatar = P.slots.avatar; draw(); flash(t('Tu foto ya no está.')); setUser({ ...S.user });
      }
    } catch (ex) { flash(ex.message, true); const s = root.querySelector('#ed-save'); if (s) s.disabled = !dirty(); }
  });
  root.addEventListener('input', (e) => { if (e.target.id === 'ed-bio') { sel.bio = e.target.value; paintPreview(); flash(''); } });
  root.addEventListener('change', async (e) => {
    if (e.target.id !== 'up-file' || !e.target.files[0]) return;
    const file = e.target.files[0];
    flash(t('Revisando tu foto…'));
    try {
      const blob = await squareUp(file);
      const res = await fetch('/api/profile/avatar', { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob, credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || t('No se aceptó esa foto.'));
      P = data.profile; sel.avatar = 'upload'; setLook(S.user.username, P.style); await refreshAll(); draw(); flash(t('Listo. Presiona Guardar para conservar los otros cambios que hiciste.')); setUser({ ...S.user });
    } catch (ex) { flash(ex.message, true); }
    e.target.value = '';
  });
  draw();
  return guard;
}

/** Crops a picture to a square and shrinks it to at most 320 pixels, so the upload is small and fast. The server checks it again. */
async function squareUp(file) {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) throw new Error(t('Elige una foto PNG, JPEG o WebP.'));
  if (file.size > 12 * 1024 * 1024) throw new Error(t('Ese archivo es enorme. Elige una foto más chica.'));
  let bmp;
  try { bmp = await createImageBitmap(file); } catch { throw new Error(t('Ese archivo no se pudo abrir como foto.')); }
  const side = Math.min(bmp.width, bmp.height), out = Math.min(320, side);
  if (side < 64) throw new Error(t('Esa foto es muy chica. Usa una de al menos 64 pixeles de ancho y de alto.'));
  const c = document.createElement('canvas'); c.width = c.height = out;
  c.getContext('2d').drawImage(bmp, (bmp.width - side) / 2, (bmp.height - side) / 2, side, side, 0, 0, out, out);
  const pick = (type, q) => new Promise((r) => c.toBlob((b) => r(b && b.type === type ? b : null), type, q));
  return (await pick('image/webp', 0.88)) || (await pick('image/png')) || (() => { throw new Error(t('Tu navegador no pudo preparar esa foto.')); })();
}
