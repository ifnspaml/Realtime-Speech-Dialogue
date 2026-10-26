import test from 'node:test';
import assert from 'node:assert/strict';
import { EventMetrics, normalizeEvent, pcm16BytesToFloat32, sessionUpdate, modularStageTimings } from '../../frontend/realtime-protocol.js';
import { BoundedPCMQueue } from '../../frontend/audio.js';
import { base64FromArrayBuffer, base64ToBytes } from '../../frontend/vendor/hf-demo/ws/codec.js';

test('normalizes shared server events without discarding vendor payload', () => {
  const event = normalizeEvent({ type: 'session.created', session: { model: 'nemotron' } });
  assert.equal(event.backendEventType, 'session.created');
  assert.equal(event.session.model, 'nemotron');
});

test('session config keeps VAD controls specific to HF modular', () => {
  assert.ok(sessionUpdate({ mode: 'modular', instructions: 'Be concise' }).session.audio.input.turn_detection);
  assert.equal(sessionUpdate({ mode: 'nemotron', instructions: 'Be concise' }).session.audio.input.turn_detection, undefined);
  assert.equal(sessionUpdate({ mode: 'nemotron' }).session.audio.input.format.rate, 24000);
});

test('PCM16 little-endian samples decode to normalized floats', () => {
  const got = pcm16BytesToFloat32(new Uint8Array([0, 128, 255, 127, 0, 0]));
  assert.equal(got[0], -1);
  assert.ok(got[1] > 0.99);
  assert.equal(got[2], 0);
  assert.throws(() => pcm16BytesToFloat32(new Uint8Array([0])), /complete samples/);
});

test('base64 transport round-trips PCM bytes in original order', () => {
  const source = new Uint8Array([0, 1, 127, 128, 255, 42]);
  const encoded = base64FromArrayBuffer(source.buffer);
  assert.deepEqual([...base64ToBytes(encoded)], [...source]);
});

test('latency uses common event receipt times and leaves absent stages unavailable', () => {
  const metrics = new EventMetrics();
  metrics.apply({ type: 'input_audio_buffer.speech_started' }, 10);
  metrics.apply({ type: 'input_audio_buffer.speech_stopped' }, 110);
  metrics.apply({ type: 'response.created' }, 160);
  metrics.apply({ type: 'response.output_audio.delta' }, 360);
  metrics.apply({ type: 'response.done', response: { status: 'completed' } }, 660);
  assert.equal(metrics.snapshot().speechStartToFirstAudioMs, 350);
  assert.equal(metrics.snapshot().speechEndToFirstAudioMs, 250);
  assert.equal(metrics.snapshot().responseDurationMs, 500);
  assert.equal(metrics.snapshot().speechEndToResponseEndMs, 550);
  assert.equal(metrics.snapshot().sttLatencyMs, undefined);
});

test('playback queue stays bounded, accepts chunks in order, and clears on interruption', () => {
  const queue = new BoundedPCMQueue({ sampleRate: 24000, maxMs: 100 });
  assert.equal(queue.enqueue(1200), true);
  assert.equal(queue.enqueue(1200), true);
  assert.equal(queue.queuedMs, 100);
  assert.equal(queue.enqueue(1), false);
  queue.reportQueuedMs(20);
  assert.equal(queue.queuedMs, 20);
  queue.clear();
  assert.equal(queue.queuedMs, 0);
});

test('overlapping audio remains negative and completed-only transcripts get timestamps', () => {
  const metrics = new EventMetrics();
  metrics.apply({ type: 'input_audio_buffer.speech_started' }, 0);
  metrics.apply({ type: 'conversation.item.input_audio_transcription.completed' }, 10);
  metrics.apply({ type: 'response.output_audio_transcript.done' }, 20);
  metrics.apply({ type: 'response.output_audio.delta' }, 50);
  metrics.apply({ type: 'input_audio_buffer.speech_stopped' }, 100);
  assert.equal(metrics.snapshot().speechEndToFirstAudioMs, -50);
  assert.equal(metrics.snapshot().firstTranscript, 10);
  assert.equal(metrics.snapshot().firstAssistantText, 20);
});

test('HF metadata exposes measured durations without inventing missing stages', () => {
  const event = { response: { metadata: { 'speech_to_speech.turn_latency': JSON.stringify({stt_s: 0.067, llm_s: 1.6, tts_ttfa_s: 0.127}) } } };
  assert.deepEqual(modularStageTimings(event), { sttMs: 67, llmMs: 1600, ttsFirstAudioMs: 127 });
  assert.equal(modularStageTimings({}), null);
  assert.equal(modularStageTimings({ response: { metadata: { 'speech_to_speech.turn_latency': 'invalid' } } }), null);
});
