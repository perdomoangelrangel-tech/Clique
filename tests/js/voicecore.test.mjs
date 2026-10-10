import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createVoiceCore, ERRORS } from '../../static/js/voicecore.js';
import { FakePC, world, flush, deferred, makeStream } from './fakes.mjs';

const C1 = { id: 'c1', name: 'The Usual Suspects' }, C2 = { id: 'c2', name: 'Other' };
const peer = (id, sid = 'peer-sid-' + id) => ({ id, sid, username: id });
const withPeer = { peers: [peer('u1')], people: [{ id: 'u1', username: 'u1' }, { id: 'u2', username: 'u2' }] };

test('joining alone: asks for the mic once, tells the server once, and counts as connected', async () => {
  const w = await world(createVoiceCore);
  assert.equal(await w.core.join(C1), true);
  assert.equal(w.core.state.status, 'connected');
  assert.equal(w.gumCalls, 1);
  assert.equal(w.posted('/api/voice/join').length, 1);
  assert.equal(FakePC.all.length, 0);
  assert.equal(w.core.state.circleId, 'c1');
});

test('joining a room with somebody in it makes exactly one connection, with the mic attached, and offers', async () => {
  const w = await world(createVoiceCore, { join: withPeer });
  await w.core.join(C1); await flush();
  assert.equal(FakePC.all.length, 1);
  assert.equal(FakePC.all[0].tracks.length, 1);
  const offers = w.posted('/api/voice/signal').filter(([, b]) => b.data.type === 'offer');
  assert.equal(offers.length, 1);
  assert.equal(offers[0][1].to, 'u1');
  assert.equal(offers[0][1].toSid, 'peer-sid-u1');
});

test('no duplicate connections: joining again, or hearing the same room twice, changes nothing', async () => {
  const w = await world(createVoiceCore, { join: withPeer });
  await w.core.join(C1); await flush();
  await w.core.join(C1);                                                          // already in this call
  w.core.onEvent({ k: 'room', room: 'c1', people: withPeer.people });
  w.core.onEvent({ k: 'room', room: 'c1', people: withPeer.people });
  await w.timers.advance(6000);
  assert.equal(FakePC.all.length, 1);
  assert.equal(w.posted('/api/voice/join').length, 1);
  assert.equal(w.gumCalls, 1);
});

test('leaving releases everything: connections, microphone, timers, and tells the server', async () => {
  const w = await world(createVoiceCore, { join: withPeer });
  await w.core.join(C1); await flush();
  const sid = w.core.state.sid;
  await w.core.leave();
  assert.equal(w.core.state.status, 'idle');
  assert.equal(w.core.state.circleId, null);
  assert.ok(FakePC.all.every((p) => p.closed));
  assert.equal(w.liveTracks(), 0);
  assert.equal(w.timers.active(), 0);
  assert.deepEqual(w.posted('/api/voice/leave').map(([, b]) => b), [{ circleId: 'c1', sid }]);
});

test('closing the page hangs up with a beacon and still releases the microphone', async () => {
  const w = await world(createVoiceCore, { join: withPeer });
  await w.core.join(C1); await flush();
  w.core.leaveNow();
  assert.equal(w.beacons.length, 1);
  assert.equal(w.beacons[0][0], '/api/voice/leave');
  assert.equal(w.liveTracks(), 0);
  assert.ok(FakePC.all.every((p) => p.closed));
  assert.equal(w.core.state.status, 'idle');
});

test('mute and deafen: the track is switched, the server is told, nothing reconnects', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  await w.core.toggleMic();
  assert.equal(w.core.state.muted, true);
  assert.equal(w.streams[0].getAudioTracks()[0].enabled, false);
  assert.equal(w.posted('/api/voice/state').at(-1)[1].muted, true);
  await w.core.toggleMic();
  assert.equal(w.streams[0].getAudioTracks()[0].enabled, true);
  w.core.toggleDeafen();
  assert.deepEqual(w.deafened, [true]);
  assert.equal(w.core.state.deaf, true);
  await flush();
  assert.equal(w.posted('/api/voice/state').at(-1)[1].deaf, true);
  assert.equal(w.gumCalls, 1);
});

for (const [name, code] of [['NotAllowedError', 'denied'], ['NotFoundError', 'nodevice'], ['NotReadableError', 'busy']]) {
  test(`microphone problem ${name} gives a clear message and joins nothing`, async () => {
    const w = await world(createVoiceCore);
    w.gum = async () => { throw Object.assign(new Error('x'), { name }); };
    assert.equal(await w.core.join(C1), false);
    assert.equal(w.core.state.status, 'error');
    assert.equal(w.core.state.error.code, code);
    assert.equal(w.core.state.error.message, ERRORS[code]);
    assert.equal(w.posted('/api/voice/join').length, 0);
    assert.equal(FakePC.all.length, 0);
    w.core.clearError();
    assert.equal(w.core.state.status, 'idle');
  });
}

