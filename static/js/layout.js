/* Layout measurements the stylesheet cannot make for itself. CSS cannot know how tall the sticky header is (it wraps onto a different
   number of rows at every width, and a banner can join it), how tall the voice-call bar is, whether a pinned side panel is shorter than
   the screen, or whether a row of tabs is wider than the room it has. This file measures those and writes the answers where the CSS
   can use them: custom properties on <html> (--head-h, --bar-h, --dock-h, --nav-h), a class on pinned panels (.is-pinned) and an attribute on
   scrolling rows (data-more). It never changes what the page says or does, and the pages still work if it fails to run. */

const root = document.documentElement;
const PINNED = '.side-sticky, .ex-side, .ed-prev, .pk-code, .pin';
const STRIPS = '.subnav-in, .sections, .tabs, .chip-row, .pills, .rk-ladder, .vd-people';
const px = (n) => Math.ceil(n) + 'px';
const seen = new WeakSet();
let queued = false, started = false;

function bars() {
  const bar = document.querySelector('.top-bar'), rest = document.querySelector('.top-rest');
  if (bar) {
    const b = bar.getBoundingClientRect().height;
    root.style.setProperty('--bar-h', px(b));
    root.style.setProperty('--head-h', px(b + (rest ? rest.getBoundingClientRect().height : 0)));
  }
  const dock = document.getElementById('voice-dock');
  root.style.setProperty('--dock-h', dock && !dock.hidden ? px(dock.getBoundingClientRect().height) : '0px');
  const nav = document.getElementById('tabbar');                    // the phone bar along the bottom (0 when it is not showing)
  root.style.setProperty('--nav-h', nav ? px(nav.getBoundingClientRect().height) : '0px');
}

/* A panel is pinned (sticky) only while all of it fits in the space under the header. */
function pins() {
  const cs = getComputedStyle(root);
  const stuck = parseFloat(cs.getPropertyValue('--stuck-h')) || 0, gap = parseFloat(cs.getPropertyValue('--stick-gap')) || 16, dock = parseFloat(cs.getPropertyValue('--dock-h')) || 0;
  const room = window.innerHeight - stuck - dock - gap * 2;
  document.querySelectorAll(PINNED).forEach((el) => el.classList.toggle('is-pinned', el.offsetHeight <= room));
}

/* A row that scrolls sideways says which way there is more (the tabs on its edge are drawn by layout.css). */
function strips() {
  document.querySelectorAll(STRIPS).forEach((el) => {
    if (!seen.has(el)) {
      seen.add(el); el.classList.add('strip');
      el.addEventListener('scroll', () => look(el), { passive: true });
      if (window.ResizeObserver) new ResizeObserver(() => look(el)).observe(el);
    }
    look(el);
  });
}
function look(el) {
  const room = el.scrollWidth - el.clientWidth, more = [];
  if (room > 3) { if (el.scrollLeft > 3) more.push('l'); if (el.scrollLeft < room - 3) more.push('r'); }
  const v = more.join(' ');
  if ((el.dataset.more || '') !== v) { if (v) el.dataset.more = v; else delete el.dataset.more; }
}

function measure() {
  queued = false;
  bars(); pins(); strips();
}
export function layoutChanged() { if (!queued) { queued = true; requestAnimationFrame(measure); } }

export function startLayout() {
  if (started) return;
  started = true;
  try {
    measure();
    const reshaped = () => { bars(); layoutChanged(); };         // the header's size is written at once, so anything else that listens for the resize already sees the new heights
    window.addEventListener('resize', reshaped);
    window.addEventListener('orientationchange', reshaped);
    if (window.visualViewport) window.visualViewport.addEventListener('resize', reshaped);      // browser zoom and phone toolbars
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(layoutChanged);
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(layoutChanged);
      ro.observe(document.getElementById('voice-dock'));
      const watch = () => document.querySelectorAll('.top-bar, .top-rest, #tabbar').forEach((h) => { if (!seen.has(h)) { seen.add(h); ro.observe(h); } });
      watch(); new MutationObserver(watch).observe(document.getElementById('app'), { childList: true });
    }
    new MutationObserver(layoutChanged).observe(document.getElementById('app'), { childList: true, subtree: true });
    // a click on the tab that marks the edge of a scrolling row scrolls that way
    document.addEventListener('click', (e) => {
      const el = e.target;
      if (!(el instanceof Element) || !el.classList.contains('strip') || !el.dataset.more) return;
      const r = el.getBoundingClientRect(), x = e.clientX - r.left, step = Math.max(120, el.clientWidth * 0.7);
      if (el.dataset.more.includes('r') && x > el.clientWidth - 26) el.scrollBy({ left: step, behavior: 'smooth' });
      else if (el.dataset.more.includes('l') && x < 26) el.scrollBy({ left: -step, behavior: 'smooth' });
    });
  } catch { /* the stylesheet's own defaults still lay the page out */ }
}
