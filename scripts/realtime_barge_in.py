#!/usr/bin/env python3
"""Inject a second WAV while receiving real assistant audio; retain raw evidence."""
import argparse
import asyncio
import base64
import json
import time
import wave
from array import array
from pathlib import Path
import websockets
from scripts.realtime_wav import RATE, load_pcm, sanitized, session_update


async def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    first = load_pcm(args.wav)
    interrupt = load_pcm(args.interrupt_wav)
    first_audio = asyncio.Event()
    ready = asyncio.Event()
    finished = asyncio.Event()
    audio = bytearray()
    report = {'backend': args.backend, 'measurement': 'real', 'status': 'FAIL',
              'user_turns': [], 'responses': [], 'second_speech_started': False}
    started = time.monotonic()
    elapsed = lambda: (time.monotonic() - started) * 1000
    async with websockets.connect(args.url, open_timeout=10, max_size=4_000_000, max_queue=16, proxy=None) as ws:
        async def receive():
            with (args.output / 'events.jsonl').open('w') as events:
                async for raw in ws:
                    event = json.loads(raw)
                    events.write(json.dumps({'received_ms': elapsed(), 'event': sanitized(event)}) + '\n'); events.flush()
                    kind = event['type']
                    if kind == 'error': raise RuntimeError(str(event))
                    if kind == 'session.created': await ws.send(json.dumps(session_update(args.backend)))
                    if kind == 'session.updated': ready.set()
                    if kind == 'input_audio_buffer.speech_started' and first_audio.is_set():
                        report['second_speech_started'] = True
                        report['second_speech_started_ms'] = elapsed()
                    if kind == 'conversation.item.input_audio_transcription.completed':
                        report['user_turns'].append(event.get('transcript', ''))
                    if kind == 'response.output_audio_transcript.delta' and event.get('delta'):
                        report['assistant_text_seen'] = True
                    if kind == 'response.output_audio_transcript.done' and report['second_speech_started'] and len(report['user_turns']) >= 2 and event.get('transcript'):
                        report['second_assistant_transcript'] = event['transcript']
                        if args.backend == 'nemotron': finished.set()
                    if kind == 'response.output_audio.delta':
                        chunk = base64.b64decode(event['delta'])
                        audio.extend(chunk)
                        if args.backend == 'nemotron' and (not report['user_turns'] or not report.get('assistant_text_seen') or max((abs(v) for v in array('h', chunk)), default=0) < 66): continue
                        if not first_audio.is_set(): report['first_audio_ms'] = elapsed()
                        first_audio.set()
                    if kind == 'response.done':
                        report['responses'].append({'at_ms': elapsed(), 'response': event.get('response')})
                        if report['second_speech_started'] and len(report['user_turns']) >= 2: finished.set()
        receiver = asyncio.create_task(receive())
        try:
            await asyncio.wait_for(ready.wait(), 20)
            chunk_bytes = RATE * (80 if args.backend == 'nemotron' else 40) // 1000 * 2
            second_offset = None
            send_start = time.monotonic()
            total_samples = int(RATE * args.duration)
            for offset in range(0, total_samples * 2, chunk_bytes):
                if second_offset is None and first_audio.is_set():
                    second_offset = offset
                    report['barge_in_sent_ms'] = elapsed()
                if second_offset is None:
                    chunk = first[offset:offset + chunk_bytes]
                else:
                    second = offset - second_offset
                    chunk = interrupt[second:second + chunk_bytes]
                chunk += b'\0' * (chunk_bytes - len(chunk))
                await ws.send(json.dumps({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(chunk).decode()}))
                if finished.is_set(): break
                if receiver.done(): await receiver; raise ConnectionError('Backend ended before barge-in completed')
                await asyncio.sleep(max(0, send_start + (offset + chunk_bytes) / (RATE * 2) - time.monotonic()))
            await asyncio.wait_for(finished.wait(), 30)
            report['status'] = 'PASS' if any(r['response'].get('status') == 'cancelled' for r in report['responses']) else 'PARTIAL'
            report['limitation'] = 'PASS requires observed server cancellation. PARTIAL means second speech and a subsequent completion were observed without cancellation proof.'
        finally:
            receiver.cancel(); await asyncio.gather(receiver, return_exceptions=True)
            with wave.open(str(args.output / 'response.wav'), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(audio)
            (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--backend', choices=['modular', 'nemotron'], required=True)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--interrupt-wav', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=50)
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(run(args), 100))
