#!/usr/bin/env python3
"""Drive native or adapted Moshi with prerecorded WAV; capture real evidence."""
import argparse
import asyncio
import base64
import hashlib
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sphn
from aiohttp import ClientSession, WSMsgType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.moshi.codec import Codec, FRAME, RATE
def write_wav(path, pcm, rate=RATE):
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)


def load_audio(path):
    """Convert mono PCM16 test input to the model's verified 24 kHz contract."""
    with wave.open(str(path)) as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2: raise ValueError('Expected mono PCM16 WAV')
        rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if rate == RATE: return raw
    samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
    samples = sphn.resample(samples, rate, RATE)
    return np.clip(np.rint(samples * 32768), -32768, 32767).astype('<i2').tobytes()


async def run(args):
    """Pace one recorded input stream and keep transport and quality evidence separate."""
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {'status': 'FAIL', 'measurement': args.measurement, 'backend': 'moshi', 'transport': 'native' if args.native else 'adapter',
               'user_transcripts': {}, 'assistant_transcripts': {}, 'speech_boundaries': 'N/A', 'response_scope': 'session'}
    audio, text, uploaded = [], [], []
    started = time.perf_counter()
    summary['started_unix'] = time.time()
    def elapsed(): return (time.perf_counter() - started) * 1000
    records = (args.output / 'events.jsonl').open('w')
    packets = (args.output / 'native-packets.jsonl').open('w')
    sends = (args.output / 'send-timeline.jsonl').open('w')
    input_samples = 0
    packet_sequence = {'input': 0, 'output': 0}
    def capture_packet(direction, packet):
        sequence = packet_sequence[direction]
        packet_sequence[direction] += 1
        packets.write(json.dumps({'direction': direction, 'sequence': sequence, 'at_ms': elapsed(),
                                  'packet': base64.b64encode(packet).decode()}) + '\n')
    async def send_pcm(ws, codec, chunk, label, target=None):
        nonlocal input_samples
        at = elapsed()
        sends.write(json.dumps({'at_ms': at, 'target_ms': target, 'label': label,
                                'sample_start': input_samples, 'samples': len(chunk) // 2}) + '\n')
        input_samples += len(chunk) // 2
        uploaded.append(chunk)
        if args.native:
            for packet in codec.encode(chunk):
                capture_packet('input', packet)
                await ws.send_bytes(packet)
        else:
            await ws.send_json({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(chunk).decode()})
    try:
        async with ClientSession() as client:
            async with client.ws_connect(args.url, max_msg_size=1024 * 1024) as ws:
                codec = Codec()
                if args.native:
                    handshake = await asyncio.wait_for(ws.receive(), timeout=10)
                    assert handshake.type == WSMsgType.BINARY and handshake.data == b'\x00', 'Invalid native handshake'
                    preamble = bytes(round(RATE * args.preamble_ms / 1000) * 2)
                    if preamble:
                        await send_pcm(ws, codec, preamble, 'preamble')
                else:
                    while True:
                        message = await asyncio.wait_for(ws.receive(), timeout=10)
                        event = json.loads(message.data)
                        records.write(json.dumps({'received_ms': elapsed(), 'event': event}) + '\n'); records.flush()
                        if event['type'] == 'session.created': break
                        if event['type'] == 'error': raise RuntimeError(event)
                    await ws.send_json({'type': 'session.update', 'session': {'audio': {'input': {'format': {'type': 'audio/pcm', 'rate': RATE}}}}})
                summary['connected_ms'] = elapsed()

                async def receive():
                    async for message in ws:
                        if args.native:
                            if message.type != WSMsgType.BINARY: break
                            packet = message.data
                            capture_packet('output', packet)
                            if packet[0] == 1:
                                raw = codec.decode(packet)
                                event = {'type': 'response.output_audio.delta', 'delta': base64.b64encode(raw).decode(), 'origin': 'native_binary_capture'}
                            elif packet[0] == 2:
                                event = {'type': 'response.output_audio_transcript.delta', 'delta': packet[1:].decode(), 'origin': 'native_binary_capture'}
                            else: raise ValueError('Unknown native frame')
                        else:
                            if message.type != WSMsgType.TEXT: break
                            event = json.loads(message.data)
                        at = elapsed()
                        if event['type'] == 'response.output_audio.delta':
                            raw = base64.b64decode(event['delta'])
                            event = {key: value for key, value in event.items() if key != 'delta'}
                            event['audio_metadata'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                            if raw:
                                audio.append(raw)
                                summary.setdefault('first_pcm_received_ms', at)
                                if np.count_nonzero(np.frombuffer(raw, dtype='<i2')): summary.setdefault('first_nonzero_pcm_received_ms', at)
                        elif event['type'] == 'response.output_audio_transcript.delta':
                            text.append(event.get('delta', '')); summary.setdefault('first_assistant_text_ms', at)
                        elif event['type'] == 'session.end': summary['session_end_stats'] = event.get('stats')
                        elif event['type'] == 'error': raise RuntimeError(event)
                        records.write(json.dumps({'received_ms': at, 'event': event}) + '\n'); records.flush()

                receiver = asyncio.create_task(receive())
                try:
                    paths = [(None, bytes(round(RATE * args.leading_silence) * 2))] if args.leading_silence else []
                    paths += [(path, load_audio(path) + bytes(int(RATE * args.silence) * 2)) for path in args.wav]
                    # Continue sending paced silence after speech: native Moshi
                    # generation advances only as user-stream frames arrive.
                    for index, (path, raw) in enumerate(paths):
                        raw += bytes((-len(raw)) % (FRAME * 2))
                        turn_started = time.perf_counter()
                        for offset in range(0, len(raw), FRAME * 2):
                            chunk = raw[offset:offset + FRAME * 2]
                            target = (turn_started - started + offset / (RATE * 2)) * 1000
                            sent_at = time.perf_counter()
                            await send_pcm(ws, codec, chunk, str(path) if path else 'leading_silence', target)
                            deadline = turn_started + (offset + len(chunk)) / (RATE * 2)
                            if args.pacing == 'no-catch-up':
                                deadline = sent_at + len(chunk) / (RATE * 2)
                            await asyncio.sleep(max(0, deadline - time.perf_counter()))
                            if receiver.done(): await receiver
                    if args.native: await ws.close()
                    else:
                        await ws.send_json({'type': 'session.close'})
                        await asyncio.wait_for(receiver, timeout=10)
                finally:
                    receiver.cancel(); await asyncio.gather(receiver, return_exceptions=True)
        combined = b''.join(audio)
        assistant = ''.join(text).strip()
        assert assistant, 'No real assistant text observed'
        assert combined and np.count_nonzero(np.frombuffer(combined, dtype='<i2')), 'No nonzero model audio observed'
        # Transport PASS means text/nonzero PCM arrived; it is not semantic evaluation.
        summary.update(status='PASS', assistant_transcripts={'session': assistant}, output_samples=len(combined) // 2,
                       duration_ms=elapsed(), input_wavs=[str(path) for path in args.wav], input_samples=input_samples,
                       prompt_label=args.prompt_id, semantic_evaluation='NOT RUN', pacing=args.pacing,
                       leading_silence_seconds=args.leading_silence, trailing_silence_seconds=args.silence,
                       preamble_ms=args.preamble_ms if args.native else 80,
                       verdicts={'transport': 'PASS', 'input_integrity': 'NOT TESTED', 'answer_relevance': 'NOT TESTED',
                                 'answer_correctness': 'NOT TESTED', 'output_decode': 'PARTIAL', 'playback_listening': 'NOT TESTED'})
    except Exception as error:
        summary['error'] = repr(error)
        raise
    finally:
        records.close()
        packets.close()
        sends.close()
        write_wav(args.output / 'client-pcm-24k.wav', b''.join(uploaded))
        (args.output / 'inputs.json').write_text(json.dumps([
            {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in args.wav], indent=2) + '\n')
        with wave.open(str(args.output / 'response.wav'), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(b''.join(audio))
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--wav', type=Path, nargs='+', required=True)
    parser.add_argument('--silence', type=float, default=15)
    parser.add_argument('--leading-silence', type=float, default=0)
    parser.add_argument('--preamble-ms', type=float, choices=[0, 80], default=80)
    parser.add_argument('--pacing', choices=['deadline', 'no-catch-up'], default='deadline')
    parser.add_argument('--prompt-id', choices=['capital', 'greeting', 'microphone', 'unknown'], default='unknown')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--measurement', choices=['real', 'synthetic', 'replay'], default='real')
    asyncio.run(run(parser.parse_args()))
