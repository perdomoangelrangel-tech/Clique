/* Voice rooms, wired to the real browser. This module is imported once, by app.js, when the page loads, and is never unmounted:
   moving between Casino, Markets, the Exchange and the Store only swaps what is inside <main>, so a call carries on untouched.
   The call lives here, the little panel pinned to the bottom of the screen (the dock) is drawn from here, and the circle pages
   only ask it to join. See voicecore.js for how the call itself works. Nothing is recorded. */
import { post, get } from './api.js';
import { S } from './state.js';
import { createVoiceCore, ERRORS } from './voicecore.js';
import { avatar, esc } from './util.js';
import { icon } from './icons.js';
import { t, th, tp } from './i18n.js';

const dock = () => document.getElementById('voice-dock');
let audioBox = null, ctx = null;
const remote = new Map();                 // peer id -> <audio>

function makeAnalyser(stream) {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  try {
    ctx = ctx || new Ctx();
    const src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser();
    an.fftSize = 512; src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    return {
      read() { an.getByteTimeDomainData(buf); let sum = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; } return Math.sqrt(sum / buf.length); },
      close() { try { src.disconnect(); } catch { /* already gone */ } },
    };
  } catch { return null; }
}

function attachAudio(peerId, stream, deaf) {
  audioBox = audioBox || (() => { const d = document.createElement('div'); d.id = 'voice-audio'; d.hidden = true; document.body.appendChild(d); return d; })();
  remote.get(peerId)?.remove();
  const el = document.createElement('audio');
  el.autoplay = true; el.setAttribute('playsinline', ''); el.muted = !!deaf; el.srcObject = stream;
  audioBox.appendChild(el);
  remote.set(peerId, el);
  el.play().catch(() => { /* the person clicked Join, so the browser allows it; if not, the next click will */ });
  return () => { el.srcObject = null; el.remove(); if (remote.get(peerId) === el) remote.delete(peerId); };
}

const core = createVoiceCore({
  api: { post, get },
  me: () => S.user,
  getUserMedia: navigator.mediaDevices && navigator.mediaDevices.getUserMedia ? (c) => navigator.mediaDevices.getUserMedia(c) : null,
  secure: window.isSecureContext !== false,
  RTCPeerConnection: window.RTCPeerConnection, MediaStream: window.MediaStream,
  makeAnalyser, attachAudio,
  setDeaf: (deaf) => { for (const el of remote.values()) el.muted = deaf; },
  now: () => Date.now(),
  setTimeout: (f, ms) => setTimeout(f, ms), clearTimeout: (id) => clearTimeout(id),
  setInterval: (f, ms) => setInterval(f, ms), clearInterval: (id) => clearInterval(id),
  genId: () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '').slice(0, 24) : Math.random().toString(36).slice(2) + Date.now().toString(36)),
  beacon: (path, body) => { try { navigator.sendBeacon(path, new Blob([JSON.stringify(body)], { type: 'application/json' })); } catch { /* the server will notice we went quiet */ } },
});

// ---- the dock: a compact panel that follows you through every section ----
function statusText(st) {
  if (st.status === 'requesting') return t('Esperando el permiso del micrófono…');
  if (st.status === 'joining') return t('Conectando…');
  if (st.status === 'reconnecting') return t('Reconectando…');
  const others = st.people.length - 1;
  return others > 0 ? tp(st.people.length, 'Conectado · {n} en la sala', 'Conectado · {n} en la sala') : t('Conectado · eres el único aquí');
}

function paintDock() {
  const el = dock(); if (!el) return;
  const st = core.state;
  const live = st.status !== 'idle' && st.status !== 'error';      // a failed attempt shows only its message, never call controls
  const visible = live || !!st.error;
  el.hidden = !visible;
  document.body.classList.toggle('has-voice', visible);
  if (!visible) { el.innerHTML = ''; return; }
  const people = st.people.map((p) => {
    const speaking = st.speaking[p.id] && !p.muted, link = st.peers[p.id];
    return `<span class="vd-p ${speaking ? 'speaking' : ''} ${p.muted ? 'muted' : ''} ${p.id !== S.user.id && link === 'failed' ? 'bad' : ''}" title="${esc(p.username)}${p.muted ? ' ' + esc(t('(silenciado)')) : ''}${p.deaf ? ' ' + esc(t('(sin oír)')) : ''}">${avatar(p.username, 28)}<em>${esc(p.username)}</em>${p.muted ? `<i class="vd-off">${icon('microphone-slash', 11)}</i>` : ''}</span>`;
  }).join('');
  const err = st.error ? `<div class="vd-err" role="alert"><span>${esc(t(st.error.message))}</span>${['busy', 'denied', 'nodevice'].includes(st.error.code) && live ? `<button data-a="mic">${t('Probar el micrófono')}</button>` : ''}<button data-a="dismiss">${t('Cerrar')}</button></div>` : '';
  el.innerHTML = `<div class="vd-in">
    ${live ? `<div class="vd-info"><span class="vd-dot ${st.status}"></span><div class="vd-txt"><b>${th('Voz · {circulo}', { circulo: st.circleName })}</b><small>${esc(statusText(st))}</small></div></div>
      <div class="vd-people" aria-label="${esc(t('Gente en la llamada'))}">${people}</div>
      <div class="vd-btns">
        <button data-a="mic" class="${st.muted ? 'off' : ''}" aria-pressed="${st.muted}" title="${esc(st.muted ? t('Activar tu micrófono') : t('Silenciar tu micrófono'))}">${icon(st.muted ? 'microphone-slash' : 'microphone', 18)}<span>${st.muted ? t('Activar') : t('Silenciar')}</span></button>
        <button data-a="deaf" class="${st.deaf ? 'off' : ''}" aria-pressed="${st.deaf}" title="${esc(st.deaf ? t('Volver a oír a todos') : t('Dejar de oír a todos'))}">${icon(st.deaf ? 'speaker-simple-slash' : 'headphones', 18)}<span>${st.deaf ? t('Oír') : t('No oír')}</span></button>
        <a class="vd-room" href="#/circle/${esc(st.circleId)}" data-a="room" title="${esc(t('Volver al círculo'))}">${icon('users-three', 18)}<span>${t('Sala')}</span></a>
        <button data-a="leave" class="leave" title="${esc(t('Salir de la llamada'))}">${icon('phone-disconnect', 18)}<span>${t('Colgar')}</span></button></div>` : ''}
    ${err}</div>`;
}

core.subscribe(paintDock);
document.addEventListener('click', (e) => {
  const b = e.target.closest('#voice-dock [data-a]'); if (!b) return;
  const a = b.dataset.a;
  if (a === 'mic') core.toggleMic(); else if (a === 'deaf') core.toggleDeafen();
  else if (a === 'leave') core.leave(); else if (a === 'dismiss') core.clearError();
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) core.checkHealth(); });
window.addEventListener('online', () => core.checkHealth());
window.addEventListener('pagehide', () => core.leaveNow());
window.addEventListener('beforeunload', () => core.leaveNow());

export const voice = {
  join: (circle) => core.join(circle),
  leave: () => core.leave(),
  hangUp: () => core.leave(),
  toggleMic: () => core.toggleMic(),
  toggleDeafen: () => core.toggleDeafen(),
  onEvent: (ev) => core.onEvent(ev),
  checkHealth: () => core.checkHealth(),
  subscribe: (fn) => core.subscribe(fn),
  get state() { return core.state; },
  inRoom: (circleId) => core.state.circleId === circleId && core.state.status !== 'idle',
  ERRORS,
};
window.__voice = voice;                                         // handy for checking a call from the console
