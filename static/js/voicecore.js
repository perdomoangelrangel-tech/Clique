/* The voice engine. No page, no DOM and no globals in here: everything the browser provides (microphone, peer connections, audio
   analysis, timers, the server) is handed in as `env`. That is what lets the very same code be tested with fakes in Node and run
   for real in voice.js, which lives for as long as the page does and so keeps a call going while you move between sections.

   How a call works: every person in the room is connected straight to every other person (a "mesh"), which is fine for the small
   groups a circle has. The server only introduces people (signaling). The person who joins offers a connection to everybody already
   there. If two offers cross, the "perfect negotiation" rule settles it: the person with the smaller id is polite and gives way.

   Nothing is recorded: audio is never sent to the server, and this code has no way to save it. */

// The messages are keys for t() (static/js/i18n.js): the pages that show them translate them, so this file stays free of the page.
export const ERRORS = {                                 // i18n: claves ↓
  denied: 'No diste permiso para el micrófono. Permítelo para este sitio en los ajustes de tu navegador y vuelve a entrar.',
  nodevice: 'No encontramos ningún micrófono. Conecta uno (o enciéndelo) y vuelve a entrar.',
  busy: 'Otra app está usando tu micrófono, o no se pudo encender. Cierra la otra app y vuelve a entrar.',
  unsupported: 'Este navegador no puede hacer llamadas de voz. Prueba un Chrome, Edge, Firefox o Safari reciente.',
  insecure: 'Las llamadas de voz necesitan una conexión segura (https).',
  taken: 'Entraste a esta llamada desde otra pestaña, así que esta colgó.',
  removed: 'Ya no estás en este círculo, así que te sacamos de la llamada.',
  full: 'Esta sala de voz está llena.',
  lost: 'Se perdió la conexión con el servidor. Intentando regresarte...',
  failed: 'No se pudo entrar a la llamada.',
  stopped: 'Tu micrófono se detuvo. Toca el botón del micrófono para intentarlo otra vez.',
};                                                      // i18n: fin

const SPEAK_ON = 0.025, SPEAK_OFF = 0.012, SPEAK_HOLD_MS = 350;

