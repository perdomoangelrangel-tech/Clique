import { post } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, ICON, catName } from '../util.js';
import { toast } from '../ui.js';
import { loadDraft, saveDraft, clearDraft, guardForm } from '../viewstate.js';
import { t } from '../i18n.js';


const EMOJIS = ['🎲', '🏆', '🎮', '🍕', '💰', '😈', '🎵', '🔥', '⚽', '🏀', '🎬', '🚗', '✈️', '🍻', '💍', '🎓', '🏠', '📱', '🐶', '🌧️'];

export default {
  async mount(root, _p, query) {
    await loadCircles().catch(() => {});
    const hasCircles = S.myCircles.length > 0;
    const f = { scope: !hasCircles || query.get('scope') === 'site' ? 'site' : 'circle',
      circleId: hasCircles ? (query.get('circle') && S.myCircles.find((c) => c.id === query.get('circle')) ? query.get('circle') : S.myCircles[0].id) : '',
      question: '', mode: 'yesno', outcomes: ['', ''], description: '', category: 'General', emoji: '', closes: '' };

    const saved = loadDraft('create');                              // a half-written bet from earlier: put it back (it is only text; nothing is decided until you press the button)
    let restored = false;
    if (saved && typeof saved === 'object') {
      for (const k of ['question', 'description', 'category', 'emoji', 'closes', 'mode']) if (typeof saved[k] === 'string') f[k] = saved[k];
      if (Array.isArray(saved.outcomes)) f.outcomes = saved.outcomes.map(String).slice(0, 12);
      if (saved.scope === 'site' || (saved.scope === 'circle' && hasCircles)) f.scope = saved.scope;
      if (saved.circleId && S.myCircles.find((c) => c.id === saved.circleId)) f.circleId = saved.circleId;
      restored = !!(f.question || f.description || f.outcomes.some((o) => o));
    }
    const dirty = () => !!(f.question.trim() || f.description.trim() || f.outcomes.some((o) => o.trim()));

    const draw = () => {
      root.innerHTML = `<div class="page-narrow" style="max-width:720px">
        <div class="section-head"><div><span class="kicker">${t('Boleto nuevo')}</span><h1 class="page-title">${t('Propón una apuesta.')}</h1></div></div>
        ${restored ? `<div class="notice" style="margin-bottom:14px">${t('Recuperamos la apuesta que dejaste a medias.')} <button type="button" class="linkish" id="drop-draft">${t('Empezar de nuevo')}</button></div>` : ''}
        <form class="card-box pad-lg paper" id="cform" autocomplete="off">
          <div class="field"><label>${t('¿Quién puede apostar?')}</label>
            <div class="seg" style="align-self:flex-start"><button type="button" data-scope="circle" class="${f.scope === 'circle' ? 'active' : ''}" ${hasCircles ? '' : `disabled title="${esc(t('Primero únete a un círculo'))}"`}>${ICON.lock} ${t('Un círculo')}</button><button type="button" data-scope="site" class="${f.scope === 'site' ? 'active' : ''}">${ICON.globe} ${t('Todo el sitio')}</button></div>
            ${f.scope === 'circle'
              ? `<select class="select" id="c-circle" style="margin-top:6px">${S.myCircles.map((c) => `<option value="${c.id}" ${f.circleId === c.id ? 'selected' : ''}>${esc(c.name)} (${c.visibility === 'public' ? t('público') : t('privado')})</option>`).join('')}</select>
                 <small>${t('Solo la gente de este círculo puede verla o apostar.')}</small>`
              : `<small>${hasCircles ? '' : t('Todavía no estás en un círculo, así que esta será pública.') + ' '}${t('Cualquiera con cuenta puede encontrarla y apostar. Tú decides el resultado, y nadie más. Elige una apuesta que puedas resolver con honestidad.')}</small>`}</div>
          <div class="field"><label>${t('¿Cuál es la apuesta?')}</label>
            <input class="input" id="c-q" maxlength="160" placeholder="${esc(t('¿Dani sí va a terminar el maratón?'))}" value="${esc(f.question)}"></div>
          <div class="field"><label>${t('¿Cómo puede terminar?')}</label>
            <div class="seg" style="align-self:flex-start"><button type="button" data-mode="yesno" class="${f.mode === 'yesno' ? 'active' : ''}">${t('Sí / No')}</button><button type="button" data-mode="custom" class="${f.mode === 'custom' ? 'active' : ''}">${t('Ponle nombre a las opciones')}</button></div>
            ${f.mode === 'custom' ? `<div class="stack" style="gap:8px;margin-top:6px">${f.outcomes.map((o, i) => `<div class="row"><input class="input" data-out="${i}" maxlength="40" placeholder="${esc(t('Opción {n}', { n: i + 1 }))}" value="${esc(o)}">
              ${f.outcomes.length > 2 ? `<button type="button" class="icon-btn" data-rm="${i}" title="${esc(t('Quitar'))}" aria-label="${esc(t('Quitar'))}">${ICON.x}</button>` : ''}</div>`).join('')}
              ${f.outcomes.length < 12 ? `<button type="button" class="btn btn-secondary btn-sm" id="add-out" style="align-self:flex-start">${ICON.plus} ${t('Otra opción')}</button>` : ''}</div>
              <small>${t('Gana exactamente una. Con tres o más, se puede apostar a favor o en contra de cada una.')}</small>` : ''}</div>
          <div class="field"><label>${t('Letra chiquita')} <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">${t('(opcional)')}</span></label>
            <textarea class="input" id="c-desc" maxlength="1000" placeholder="${esc(t('¿Quién decide y cómo? Sé específico. Tus amigos van a hacer trampa.'))}">${esc(f.description)}</textarea></div>
          <div class="field"><label>${t('Categoría')}</label><div class="chips">${S.categories.map((c) => `<button type="button" class="pill ${f.category === c ? 'active' : ''}" data-cat="${esc(c)}">${esc(catName(c))}</button>`).join('')}</div></div>
          <div class="field"><label>${t('Tu propio ícono')} <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">${t('(si lo saltas, sale la calcomanía de la categoría)')}</span></label><div class="emoji-pick">${EMOJIS.map((e) => `<button type="button" class="${f.emoji === e ? 'active' : ''}" data-emoji="${e}">${e}</button>`).join('')}</div></div>
          <div class="field"><label>${t('Cierre de apuestas')} <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">${t('(opcional)')}</span></label>
            <div class="row" style="flex-wrap:wrap"><input class="input" id="c-end" type="datetime-local" value="${esc(f.closes)}" style="max-width:240px">
              ${[[t('+1 día'), 1], [t('+1 semana'), 7], [t('+1 mes'), 30]].map(([l, d]) => `<button type="button" class="pill" data-days="${d}">${esc(l)}</button>`).join('')}<button type="button" class="pill" data-days="0">${t('Sin cierre')}</button></div>
            <small>${t('Después de eso nadie puede apostar hasta que decidas el resultado.')}</small></div>
          <div class="error-text" id="c-err" style="min-height:20px"></div>
          <div class="row cform-foot"><a class="btn btn-secondary" href="#/">${t('Cancelar')}</a><button class="btn btn-primary" id="c-go">${t('Imprimir el boleto')}</button></div>
        </form></div>`;
    };
    draw();

    const sync = () => {
      const g = (id) => root.querySelector(id);
      if (g('#c-q')) f.question = g('#c-q').value;
      if (g('#c-desc')) f.description = g('#c-desc').value;
      if (g('#c-end')) f.closes = g('#c-end').value;
      if (g('#c-circle')) f.circleId = g('#c-circle').value;
      root.querySelectorAll('[data-out]').forEach((i) => { f.outcomes[+i.dataset.out] = i.value; });
    };
    root.addEventListener('click', (e) => {
      const btn = e.target.closest('button'); if (!btn) return;
      if (btn.id === 'drop-draft') { clearDraft('create'); Object.assign(f, { question: '', mode: 'yesno', outcomes: ['', ''], description: '', category: 'General', emoji: '', closes: '' }); restored = false; draw(); return; }
      if (btn.dataset.mode) { sync(); f.mode = btn.dataset.mode; draw(); }
      else if (btn.dataset.scope) { sync(); f.scope = btn.dataset.scope; draw(); }
      else if (btn.dataset.cat) { sync(); f.category = btn.dataset.cat; draw(); }
      else if (btn.dataset.emoji) { sync(); f.emoji = f.emoji === btn.dataset.emoji ? '' : btn.dataset.emoji; draw(); }
      else if (btn.dataset.rm) { sync(); f.outcomes.splice(+btn.dataset.rm, 1); draw(); }
      else if (btn.id === 'add-out') { sync(); f.outcomes.push(''); draw(); root.querySelector(`[data-out="${f.outcomes.length - 1}"]`)?.focus(); }
      else if (btn.dataset.days !== undefined) {
        sync(); const d = +btn.dataset.days;
        if (!d) f.closes = ''; else { const x = new Date(Date.now() + d * 86400000); x.setSeconds(0, 0); f.closes = new Date(x - x.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
        draw();
      }
    });
    root.addEventListener('submit', async (e) => {
      e.preventDefault(); sync();
      const err = root.querySelector('#c-err'); err.textContent = '';
      const body = { ...(f.scope === 'site' ? { scope: 'site' } : { circleId: f.circleId }), question: f.question, description: f.description, category: f.category, emoji: f.emoji,
        closesAt: f.closes ? new Date(f.closes).getTime() : null };
      if (f.mode === 'custom') {
        body.outcomes = f.outcomes.map((o) => o.trim()).filter(Boolean);
        if (body.outcomes.length < 2) { err.textContent = t('Necesitas al menos dos opciones. De eso se trata una apuesta.'); return; }
      }
      const btn = root.querySelector('#c-go'); btn.disabled = true;
      try { const d = await post('/api/markets', body); clearDraft('create'); Object.assign(f, { question: '', description: '', outcomes: ['', ''] }); toast(t('Boleto impreso. Ve a contarle a todos.'), 'ok'); go(`#/market/${d.market.id}`); }
      catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
    const keep = () => { sync(); if (dirty()) saveDraft('create', f); else clearDraft('create'); };
    root.addEventListener('input', keep);
    root.addEventListener('click', () => setTimeout(keep, 0));
    return guardForm(dirty, t('Tu apuesta nueva no se ha publicado. ¿Salir sin publicarla? (Lo que escribiste se guarda como borrador de todos modos.)'));
  },
};
