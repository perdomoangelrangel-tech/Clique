// Stand-ins for what a browser provides, so the voice engine (static/js/voicecore.js) can be run and checked in Node.
// Nothing here touches a real microphone, network or audio device.

export class FakePC {
  static all = [];
  constructor(cfg) {
    this.cfg = cfg; this.tracks = []; this.closed = false; this.restarts = 0; this.added = [];
    this.connectionState = 'new'; this.iceConnectionState = 'new'; this.signalingState = 'stable';
    this.remoteDescription = null; this.localDescription = null;
    FakePC.all.push(this);
  }
  addTrack(t) { this.tracks.push(t); queueMicrotask(() => this.onnegotiationneeded && this.onnegotiationneeded()); return {}; }
  addTransceiver() { queueMicrotask(() => this.onnegotiationneeded && this.onnegotiationneeded()); return {}; }
  async setLocalDescription() { this.localDescription = { type: this.remoteDescription && this.signalingState === 'have-remote-offer' ? 'answer' : 'offer', sdp: 'fake' }; this.signalingState = this.localDescription.type === 'offer' ? 'have-local-offer' : 'stable'; }
  async setRemoteDescription(d) { this.remoteDescription = d; this.signalingState = d.type === 'offer' ? 'have-remote-offer' : 'stable'; }
  async addIceCandidate(c) { this.added.push(c); }
  restartIce() { this.restarts++; }
  close() { this.closed = true; this.connectionState = 'closed'; }
}

export class FakeMediaStream {
  constructor(tracks) { this.tracks = tracks || []; }
  getTracks() { return this.tracks; }
  getAudioTracks() { return this.tracks.filter((t) => t.kind === 'audio'); }
}

export const makeStream = () => {
  const track = { kind: 'audio', enabled: true, readyState: 'live', stopped: false, onended: null, stop() { this.stopped = true; this.readyState = 'ended'; } };
  return new FakeMediaStream([track]);
};

export function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

/** Timers that only move when told to. */
export function makeTimers() {
  let id = 0, now = 1_000_000; const live = new Map();
  return {
    now: () => now,
    setTimeout: (fn, ms) => { live.set(++id, { fn, at: now + ms, every: 0 }); return id; },
    clearTimeout: (i) => { live.delete(i); },
    setInterval: (fn, ms) => { live.set(++id, { fn, at: now + ms, every: ms }); return id; },
    clearInterval: (i) => { live.delete(i); },
    active: () => live.size,
    async advance(ms) {
      const end = now + ms;
      for (;;) {
        const due = [...live.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        const [i, t] = due; now = Math.max(now, t.at);
        if (t.every) t.at += t.every; else live.delete(i);
        t.fn(); await flush();
      }
      now = end;
    },
  };
}

export const flush = async () => { for (let i = 0; i < 12; i++) await new Promise((r) => setImmediate(r)); };

/** A whole fake page: server answers, microphone, peer connections and timers, around a fresh voice engine. */
export async function world(createVoiceCore, { me = 'u2', join = {}, state = null, secure = true, noMic = false } = {}) {
  FakePC.all.length = 0;
  const timers = makeTimers();
  const w = { calls: [], streams: [], beacons: [], timers, deafened: [], gum: async () => { const s = makeStream(); w.streams.push(s); return s; }, gumCalls: 0 };
  const handlers = {
    '/api/voice/join': () => ({ room: 'c1', peers: [], ice: [], people: [{ id: me, username: me }], maxPeople: 8, ...join }),
    '/api/voice/state': () => (state ? state() : { inRoom: true, people: [{ id: me, username: me }] }),
    '/api/voice/signal': () => ({ ok: true }),
    '/api/voice/leave': () => ({ ok: true }),
  };
  w.handlers = handlers;
  let n = 0;
  w.core = createVoiceCore({
    api: { post: async (url, body) => { w.calls.push([url, body]); const h = handlers[url]; if (!h) throw Object.assign(new Error('no route ' + url), { status: 404 }); return h(body); } },
    me: () => ({ id: me, username: me }),
    getUserMedia: noMic ? null : (c) => { w.gumCalls++; return w.gum(c); },
    secure,
    RTCPeerConnection: FakePC, MediaStream: FakeMediaStream,
    makeAnalyser: null, attachAudio: null,
    setDeaf: (d) => w.deafened.push(d),
    now: timers.now, setTimeout: timers.setTimeout, clearTimeout: timers.clearTimeout, setInterval: timers.setInterval, clearInterval: timers.clearInterval,
    genId: () => 'sid-' + String(++n).padStart(8, '0'),
    beacon: (url, body) => w.beacons.push([url, body]),
  });
  w.posted = (url) => w.calls.filter(([u]) => u === url);
  w.liveTracks = () => w.streams.flatMap((s) => s.getTracks()).filter((t) => !t.stopped).length;
  return w;
}
