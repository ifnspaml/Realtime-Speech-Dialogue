import test from 'node:test';
import assert from 'node:assert/strict';
import { BACKENDS, backendSessionUpdate } from '../../frontend/backends.js';

test('Moshi capabilities exclude unsupported user transcripts and configuration', () => {
  assert.equal(BACKENDS.moshi.userTranscript, false);
  assert.equal(BACKENDS.moshi.speechBoundaries, false);
  assert.equal(BACKENDS.moshi.turnDone, false);
  assert.equal(BACKENDS.moshi.chunkMs, 80);
  const update = backendSessionUpdate('moshi', 'Must not be sent');
  assert.equal(update.session.instructions, undefined);
  assert.equal(update.session.audio.input.turn_detection, undefined);
  assert.equal(update.session.audio.output.format.rate, 24000);
});

test('Existing backends retain instructions and HF-only VAD', () => {
  assert.equal(backendSessionUpdate('nemotron', 'Hello').session.instructions, 'Hello');
  assert.equal(backendSessionUpdate('modular', 'Hello').session.audio.input.turn_detection.type, 'server_vad');
});
