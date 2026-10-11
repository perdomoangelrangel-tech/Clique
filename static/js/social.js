// Friends and chat, from the shell's point of view: tell the server where we are, keep the two header badges
// up to date, and say so when a message arrives somewhere else.
import { get, post } from './api.js';
import { S, go } from './state.js';
import { debounce } from './util.js';
import { toast } from './ui.js';
import { t } from './i18n.js';

export const social = { online: 0, unread: 0, openChat: null };      // openChat: the chat that is on screen right now

// ---- where am I (a handful of fixed phrases, never titles or names)
export function whereFrom(path) {
  let m;
  if ((m = path.match(/^\/games\/(\w+)/))) return { k: 'game', v: m[1] };
  if (/^\/games\/?$/.test(path)) return { k: 'casino' };
  if (/^\/poker/.test(path)) return { k: 'poker' };
  if (/^\/market\//.test(path)) return { k: 'market' };
  if (/^\/create/.test(path)) return { k: 'create' };
  if (/^\/circles/.test(path)) return { k: 'circles' };
  if (/^\/circle\//.test(path)) return { k: 'circle' };
  if (/^\/weekly/.test(path)) return { k: 'weekly' };
  if (/^\/(u\/|portfolio)/.test(path)) return { k: 'profile' };
  if (/^\/friends/.test(path)) return { k: 'friends' };
  if (/^\/chat/.test(path)) return { k: 'chat' };
  if (/^\/?$/.test(path)) return { k: 'markets' };
  return { k: 'other' };
}
const currentPath = () => (location.hash.slice(1) || '/').split('?')[0];

let beat = null, onHash = null, onVis = null;
const ping = () => { if (S.user) post('/api/presence', { where: whereFrom(currentPath()), visible: !document.hidden }).catch(() => {}); };
const pingSoon = debounce(ping, 600);

export function startPresence() {
  stopPresence();
  ping();
  beat = setInterval(ping, 30000);
  onHash = () => pingSoon();
  onVis = () => { ping(); if (!document.hidden) refreshBadges(); };
  window.addEventListener('hashchange', onHash);
  document.addEventListener('visibilitychange', onVis);
}
export function stopPresence() {
  clearInterval(beat); beat = null;
  if (onHash) window.removeEventListener('hashchange', onHash);
  if (onVis) document.removeEventListener('visibilitychange', onVis);
  onHash = onVis = null;
  social.online = 0; social.unread = 0; social.openChat = null;
  paintBadges();
}

// ---- the two little numbers on the header buttons
export function paintBadges() {
  const set = (key, n, cap = 99) => document.querySelectorAll(`[data-badge="${key}"]`).forEach((el) => {
    el.textContent = n > cap ? `${cap}+` : String(n);
    el.classList.toggle('hidden', !n);
  });
  set('friends', social.online);
  set('chat', social.unread);
}
export async function refreshBadges() {
  if (!S.user) return;
  try {
    const [f, c] = await Promise.all([get('/api/friends'), get('/api/chats/unread')]);
    social.online = f.online; social.unread = c.total;
    paintBadges();
  } catch { /* the next event or the next minute tries again */ }
}
export const refreshBadgesSoon = debounce(refreshBadges, 500);
export function setUnread(total) { social.unread = total; paintBadges(); }

// ---- things that happen on the live stream
let lastToast = 0;
export function onSocialEvent(ev) {
  if (ev.type === 'presence' || ev.type === 'chats') { refreshBadgesSoon(); return; }
  if (ev.type === 'friends') {
    refreshBadgesSoon();
    if (ev.by && ev.by !== S.user?.username) {
      if (ev.what === 'requested') toast(t('{nombre} quiere ser tu amigo', { nombre: ev.by }), '', { onClick: () => go('#/friends'), ms: 6000 });
      else if (ev.what === 'friends') toast(t('{nombre} y tú ya son amigos', { nombre: ev.by }), 'ok', { onClick: () => go('#/friends'), ms: 5000 });
    }
    return;
  }
  if (ev.type !== 'chat' || !ev.msg) return;
  if (ev.msg.u === S.user?.id || ev.msg.sys) return;
  if (social.openChat === ev.id && !document.hidden) return;                    // you are looking right at it
  if (ev.kind !== 'global') {                                                    // the busy site-wide chat never nags
    social.unread += 1; paintBadges();
    if (Date.now() - lastToast > 1500) {
      lastToast = Date.now();
      const text = ev.msg.x.length > 60 ? ev.msg.x.slice(0, 59) + '…' : ev.msg.x;
      const room = ev.kind === 'circle' ? ev.title : ev.kind === 'group' ? (ev.title || t('tu grupo')) : '';
      toast(room ? t('{nombre} en {sala}: {texto}', { nombre: ev.msg.name, sala: room, texto: text }) : t('{nombre}: {texto}', { nombre: ev.msg.name, texto: text }), '', { onClick: () => go('#/chat/' + ev.id), ms: 5000 });
    }
  }
}