export function createVoiceCore(env) {
  const E = env;
  const state = {
    status: 'idle',                  // idle, requesting (asking for the mic), joining, connected, reconnecting, error
    error: null, circleId: null, circleName: '', sid: null, muted: false, deaf: false,
    people: [], peers: {}, speaking: {}, startedAt: 0, maxPeople: 8,
  };
  const subs = new Set();
  let ice = [], local = null, localAnalyser = null, hb = null, meter = null, rejoinTimer = null, rejoinTries = 0, joining = null, inRoom = false;   // inRoom: the server has said yes to our join (not while the mic prompt is still open)
  const conns = new Map();           // peer id -> {pc, sid, polite, makingOffer, ignoreOffer, pending: [], audio, analyser, since, tries}

  const emit = () => { for (const f of subs) { try { f(state); } catch { /* a listener must not break the call */ } } };
  const set = (patch) => { Object.assign(state, patch); emit(); };
  const me = () => E.me();
  const log = (...a) => { if (E.debug) E.debug(...a); };

  // ---- the microphone ---------------------------------------------------------------------------------------------
  function describe(err) {
    const name = (err && err.name) || '';
    if (name === 'NotAllowedError' || name === 'SecurityError' || name === 'PermissionDeniedError') return 'denied';
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') return 'nodevice';
    if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') return 'busy';
    return 'busy';
  }

  async function openMic() {
    if (!E.getUserMedia) throw Object.assign(new Error(ERRORS.unsupported), { code: E.secure === false ? 'insecure' : 'unsupported' });
    try {
      return await E.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
    } catch (err) {
      if (err && err.name === 'OverconstrainedError') return E.getUserMedia({ audio: true, video: false });
      throw Object.assign(new Error(ERRORS[describe(err)]), { code: describe(err) });
    }
  }

  function watchLocal(stream) {
    for (const t of stream.getAudioTracks()) {
      t.enabled = !state.muted;
      t.onended = () => {                                        // unplugged, or the browser took it away
        if (state.status === 'idle' || local !== stream) return;
        set({ error: { code: 'busy', message: ERRORS.stopped }, muted: true });
        pushState();
      };
    }
  }

  // ---- speaking indicators ----------------------------------------------------------------------------------------
  function measure(stream, key) {
    if (!E.makeAnalyser) return null;
    const a = E.makeAnalyser(stream);
    return a ? { key, read: a.read, close: a.close, on: false, since: 0 } : null;
  }

  function startMeter() {
    if (meter) return;
    meter = E.setInterval(() => {
      const now = E.now();
      let changed = false;
      const probes = [localAnalyser, ...[...conns.values()].map((c) => c.analyser)].filter(Boolean);
      for (const p of probes) {
        let level = 0;
        try { level = p.read(); } catch { level = 0; }
        const mutedMe = p.key === me().id && state.muted;
        const loud = !mutedMe && level > (p.on ? SPEAK_OFF : SPEAK_ON);
        if (loud) p.since = now;
        const on = loud || (p.on && now - p.since < SPEAK_HOLD_MS);
        if (on !== p.on) { p.on = on; state.speaking[p.key] = on; changed = true; }
      }
      if (changed) emit();
    }, 120);
  }
  const stopMeter = () => { if (meter) { E.clearInterval(meter); meter = null; } };

  // ---- talking to the server --------------------------------------------------------------------------------------
  const send = (to, toSid, data) => E.api.post('/api/voice/signal', { circleId: state.circleId, sid: state.sid, to, toSid, data }).catch((e) => {
    log('signal failed', e && e.message);
  });

  async function pushState() {
    if (!state.circleId || state.status === 'idle' || !inRoom) return;       // still waiting for the microphone: there is nothing to check yet
    try {
      const out = await E.api.post('/api/voice/state', { circleId: state.circleId, sid: state.sid, muted: state.muted, deaf: state.deaf });
      if (!out.inRoom) return dropped();
      rejoinTries = 0;
      if (state.status === 'reconnecting') set({ status: peerCount() ? 'connected' : 'joining', error: null });
      set({ people: out.people });
      reconcile();
    } catch (e) {
      if (e && (e.status === 401)) return leave();
      if (e && e.status === 403) return leave('removed');
      if (state.status === 'connected' || state.status === 'joining') set({ status: 'reconnecting', error: { code: 'lost', message: ERRORS.lost } });
    }
  }

  // The server no longer has us (it restarted, or we were quiet too long): get back in without asking for the mic again.
  function dropped() {
    if (state.status === 'idle') return;
    set({ status: 'reconnecting', error: { code: 'lost', message: ERRORS.lost } });
    if (rejoinTimer) return;
    const wait = Math.min(15000, 1000 * 2 ** rejoinTries++);
    rejoinTimer = E.setTimeout(async () => {
      rejoinTimer = null;
      if (state.status !== 'reconnecting' || !local) return;
      try { await enter(); } catch { dropped(); }
    }, wait);
  }

  // ---- peer connections -------------------------------------------------------------------------------------------
  const peerCount = () => [...conns.values()].filter((c) => c.pc.connectionState === 'connected' || c.pc.iceConnectionState === 'connected' || c.pc.iceConnectionState === 'completed').length;
  const refreshPeers = () => {
    const peers = {};
    for (const [id, c] of conns) peers[id] = c.pc.connectionState === 'connected' || c.pc.iceConnectionState === 'connected' || c.pc.iceConnectionState === 'completed' ? 'connected'
      : c.pc.connectionState === 'failed' || c.pc.iceConnectionState === 'failed' ? 'failed' : 'connecting';
    state.peers = peers;
    if (state.status === 'joining' && (state.people.length <= 1 || Object.values(peers).includes('connected'))) state.status = 'connected';       // alone in the room counts as connected
    emit();
  };

  function makeConn(peerId, peerSid) {
    const old = conns.get(peerId);
    if (old) closeConn(peerId);
    const pc = new E.RTCPeerConnection({ iceServers: ice });
    const c = { pc, sid: peerSid, polite: me().id < peerId, makingOffer: false, ignoreOffer: false, pending: [], audio: null, analyser: null, since: E.now(), tries: 0, disc: null };
    conns.set(peerId, c);
    if (local) for (const t of local.getTracks()) pc.addTrack(t, local);
    else pc.addTransceiver('audio', { direction: 'recvonly' });          // no microphone right now: we can still hear them
    pc.onicecandidate = (e) => { if (e.candidate) send(peerId, c.sid, { type: 'candidate', candidate: e.candidate.toJSON ? e.candidate.toJSON() : e.candidate }); };
    pc.ontrack = (e) => {
      const stream = (e.streams && e.streams[0]) || new E.MediaStream([e.track]);
      if (c.stream === stream) return;
      c.stream = stream;
      c.detach && c.detach();
      c.detach = E.attachAudio ? E.attachAudio(peerId, stream, state.deaf) : null;
      c.analyser && c.analyser.close();
      c.analyser = measure(stream, peerId);
      startMeter();
    };
    pc.onnegotiationneeded = async () => {
      try {
        c.makingOffer = true;
        await pc.setLocalDescription();
        await send(peerId, c.sid, { type: 'offer', description: pc.localDescription });
      } catch (e) { log('offer failed', e && e.message); } finally { c.makingOffer = false; }
    };
    const health = () => {
      refreshPeers();
      const bad = pc.connectionState === 'failed' || pc.iceConnectionState === 'failed';
      const gone = pc.connectionState === 'disconnected' || pc.iceConnectionState === 'disconnected';
      if (c.disc) { E.clearTimeout(c.disc); c.disc = null; }
      if (bad) retry(peerId);
      else if (gone) c.disc = E.setTimeout(() => retry(peerId), 6000);
    };
    pc.onconnectionstatechange = health;
    pc.oniceconnectionstatechange = health;
    return c;
  }

  function retry(peerId) {
    const c = conns.get(peerId);
    if (!c || state.status === 'idle') return;
    if (c.pc.connectionState === 'connected' || c.pc.iceConnectionState === 'connected') return;
    if (++c.tries > 3) {                                       // ICE restarts did not help: build the connection again
      const sid = c.sid;
      closeConn(peerId);
      if (state.people.find((p) => p.id === peerId)) { makeConn(peerId, sid); }
      return;
    }
    try { c.pc.restartIce(); } catch { /* an old browser: the next attempt rebuilds it */ }
  }

  function closeConn(peerId) {
    const c = conns.get(peerId);
    if (!c) return;
    conns.delete(peerId);
    if (c.disc) E.clearTimeout(c.disc);
    try { c.pc.onicecandidate = c.pc.ontrack = c.pc.onnegotiationneeded = c.pc.onconnectionstatechange = c.pc.oniceconnectionstatechange = null; c.pc.close(); } catch { /* already closed */ }
    c.detach && c.detach();
    c.analyser && c.analyser.close();
    delete state.speaking[peerId];
  }

  async function onSignal(ev) {
    if (state.status === 'idle' || ev.room !== state.circleId || ev.toSid !== state.sid) return;       // not for this tab, or an old call
    const from = ev.from, data = ev.data || {};
    let c = conns.get(from);
    if (c && c.sid !== ev.fromSid) { closeConn(from); c = null; }                                    // they rejoined: a new connection
    if (!c) {
      if (data.type !== 'offer') return;                                                              // only an offer starts a connection from their side
      c = makeConn(from, ev.fromSid);
    }
    const pc = c.pc;
    try {
      if (data.type === 'offer') {
        const collision = c.makingOffer || pc.signalingState !== 'stable';
        c.ignoreOffer = !c.polite && collision;
        if (c.ignoreOffer) return;
        await pc.setRemoteDescription(data.description);
        for (const cand of c.pending.splice(0)) { try { await pc.addIceCandidate(cand); } catch { /* stale */ } }
        await pc.setLocalDescription();
        await send(from, c.sid, { type: 'answer', description: pc.localDescription });
      } else if (data.type === 'answer') {
        await pc.setRemoteDescription(data.description);
        for (const cand of c.pending.splice(0)) { try { await pc.addIceCandidate(cand); } catch { /* stale */ } }
      } else if (data.type === 'candidate') {
        if (!pc.remoteDescription) { c.pending.push(data.candidate); return; }
        try { await pc.addIceCandidate(data.candidate); } catch (e) { if (!c.ignoreOffer) log('candidate failed', e && e.message); }
      } else if (data.type === 'ready') {
        if (!pc.remoteDescription && !c.makingOffer) offerTo(from);
      }
    } catch (e) { log('signal handling failed', e && e.message); }
  }

  function offerTo(peerId) {
    const person = state.people.find((p) => p.id === peerId);
    const sid = (conns.get(peerId) || {}).sid || (person && person.sid);
    if (!sid) return;
    if (!conns.has(peerId)) makeConn(peerId, sid);
  }

  // Keep one connection per person who is in the room, and none for people who left.
  function reconcile() {
    const present = new Set(state.people.map((p) => p.id).filter((id) => id !== me().id));
    for (const id of [...conns.keys()]) if (!present.has(id)) closeConn(id);
    for (const [id, c] of conns) { if (!state.peers[id]) state.peers[id] = 'connecting'; void c; }
    refreshPeers();
  }

  // ---- joining and leaving ----------------------------------------------------------------------------------------
  async function enter() {
    const out = await E.api.post('/api/voice/join', { circleId: state.circleId, sid: state.sid });
    ice = out.ice || [];
    inRoom = true;
    set({ people: out.people, maxPeople: out.maxPeople || state.maxPeople });
    for (const peer of out.peers) {
      const c = conns.get(peer.id);
      if (!c || c.sid !== peer.sid || ['failed', 'closed'].includes(c.pc.connectionState)) makeConn(peer.id, peer.sid);     // we call the people already here
    }
    for (const id of [...conns.keys()]) if (!out.peers.find((p) => p.id === id) && !state.people.find((p) => p.id === id)) closeConn(id);
    set({ status: out.peers.length === 0 || Object.values(state.peers).includes('connected') ? 'connected' : 'joining', error: null });
    rejoinTries = 0;
    refreshPeers();
  }

  async function join(circle) {
    if (state.status !== 'idle' && state.circleId === circle.id && !state.error) return;                 // already in this call
    if (joining) return joining;
    joining = (async () => {
      if (state.status !== 'idle') await leave();                                                       // one call at a time
      const sid = E.genId();
      set({ status: 'requesting', error: null, circleId: circle.id, circleName: circle.name || '', sid, muted: false, deaf: false,
            people: [], peers: {}, speaking: {}, startedAt: E.now() });
      const stillAsking = () => state.sid === sid && state.status === 'requesting';          // hanging up while the mic prompt is open cancels the join
      let stream;
      try {
        stream = await openMic();
      } catch (e) {
        if (!stillAsking()) return false;
        const code = e.code || 'failed';
        set({ status: 'error', error: { code, message: ERRORS[code] || e.message }, circleId: null });
        return false;
      }
      if (!stillAsking()) {                                      // they changed their mind (or joined elsewhere) while the browser was asking: let the mic go
        for (const t of stream.getTracks()) { try { t.stop(); } catch { /* ignore */ } }
        return false;
      }
      local = stream;
      watchLocal(local);
      localAnalyser = measure(local, me().id);
      startMeter();
      set({ status: 'joining' });
      try {
        await enter();
      } catch (e) {
        stopEverything();
        const code = e && e.status === 409 ? 'full' : 'failed';
        set({ status: 'error', error: { code, message: e && e.status === 409 ? e.message : (e && e.message) || ERRORS.failed }, circleId: null });
        return false;
      }
      hb = E.setInterval(pushState, 10000);
      return true;
    })();
    try { return await joining; } finally { joining = null; }
  }

  function stopEverything() {
    inRoom = false;
    if (hb) { E.clearInterval(hb); hb = null; }
    if (rejoinTimer) { E.clearTimeout(rejoinTimer); rejoinTimer = null; }
    stopMeter();
    for (const id of [...conns.keys()]) closeConn(id);
    if (local) { for (const t of local.getTracks()) { t.onended = null; try { t.stop(); } catch { /* ignore */ } } local = null; }
    if (localAnalyser) { localAnalyser.close(); localAnalyser = null; }
  }

  async function leave(reason) {
    const wasIn = state.circleId, sid = state.sid, status = state.status;
    stopEverything();
    set({ status: reason ? 'error' : 'idle', error: reason && ERRORS[reason] ? { code: reason, message: ERRORS[reason] } : null,
          circleId: null, circleName: '', sid: null, people: [], peers: {}, speaking: {}, muted: false, deaf: false, startedAt: 0 });
    if (wasIn && status !== 'idle' && reason !== 'removed' && reason !== 'taken') {
      try { await E.api.post('/api/voice/leave', { circleId: wasIn, sid }); } catch { /* the server drops quiet people anyway */ }
    }
  }

  // The page is closing: hang up even if there is no time to wait for an answer.
  function leaveNow() {
    if (!state.circleId) return;
    if (E.beacon) E.beacon('/api/voice/leave', { circleId: state.circleId, sid: state.sid });
    stopEverything();
    Object.assign(state, { status: 'idle', circleId: null, sid: null, people: [], peers: {}, speaking: {} });
  }

  // ---- the buttons ------------------------------------------------------------------------------------------------
  async function toggleMic() {
    if (!local) {                                              // the mic went away: try to get it back
      if (state.status === 'idle') return;
      try { local = await openMic(); watchLocal(local); localAnalyser = measure(local, me().id); for (const [, c] of conns) for (const t of local.getTracks()) c.pc.addTrack(t, local); set({ muted: false, error: null }); }
      catch (e) { set({ error: { code: e.code || 'busy', message: ERRORS[e.code] || ERRORS.busy } }); }
      pushState();
      return;
    }
    const muted = !state.muted;
    for (const t of local.getAudioTracks()) t.enabled = !muted;
    if (!muted && state.error && state.error.code === 'busy') {                // a dead mic: try to start it again
      const dead = local.getAudioTracks().every((t) => t.readyState === 'ended');
      if (dead) { local = null; return toggleMic(); }
    }
    if (muted) delete state.speaking[me().id];
    set({ muted });
    pushState();
  }

  function toggleDeafen() {
    const deaf = !state.deaf;
    if (E.setDeaf) E.setDeaf(deaf);
    set({ deaf });
    pushState();
  }

  function clearError() { if (state.status === 'error' || state.error) set({ status: state.circleId ? state.status : 'idle', error: null }); }

  // ---- messages from the server, and from the page ----------------------------------------------------------------
  function onEvent(ev) {
    if (ev.k === 'signal') return onSignal(ev);
    if (ev.k === 'replaced' && ev.sid === state.sid) return leave('taken');
    if (ev.k === 'removed' && ev.sid === state.sid) return leave('removed');
    if (ev.k === 'room' && ev.room === state.circleId && state.status !== 'idle') {
      set({ people: ev.people });
      reconcile();
      // somebody is in the room but nobody has called us: after a few seconds, call them ourselves
      for (const p of ev.people) {
        if (p.id === me().id || conns.has(p.id)) continue;
        const wait = me().id < p.id ? 800 : 5000;
        E.setTimeout(() => { if (state.status !== 'idle' && !conns.has(p.id) && state.people.find((q) => q.id === p.id)) offerTo(p.id); }, wait);
      }
    }
  }

  // The page woke up, or the live stream reopened, or the network came back: check that everything is still there.
  function checkHealth() {
    if (state.status === 'idle') return;
    pushState();
    for (const id of [...conns.keys()]) {
      const c = conns.get(id);
      if (c && ['failed', 'disconnected'].includes(c.pc.connectionState)) retry(id);
    }
  }

  return {
    state, join, leave, leaveNow, toggleMic, toggleDeafen, onEvent, checkHealth, clearError, pushState,
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    connections: () => [...conns.keys()],
    setDeafened(deaf) { state.deaf = deaf; },
  };
}