test('a browser without calls, or without https, says so', async () => {
  let w = await world(createVoiceCore, { noMic: true });
  await w.core.join(C1);
  assert.equal(w.core.state.error.code, 'unsupported');
  w = await world(createVoiceCore, { noMic: true, secure: false });
  await w.core.join(C1);
  assert.equal(w.core.state.error.code, 'insecure');
});

test('a full room is explained and the microphone is let go', async () => {
  const w = await world(createVoiceCore);
  w.handlers['/api/voice/join'] = () => { throw Object.assign(new Error('This room is full (8 people)'), { status: 409 }); };
  assert.equal(await w.core.join(C1), false);
  assert.equal(w.core.state.error.code, 'full');
  assert.equal(w.liveTracks(), 0);
  assert.equal(w.timers.active(), 0);
});

test('the server forgot us (restart, or we went quiet): it gets back in by itself, keeping the same session, without asking for the mic again', async () => {
  let inRoom = true;
  const w = await world(createVoiceCore, { state: () => (inRoom ? { inRoom: true, people: [{ id: 'u2', username: 'u2' }] } : { inRoom: false }) });
  await w.core.join(C1);
  const sid = w.core.state.sid;
  inRoom = false;
  await w.core.pushState();
  assert.equal(w.core.state.status, 'reconnecting');
  assert.equal(w.core.state.error.code, 'lost');
  inRoom = true;
  await w.timers.advance(1000);
  assert.equal(w.core.state.status, 'connected');
  assert.equal(w.core.state.error, null);
  assert.equal(w.posted('/api/voice/join').length, 2);
  assert.equal(w.posted('/api/voice/join')[1][1].sid, sid);
  assert.equal(w.gumCalls, 1);
});

test('a network failure while connected shows "reconnecting" and recovers on the next check-in', async () => {
  let down = false;
  const w = await world(createVoiceCore, { state: () => { if (down) throw Object.assign(new Error('offline'), { status: 0 }); return { inRoom: true, people: [{ id: 'u2', username: 'u2' }] }; } });
  await w.core.join(C1);
  down = true;
  await w.timers.advance(10000);
  assert.equal(w.core.state.status, 'reconnecting');
  down = false;
  await w.timers.advance(10000);
  assert.equal(w.core.state.status, 'connected');
  assert.equal(w.core.state.error, null);
});

test('being logged out, or removed from the circle, ends the call', async () => {
  let status = 401;
  const w = await world(createVoiceCore, { state: () => { throw Object.assign(new Error('no'), { status }); } });
  await w.core.join(C1);
  await w.core.pushState();
  assert.equal(w.core.state.status, 'idle');
  assert.equal(w.liveTracks(), 0);
  status = 403;
  await w.core.join(C1);
  await w.core.pushState();
  assert.equal(w.core.state.error.code, 'removed');
  assert.equal(w.liveTracks(), 0);
});

test('REGRESSION: a health check while the browser is still asking for the microphone does not look like a dropped call', async () => {
  const w = await world(createVoiceCore);
  const prompt = deferred();
  w.gum = () => prompt.promise;
  const joining = w.core.join(C1);
  await flush();
  assert.equal(w.core.state.status, 'requesting');
  w.core.checkHealth(); await flush();
  assert.equal(w.core.state.status, 'requesting');
  assert.equal(w.core.state.error, null);
  assert.equal(w.posted('/api/voice/state').length, 0);
  prompt.resolve(makeStream());
  assert.equal(await joining, true);
  assert.equal(w.core.state.status, 'connected');
});

test('REGRESSION: hanging up while the microphone prompt is open cancels the join, and a late "allow" is released', async () => {
  const w = await world(createVoiceCore);
  const prompt = deferred();
  w.gum = () => prompt.promise;
  const joining = w.core.join(C1);
  await flush();
  await w.core.leave();
  const late = makeStream(); w.streams.push(late);
  prompt.resolve(late);
  assert.equal(await joining, false);
  assert.equal(w.core.state.status, 'idle');
  assert.equal(w.posted('/api/voice/join').length, 0);
  assert.equal(late.getTracks()[0].stopped, true);
  assert.equal(w.timers.active(), 0);
});

test('a second tab taking over hangs this one up, quietly; a message for an old session is ignored', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  const sid = w.core.state.sid;
  w.core.onEvent({ k: 'replaced', sid: 'some-other-session' });
  assert.equal(w.core.state.status, 'connected');
  await w.core.onEvent({ k: 'replaced', sid });
  assert.equal(w.core.state.error.code, 'taken');
  assert.equal(w.liveTracks(), 0);
  assert.equal(w.posted('/api/voice/leave').length, 0);
});

test('one call at a time: moving to another circle hangs up the first, and only one microphone is ever live', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  await w.core.join(C2);
  assert.equal(w.core.state.circleId, 'c2');
  assert.deepEqual(w.posted('/api/voice/leave').map(([, b]) => b.circleId), ['c1']);
  assert.equal(w.liveTracks(), 1);
});

test('somebody leaving the room closes their connection', async () => {
  const w = await world(createVoiceCore, { join: withPeer });
  await w.core.join(C1); await flush();
  w.core.onEvent({ k: 'room', room: 'c1', people: [{ id: 'u2', username: 'u2' }] });
  assert.equal(FakePC.all[0].closed, true);
  assert.deepEqual(w.core.connections(), []);
});

