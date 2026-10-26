import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { EventMetrics, normalizeEvent } from '../../frontend/realtime-protocol.js';

for (const fixture of ['hf_realtime_session.jsonl', 'nemotron_realtime_session.jsonl']) {
  test(`replays ${fixture} through the common client state`, async () => {
    const source = await readFile(new URL(`../fixtures/${fixture}`, import.meta.url), 'utf8');
    const events = source.trim().split('\n').map((line) => normalizeEvent(JSON.parse(line)));
    const metrics = new EventMetrics();
    events.forEach((event, index) => metrics.apply(event, index * 10));
    assert.equal(events[0].type, 'session.created');
    assert.equal(events.at(-1).response.status, 'completed');
    assert.equal(metrics.snapshot().response, 'completed');
    assert.equal(metrics.snapshot().firstAssistantAudio, 100);
    assert.equal(events.filter((event) => event.type === 'response.output_audio_transcript.delta').length, 1);
  });
}
