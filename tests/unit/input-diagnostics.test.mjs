import test from 'node:test';
import assert from 'node:assert/strict';
import { PCMInputDiagnostics } from '../../frontend/audio.js';

function pcm(values) {
  const buffer = new ArrayBuffer(values.length * 2);
  const view = new DataView(buffer);
  values.forEach((value, index) => view.setInt16(index * 2, value, true));
  return buffer;
}

test('silent uploaded PCM counts transport duration without claiming speech', () => {
  const stats = new PCMInputDiagnostics();
  stats.markSent(stats.observe(new ArrayBuffer(48000)));
  assert.deepEqual(stats.snapshot(), { capturedSeconds: 1, sentSeconds: 1,
    signalSeconds: 0, rmsDbfs: null, peak: 0, clippedSamples: 0 });
});

test('input levels decode signed little-endian PCM and distinguish capture from send', () => {
  const stats = new PCMInputDiagnostics({ sampleRate: 4 });
  const buffer = pcm([16384, -16384, 16384, -16384]);
  const original = [...new Uint8Array(buffer)];
  stats.observe(buffer);
  assert.deepEqual([...new Uint8Array(buffer)], original, 'Diagnostics must not change uploaded audio');
  let result = stats.snapshot();
  assert.equal(result.capturedSeconds, 1);
  assert.equal(result.sentSeconds, 0);
  assert.equal(result.signalSeconds, 1);
  assert.equal(result.peak, 0.5);
  assert.ok(Math.abs(result.rmsDbfs + 6.020599913) < 1e-8);
  stats.markSent(4);
  assert.equal(stats.snapshot().sentSeconds, 1);
  assert.throws(() => stats.markSent(1), RangeError);
});

test('quiet signal and clipping remain observable, and microphone restarts reset counters', () => {
  const stats = new PCMInputDiagnostics({ sampleRate: 2 });
  stats.observe(pcm([1, -1]));
  assert.equal(stats.snapshot().signalSeconds, 0);
  assert.ok(stats.snapshot().rmsDbfs < -50);
  stats.observe(pcm([-32768, 32767]));
  assert.equal(stats.snapshot().clippedSamples, 2);
  assert.equal(stats.snapshot().signalSeconds, 1);
  stats.reset();
  assert.equal(stats.snapshot().capturedSeconds, 0);
  assert.equal(stats.snapshot().clippedSamples, 0);
  assert.throws(() => stats.observe(new ArrayBuffer(1)), TypeError);
  assert.throws(() => new PCMInputDiagnostics({ sampleRate: 0 }), RangeError);
});
