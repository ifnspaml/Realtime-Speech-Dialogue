import test from 'node:test';
import assert from 'node:assert/strict';
import { LocalInputRecording, microphoneConstraints, continuousStreamStalled } from '../../frontend/audio.js';

test('local input recording is opt-in and preserves PCM byte order in a valid WAV', () => {
  const recording = new LocalInputRecording();
  const pcm = new Uint8Array([1, 0, 255, 127, 0, 128]);
  recording.append(pcm.buffer);
  assert.equal(recording.bytes, 0);
  recording.start();
  recording.append(pcm.buffer.slice(0, 2));
  recording.append(pcm.buffer.slice(2));
  pcm.fill(0); // Recording owns a copy, independent of transferred capture buffers.
  const wav = recording.wav();
  const header = new DataView(wav.buffer);
  assert.equal(new TextDecoder().decode(wav.subarray(0, 4)), 'RIFF');
  assert.equal(new TextDecoder().decode(wav.subarray(8, 12)), 'WAVE');
  assert.equal(header.getUint32(24, true), 24000);
  assert.equal(header.getUint16(22, true), 1);
  assert.equal(header.getUint16(34, true), 16);
  assert.equal(header.getUint32(4, true), wav.length - 8);
  assert.equal(header.getUint32(40, true), 6);
  assert.deepEqual([...wav.subarray(44)], [1, 0, 255, 127, 0, 128]);
  recording.stop();
  recording.append(new Int16Array([42]).buffer);
  assert.equal(recording.bytes, 6);
});

test('local recording stops exactly at its cap, and rearming discards the previous recording', () => {
  const recording = new LocalInputRecording({ sampleRate: 10, maxSeconds: 0.3 });
  recording.start();
  recording.append(new Int16Array([1, 2, 3, 4, 5]).buffer);
  assert.equal(recording.seconds, 0.3);
  assert.equal(recording.active, false);
  assert.deepEqual([...new Int16Array(recording.wav().buffer, 44)], [1, 2, 3]);
  recording.append(new Int16Array([9]).buffer);
  assert.equal(recording.bytes, 6);
  recording.start();
  assert.equal(recording.bytes, 0);
  assert.throws(() => recording.append(new Uint8Array([1]).buffer), TypeError);
  assert.throws(() => new LocalInputRecording({ maxSeconds: 31 }), RangeError);
});

test('microphone comparison profiles retain current defaults and allow all processing to be disabled', () => {
  assert.deepEqual(microphoneConstraints(), { echoCancellation: true, noiseSuppression: true, autoGainControl: true });
  assert.deepEqual(microphoneConstraints('echo'), { echoCancellation: true, noiseSuppression: false, autoGainControl: false });
  assert.deepEqual(microphoneConstraints('raw'), { echoCancellation: false, noiseSuppression: false, autoGainControl: false });
});

test('continuous PCM watchdog tolerates initial startup and short gaps, then detects silent stalls', () => {
  assert.equal(continuousStreamStalled({ startedAt: null, lastAudioAt: null, now: 50000 }), false);
  assert.equal(continuousStreamStalled({ startedAt: 1000, lastAudioAt: null, now: 10999 }), false);
  assert.equal(continuousStreamStalled({ startedAt: 1000, lastAudioAt: null, now: 11000 }), true);
  assert.equal(continuousStreamStalled({ startedAt: 1000, lastAudioAt: 5000, now: 9999 }), false);
  assert.equal(continuousStreamStalled({ startedAt: 1000, lastAudioAt: 5000, now: 10000 }), true);
});
