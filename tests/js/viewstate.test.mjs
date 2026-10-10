// The part of "getting back to where you were" that can be checked without a page: what is remembered, what is not, drafts, and
// the unsaved-changes guard. It runs viewstate.js against small stand-ins for the browser's storage and history.
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

const store = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), _m: m }; };
globalThis.sessionStorage = store();
globalThis.localStorage = store();
const listeners = {};
const scrolls = [];
globalThis.window = { scrollY: 0, innerHeight: 800, addEventListener: (t, f) => { (listeners[t] ||= []).push(f); }, scrollTo: (x, y) => { scrolls.push(y); window.scrollY = y; } };
globalThis.history = { state: null, scrollRestoration: 'auto', replaceState(s) { this.state = s; } };
globalThis.document = { documentElement: { scrollHeight: 5000 } };

const V = await import('../../static/js/viewstate.js');

beforeEach(() => { scrolls.length = 0; window.scrollY = 0; history.state = null; });

test('visual state is remembered per screen and merged, and comes back after a reload (it is in sessionStorage)', () => {
  V.remember('markets', { sort: 'new', q: 'party' });
  V.remember('markets', { q: 'friday' });
  assert.deepEqual(V.recall('markets'), { sort: 'new', q: 'friday' });
  assert.deepEqual(V.recall('never-seen'), {});
  assert.match(sessionStorage.getItem('clique-nav:v:markets'), /friday/);
});

test('money is never put in the remembered state by this module: it stores only what a screen hands it', () => {
  V.remember('exchange:NEXO', { range: '5m' });
  const raw = [...sessionStorage._m.values()].join(' ');
  assert.doesNotMatch(raw, /balance|price|quote|accum/i);
});

test('a fresh page view gets a marker; coming back to the same entry is a revisit', () => {
  const first = V.arrive();
  assert.equal(first.revisit, false);
  assert.ok(history.state.cq.id);
  const id = history.state.cq.id;
  const again = V.arrive();                                                      // Back/Forward/reload: the entry already has its marker
  assert.equal(again.revisit, true);
  assert.equal(V.entryNow().id, id);
});

test('scroll position is saved when leaving and put back on a revisit, but a new visit starts at the top', async () => {
  V.arrive(); const id = V.entryNow().id;
  window.scrollY = 1234; V.leaving();
  assert.match(sessionStorage.getItem('clique-nav:scroll'), new RegExp(id));
  V.settle({ revisit: true });
  assert.equal(scrolls.at(-1), 1234);
  scrolls.length = 0;
  V.settle({ revisit: false });
  assert.equal(scrolls.at(-1), 0);
});

test('drafts are saved, expire after three days, and can be cleared', () => {
  V.saveDraft('create', { title: 'Will it rain?' });
  assert.deepEqual(V.loadDraft('create'), { title: 'Will it rain?' });
  const key = 'clique-draft:create', d = JSON.parse(localStorage.getItem(key));
  d.t -= 4 * 86400000; localStorage.setItem(key, JSON.stringify(d));
  assert.equal(V.loadDraft('create'), null);
  V.saveDraft('chat:abc', 'half a message'); V.clearDraft('chat:abc');
  assert.equal(V.loadDraft('chat:abc'), null);
});

test('the unsaved-changes guard only objects while there is something to lose, and stops when the form is gone', () => {
  let dirty = false;
  assert.equal(V.unsaved(), null);
  const h = V.guardForm(() => dirty);
  assert.equal(V.unsaved(), null);                                               // untouched form: leave freely
  dirty = true;
  assert.ok(V.unsaved());
  h.unmount();
  assert.equal(V.unsaved(), null);                                               // the view closed: nothing to guard
  const broken = V.guardForm(() => { throw new Error('x'); });
  assert.equal(V.unsaved(), null);                                               // a broken check never traps someone on a page
  broken.unmount();
});

test('closing the tab with unsaved changes asks the browser to confirm; with none, it does not', () => {
  const fire = () => { const e = { prevented: false, preventDefault() { this.prevented = true; } }; for (const f of listeners.beforeunload || []) f(e); return e.prevented; };
  assert.equal(fire(), false);
  let dirty = true; const h = V.guardForm(() => dirty);
  assert.equal(fire(), true);
  dirty = false;
  assert.equal(fire(), false);
  h.unmount();
});
