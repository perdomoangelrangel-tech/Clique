import { post } from '../api.js';
import { S, go, loadCircles } from '../state.js';
import { esc, ICON } from '../util.js';
import { toast } from '../ui.js';
import { loadDraft, saveDraft, clearDraft, guardForm } from '../viewstate.js';


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
        <div class="section-head"><div><span class="kicker">New slip</span><h1 class="page-title">Propose a bet.</h1></div></div>
        ${restored ? '<div class="notice" style="margin-bottom:14px">Your unfinished bet from earlier was put back. <button type="button" class="linkish" id="drop-draft">Start over</button></div>' : ''}
        <form class="card-box pad-lg paper" id="cform" autocomplete="off">
          <div class="field"><label>Who can bet on it?</label>
            <div class="seg" style="align-self:flex-start"><button type="button" data-scope="circle" class="${f.scope === 'circle' ? 'active' : ''}" ${hasCircles ? '' : 'disabled title="Join a circle first"'}>${ICON.lock} One circle</button><button type="button" data-scope="site" class="${f.scope === 'site' ? 'active' : ''}">${ICON.globe} Everyone on the site</button></div>
            ${f.scope === 'circle'
              ? `<select class="select" id="c-circle" style="margin-top:6px">${S.myCircles.map((c) => `<option value="${c.id}" ${f.circleId === c.id ? 'selected' : ''}>${esc(c.name)} (${c.visibility})</option>`).join('')}</select>
                 <small>Only people in this circle can see it or bet on it.</small>`
              : `<small>${hasCircles ? '' : 'You are not in a circle yet, so this one goes public. '}Anyone with an account can find it and bet. You call it, and nobody else can. Pick a bet you can settle honestly.</small>`}</div>
          <div class="field"><label>What's the bet?</label>
            <input class="input" id="c-q" maxlength="160" placeholder="Will Dani actually finish the marathon?" value="${esc(f.question)}"></div>
          <div class="field"><label>How can it end?</label>
            <div class="seg" style="align-self:flex-start"><button type="button" data-mode="yesno" class="${f.mode === 'yesno' ? 'active' : ''}">Yes / No</button><button type="button" data-mode="custom" class="${f.mode === 'custom' ? 'active' : ''}">Name the outcomes</button></div>
            ${f.mode === 'custom' ? `<div class="stack" style="gap:8px;margin-top:6px">${f.outcomes.map((o, i) => `<div class="row"><input class="input" data-out="${i}" maxlength="40" placeholder="Outcome ${i + 1}" value="${esc(o)}">
              ${f.outcomes.length > 2 ? `<button type="button" class="icon-btn" data-rm="${i}" title="Remove" aria-label="Remove">${ICON.x}</button>` : ''}</div>`).join('')}
              ${f.outcomes.length < 12 ? `<button type="button" class="btn btn-secondary btn-sm" id="add-out" style="align-self:flex-start">${ICON.plus} Another outcome</button>` : ''}</div>
              <small>Exactly one wins. With three or more, people can back or fade each one.</small>` : ''}</div>
          <div class="field"><label>Fine print <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">(optional)</span></label>
            <textarea class="input" id="c-desc" maxlength="1000" placeholder="Who calls it, and how? Be specific. Your friends will cheat.">${esc(f.description)}</textarea></div>
          <div class="field"><label>Category</label><div class="chips">${S.categories.map((c) => `<button type="button" class="pill ${f.category === c ? 'active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('')}</div></div>
          <div class="field"><label>Your own icon <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">(skip it and you get the sticker for the category)</span></label><div class="emoji-pick">${EMOJIS.map((e) => `<button type="button" class="${f.emoji === e ? 'active' : ''}" data-emoji="${e}">${e}</button>`).join('')}</div></div>
          <div class="field"><label>Betting closes <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">(optional)</span></label>
            <div class="row" style="flex-wrap:wrap"><input class="input" id="c-end" type="datetime-local" value="${esc(f.closes)}" style="max-width:240px">
              ${[['+1 day', 1], ['+1 week', 7], ['+1 month', 30]].map(([l, d]) => `<button type="button" class="pill" data-days="${d}">${l}</button>`).join('')}<button type="button" class="pill" data-days="0">No end</button></div>
            <small>After that, nobody can bet until you call it.</small></div>
          <div class="error-text" id="c-err" style="min-height:20px"></div>
          <div class="row cform-foot"><a class="btn btn-secondary" href="#/">Cancel</a><button class="btn btn-primary" id="c-go">Print the slip</button></div>
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
      const t = e.target.closest('button'); if (!t) return;
      if (t.id === 'drop-draft') { clearDraft('create'); Object.assign(f, { question: '', mode: 'yesno', outcomes: ['', ''], description: '', category: 'General', emoji: '', closes: '' }); restored = false; draw(); return; }
      if (t.dataset.mode) { sync(); f.mode = t.dataset.mode; draw(); }
      else if (t.dataset.scope) { sync(); f.scope = t.dataset.scope; draw(); }
      else if (t.dataset.cat) { sync(); f.category = t.dataset.cat; draw(); }
      else if (t.dataset.emoji) { sync(); f.emoji = f.emoji === t.dataset.emoji ? '' : t.dataset.emoji; draw(); }
      else if (t.dataset.rm) { sync(); f.outcomes.splice(+t.dataset.rm, 1); draw(); }
      else if (t.id === 'add-out') { sync(); f.outcomes.push(''); draw(); root.querySelector(`[data-out="${f.outcomes.length - 1}"]`)?.focus(); }
      else if (t.dataset.days !== undefined) {
        sync(); const d = +t.dataset.days;
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
        if (body.outcomes.length < 2) { err.textContent = 'You need at least two outcomes. That is the whole point of a bet.'; return; }
      }
      const btn = root.querySelector('#c-go'); btn.disabled = true;
      try { const d = await post('/api/markets', body); clearDraft('create'); Object.assign(f, { question: '', description: '', outcomes: ['', ''] }); toast('Slip printed. Go tell everyone.', 'ok'); go(`#/market/${d.market.id}`); }
      catch (ex) { err.textContent = ex.message; btn.disabled = false; }
    });
    const keep = () => { sync(); if (dirty()) saveDraft('create', f); else clearDraft('create'); };
    root.addEventListener('input', keep);
    root.addEventListener('click', () => setTimeout(keep, 0));
    return guardForm(dirty, 'Your new bet has not been posted. Leave without posting it? (Your words are kept as a draft either way.)');
  },
};
