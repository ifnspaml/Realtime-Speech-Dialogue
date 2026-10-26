import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { EventMetrics } from '../../frontend/realtime-protocol.js';

test('synthetic Moshi fixture preserves continuous session and unsupported features', async () => {
  const source = await readFile(new URL('../fixtures/synthetic/moshi.events.jsonl', import.meta.url), 'utf8');
  const records = source.trim().split('\n').map(JSON.parse);
  const events = records.map(record => record.event);
  const metrics = new EventMetrics();
  for (const record of records) metrics.apply(record.event, record.received_ms);
  assert.equal(events[0].type, 'session.created');
  assert.equal(events[0].session.capabilities.user_transcript, false);
  assert.ok(events.some(e => e.type === 'response.output_audio_transcript.delta' && e.delta));
  assert.ok(events.some(e => e.audio_metadata?.bytes > 0));
  assert.equal(events.at(-1).type, 'session.end');
  assert.equal(events.at(-1).origin, 'moshi_adapter');
  assert.ok(!events.some(e => e.type === 'response.done' || e.type.includes('speech_started') || e.type.includes('input_audio_transcription')));
  assert.equal(metrics.snapshot().speechEndToFirstAudioMs, null);
});
