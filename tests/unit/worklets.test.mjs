import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function loadWorklet(file, sampleRate = 48000, options = {}) {
  let Processor;
  const messages = [];
  const context = { sampleRate, currentTime: 0, Float32Array, Int16Array, ArrayBuffer, Math, Number, Map, Set,
    AudioWorkletProcessor: class { constructor() { this.port = { postMessage: (message) => messages.push(message) }; } },
    registerProcessor: (_, constructor) => { Processor = constructor; },
  };
  vm.runInNewContext(readFileSync(new URL(`../../frontend/vendor/hf-demo/worklets/${file}`, import.meta.url), 'utf8'), context);
  return { processor: new Processor(options), messages };
}

test('official playback renders ordered PCM, bounds queued samples, and clears', () => {
  const { processor, messages } = loadWorklet('audio-playback.js');
  const output = new Float32Array(128);
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(24000).fill(0.25), key: 'a' } });
  processor.process([], [[output]]);
  assert.ok(output.slice(40).every(value => Math.abs(value - 0.25) < 0.01));
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(24000 * 8), key: 'overflow' } });
  assert.ok(messages.some(message => message.kind === 'overflow'));
  processor.port.onmessage({ data: { kind: 'clear', clearId: 1 } });
  processor.process([], [[output]]);
  processor.process([], [[output]]);
  assert.equal(processor._queuedSamples(), 0);
  assert.ok(output.every(value => value === 0));
});

test('playback accepts a bounded sentence burst and rejects limits above thirty seconds', () => {
  const { processor, messages } = loadWorklet('audio-playback.js');
  processor.port.onmessage({ data: { kind: 'config', maxQueuedMs: 30000 } });
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(24000 * 12), key: 'sentence' } });
  assert.equal(processor._queuedSamples(), 24000 * 12);
  processor.port.onmessage({ data: { kind: 'config', maxQueuedMs: Infinity } });
  assert.equal(processor._maxQueuedMs, 30000);
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(24000 * 19), key: 'overflow' } });
  assert.ok(messages.some(message => message.kind === 'overflow'));
});

test('capture emits ordered 24kHz PCM16 chunks at both browser input rates', () => {
  for (const rate of [48000, 44100]) {
    const { processor, messages } = loadWorklet('mic-capture.js', rate, { processorOptions: { targetRate: 24000, chunkMs: 40 } });
    processor._ingest(new Float32Array(Math.ceil(rate * 0.04)).fill(0.5));
    processor._ingest(new Float32Array(Math.ceil(rate * 0.04)).fill(-0.5));
    const pcm = messages.filter(message => message instanceof ArrayBuffer);
    assert.equal(pcm.length, 2);
    assert.equal(pcm[0].byteLength, 1920);
    assert.ok(new DataView(pcm[0]).getInt16(0, true) > 0);
    assert.ok(new DataView(pcm[1]).getInt16(100, true) < 0);
    assert.ok(processor._scratch.length < Math.ceil(rate * 0.04));
  }
});

test('capture preserves a quiet speech onset after silence without a noise gate', () => {
  for (const rate of [48000, 44100]) {
    const { processor, messages } = loadWorklet('mic-capture.js', rate, { processorOptions: { targetRate: 24000, chunkMs: 80 } });
    const silenceSamples = Math.round(rate * 0.16);
    const quietSamples = Math.round(rate * 0.24);
    const input = new Float32Array(silenceSamples + quietSamples);
    for (let i = 0; i < quietSamples; i++) input[silenceSamples + i] = 0.01 * Math.sin(2 * Math.PI * 440 * i / rate);
    // Real worklets receive 128-frame blocks, not one full utterance.
    for (let offset = 0; offset < input.length; offset += 128) processor.process([[input.slice(offset, offset + 128)]]);
    const chunks = messages.filter(message => message instanceof ArrayBuffer);
    assert.equal(chunks.length, 5);
    assert.ok(new Int16Array(chunks[0]).every(value => value === 0));
    assert.ok(new Int16Array(chunks[1]).every(value => value === 0));
    for (const chunk of chunks.slice(2)) {
      const samples = new Int16Array(chunk);
      assert.ok(samples.some(value => Math.abs(value) > 250));
      assert.ok(samples.slice(1, 40).some(value => Math.abs(value) > 200), 'First quiet waveform samples must survive');
    }
  }
});

test('playback resamples contiguous chunks without losing chunk boundaries', () => {
  const { processor } = loadWorklet('audio-playback.js', 24000);
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(128).fill(0.2), key: 'a' } });
  processor.port.onmessage({ data: { kind: 'audio', samples: new Float32Array(128).fill(-0.2), key: 'b' } });
  const first = new Float32Array(128), second = new Float32Array(128);
  processor.process([], [[first]]); processor.process([], [[second]]);
  assert.ok(first[80] > 0); assert.ok(second[80] < 0);
  assert.equal(processor._queuedSamples(), 0);
});