test('the servers the site hands out (STUN and TURN) are the ones used for the connection', async () => {
  const ice = [{ urls: ['stun:s.example'] }, { urls: ['turn:t.example'], username: 'u', credential: 'c' }];
  const w = await world(createVoiceCore, { join: { ...withPeer, ice } });
  await w.core.join(C1);
  assert.deepEqual(FakePC.all[0].cfg.iceServers, ice);
});

test('signaling: an offer is answered; candidates that arrive early wait for it; messages for another session are ignored', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  const sid = w.core.state.sid;
  const base = { k: 'signal', room: 'c1', from: 'u1', fromSid: 'p1', toSid: sid };
  await w.core.onEvent({ ...base, data: { type: 'candidate', candidate: { c: 1 } } });
  assert.equal(FakePC.all.length, 0);                                            // only an offer starts a connection
  await w.core.onEvent({ ...base, toSid: 'someone-else', data: { type: 'offer', description: { type: 'offer', sdp: 's' } } });
  assert.equal(FakePC.all.length, 0);
  await w.core.onEvent({ ...base, data: { type: 'offer', description: { type: 'offer', sdp: 's' } } });
  assert.equal(FakePC.all.length, 1);
  await w.core.onEvent({ ...base, data: { type: 'candidate', candidate: { c: 2 } } });
  await flush();
  assert.equal(FakePC.all[0].added.length, 1);
  const answers = w.posted('/api/voice/signal').filter(([, b]) => b.data.type === 'answer');
  assert.equal(answers.length, 1);
  assert.equal(answers[0][1].to, 'u1');
});

test('signaling: when two offers cross, the person with the smaller id gives way and the other ignores the offer', async () => {
  // u2 (larger id) is impolite towards u1: it keeps its own offer.
  let w = await world(createVoiceCore, { me: 'u2', join: withPeer });
  await w.core.join(C1); await flush();
  await w.core.onEvent({ k: 'signal', room: 'c1', from: 'u1', fromSid: 'peer-sid-u1', toSid: w.core.state.sid, data: { type: 'offer', description: { type: 'offer', sdp: 'theirs' } } });
  assert.equal(FakePC.all[0].remoteDescription, null);
  // u0 (smaller id) is polite towards u1: it accepts theirs.
  w = await world(createVoiceCore, { me: 'u0', join: { peers: [peer('u1')], people: [{ id: 'u1', username: 'u1' }, { id: 'u0', username: 'u0' }] } });
  await w.core.join(C1); await flush();
  await w.core.onEvent({ k: 'signal', room: 'c1', from: 'u1', fromSid: 'peer-sid-u1', toSid: w.core.state.sid, data: { type: 'offer', description: { type: 'offer', sdp: 'theirs' } } });
  assert.equal(FakePC.all.at(-1).remoteDescription.sdp, 'theirs');
});

test('a person who rejoined (new session) gets a fresh connection, and the old one is closed', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  const sid = w.core.state.sid;
  const offer = (fromSid) => ({ k: 'signal', room: 'c1', from: 'u1', fromSid, toSid: sid, data: { type: 'offer', description: { type: 'offer', sdp: 's' } } });
  await w.core.onEvent(offer('p1'));
  await w.core.onEvent(offer('p2'));
  assert.equal(FakePC.all.length, 2);
  assert.equal(FakePC.all[0].closed, true);
  assert.equal(FakePC.all[1].closed, false);
  assert.equal(w.core.connections().length, 1);
});

test('a microphone that is unplugged mid-call mutes with an explanation, and pressing the button asks for it again', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  const track = w.streams[0].getAudioTracks()[0];
  track.readyState = 'ended'; track.onended();
  await flush();
  assert.equal(w.core.state.muted, true);
  assert.equal(w.core.state.error.code, 'busy');
  await w.core.toggleMic();
  assert.equal(w.gumCalls, 2);
  assert.equal(w.core.state.muted, false);
  assert.equal(w.core.state.error, null);
});

test('a person whose microphone is gone and will not come back can still hear: new people get a listen-only connection, and leaving cleans up', async () => {
  const w = await world(createVoiceCore);
  await w.core.join(C1);
  const track = w.streams[0].getAudioTracks()[0];
  track.readyState = 'ended'; track.onended();
  w.gum = async () => { throw Object.assign(new Error('x'), { name: 'NotFoundError' }); };
  await w.core.toggleMic();                                                      // try to get it back: nothing there
  assert.equal(w.core.state.error.code, 'nodevice');
  w.core.onEvent({ k: 'room', room: 'c1', people: [{ id: 'u1', username: 'u1', sid: 'peer-sid-u1' }, { id: 'u2', username: 'u2' }] });
  await w.timers.advance(6000);
  assert.equal(FakePC.all.length, 1);
  assert.equal(FakePC.all[0].tracks.length, 0);                                  // nothing of ours to send, but it is there to listen
  await w.core.leave();
  assert.ok(FakePC.all.every((p) => p.closed));
  assert.equal(w.timers.active(), 0);
});
