#!/usr/bin/env python3
"""Replay mono PCM WAV files over either official realtime WebSocket API."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import time
import wave
from pathlib import Path

RATE = 24000


def load_pcm(path: Path, rate: int = RATE) -> bytes:
    """Validate PCM16 and perform actual band-limited sample-rate conversion."""
    import numpy as np
    from scipy.signal import resample_poly

    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError("Input must be uncompressed mono PCM16 WAV")
        source_rate = wav.getframerate()
        data = wav.readframes(wav.getnframes())
    if not data:
        raise ValueError("Input WAV is empty")
    if source_rate == rate:
        return data
    common = math.gcd(source_rate, rate)
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    converted = resample_poly(samples, rate // common, source_rate // common)
    return np.clip(np.rint(converted), -32768, 32767).astype("<i2").tobytes()


def session_update(backend: str) -> dict:
    session = {
        "type": "realtime", "instructions": "Answer briefly in English.", "tools": [],
        "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE}},
                  "output": {"format": {"type": "audio/pcm", "rate": RATE}}},
    }
    if backend != "nemotron":
        session["audio"]["input"]["turn_detection"] = {"type": "server_vad", "interrupt_response": True}
    return {"type": "session.update", "session": session}


def sanitized(event: dict) -> dict:
    """Keep schema and transcripts; replace bulky audio with reproducible metadata."""
    result = dict(event)
    if event.get("type") == "response.output_audio.delta" and isinstance(event.get("delta"), str):
        raw = base64.b64decode(event["delta"], validate=True)
        result["delta"] = ""
        result["audio_metadata"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return result


async def run(args) -> dict:
    import websockets

    pcm = load_pcm(args.wav)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'failure.json').unlink(missing_ok=True)
    started = time.monotonic()
    times, event_types, audio, users, assistants = {}, [], bytearray(), {}, {}
    summary = {"backend": args.backend, "measurement": "synthetic" if args.backend == "mock" else "real",
               "input_rate": RATE, "input_samples": len(pcm) // 2, "status": "FAIL"}
    created, updated, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    turn_seen = False
    response_ids = set()
    first_audio_event = asyncio.Event()
    current_turn = 0

    def elapsed():
        return (time.monotonic() - started) * 1000

    async with websockets.connect(args.url, open_timeout=args.connect_timeout, max_size=4_000_000,
                                  max_queue=16, write_limit=65536, proxy=None) as ws:
        times["connected_ms"] = elapsed()
        summary['connected_ms'] = times['connected_ms']
        async def receive():
            nonlocal turn_seen
            with (args.output / "events.jsonl").open("w") as events:
                async for message in ws:
                    event = json.loads(message)
                    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                        raise ValueError("Malformed realtime event")
                    kind = event["type"]
                    event_types.append(kind)
                    events.write(json.dumps({"received_ms": elapsed(), "event": sanitized(event)}) + "\n")
                    events.flush()
                    if kind == "error":
                        raise RuntimeError(json.dumps(event.get("error", event)))
                    if kind == "session.created": created.set()
                    if kind == "session.updated": updated.set()
                    if kind == "input_audio_buffer.speech_started":
                        turn_seen = True
                        times.setdefault("speech_start_ms", elapsed())
                    if kind == "input_audio_buffer.speech_stopped": times.setdefault("speech_end_ms", elapsed())
                    if kind.startswith("conversation.item.input_audio_transcription"):
                        turn_seen = True
                        times.setdefault("first_user_text_ms", elapsed())
                        key = event.get("item_id", "user")
                        if args.backend == 'nemotron': key = f'{current_turn}:{key}'
                        users[key] = event.get("transcript", users.get(key, "") + event.get("delta", ""))
                    if kind == "response.created" and turn_seen:
                        response_ids.add(event.get("response", {}).get("id"))
                        times.setdefault('response_start_ms', elapsed())
                    relevant = turn_seen and (not response_ids or event.get("response_id", event.get("response", {}).get("id")) in response_ids)
                    if relevant and kind.startswith("response.output_audio_transcript"):
                        times.setdefault("first_assistant_text_ms", elapsed())
                        key = event.get("item_id", "assistant")
                        if args.backend == 'nemotron': key = f'{current_turn}:{key}'
                        assistants[key] = event.get("transcript", assistants.get(key, "") + event.get("delta", ""))
                        if args.backend == 'nemotron' and kind.endswith('.done') and event.get('transcript'):
                            times['assistant_text_end_ms'] = elapsed()
                            completed.set()
                    if kind == "response.output_audio.delta":
                        raw = base64.b64decode(event["delta"], validate=True)
                        if len(raw) % 2: raise ValueError("Incomplete PCM16 output sample")
                        audio.extend(raw)
                        if relevant:
                            times.setdefault("first_audio_received_ms", elapsed())
                            first_audio_event.set()
                    if kind == 'session.end': summary['session_end_stats'] = event.get('stats')
                    if kind == "response.done" and (relevant or args.backend == 'nemotron'):
                        summary["response_status"] = event.get("response", {}).get("status", "completed")
                        times["response_end_ms"] = elapsed()
                        completed.set()

        receiver = asyncio.create_task(receive())
        async def wait_event(event, timeout):
            waiter = asyncio.create_task(event.wait())
            try:
                done, _ = await asyncio.wait({waiter, receiver}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                if event.is_set(): return
                if receiver in done:
                    await receiver
                    raise ConnectionError("Backend disconnected before the required event")
                if waiter not in done: raise TimeoutError("Timed out waiting for a required realtime event")
            finally:
                waiter.cancel()

        try:
            await wait_event(created, args.event_timeout)
            await ws.send(json.dumps(session_update(args.backend)))
            await wait_event(updated, args.event_timeout)
            async def cancel_after_audio():
                await wait_event(first_audio_event, args.response_timeout)
                await ws.send(json.dumps({"type": "response.cancel"}))
                summary["cancel_sent"] = True
            tail = args.silence if args.silence is not None else (20 if args.backend == "nemotron" else 2)
            chunk_ms = args.chunk_ms or (80 if args.backend == "nemotron" else 40)
            chunk_bytes = RATE * chunk_ms // 1000 * 2
            summary["turns"] = []
            clips = [args.wav] + getattr(args, 'next_wav', [])
            for turn_number, clip in enumerate(clips, 1):
                current_turn = turn_number
                completed.clear(); first_audio_event.clear(); response_ids.clear()
                turn_seen = False
                times.clear(); times['turn_sent_ms'] = elapsed()
                user_before, assistant_before = set(users), set(assistants)
                audio_before = len(audio)
                interrupter = asyncio.create_task(cancel_after_audio()) if args.interrupt else None
                data = load_pcm(clip) + b"\0\0" * int(RATE * tail)
                send_start = time.monotonic()
                for offset in range(0, len(data), chunk_bytes):
                    await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(data[offset:offset + chunk_bytes]).decode()}))
                    await asyncio.sleep(max(0, send_start + (offset + chunk_bytes) / (RATE * 2) - time.monotonic()))
                if args.backend == 'nemotron' and turn_number == len(clips):
                    # NVIDIA's response.done is session scoped, not an utterance boundary.
                    await ws.send(json.dumps({'type': 'session.close'}))
                await wait_event(completed, args.response_timeout)
                user_turn = {key: value for key, value in users.items() if key not in user_before}
                assistant_turn = {key: value for key, value in assistants.items() if key not in assistant_before}
                status = "PASS" if len(audio) > audio_before and any(user_turn.values()) and any(assistant_turn.values()) else "PARTIAL"
                if args.interrupt:
                    await interrupter
                    if summary.get("response_status") != "cancelled": status = "FAIL"
                summary['turns'].append({'turn': turn_number, 'status': status, 'times': dict(times),
                    'response_status': 'utterance_text_completed' if args.backend == 'nemotron' else summary.get('response_status'), 'user_transcripts': user_turn,
                    'assistant_transcripts': assistant_turn, 'output_samples': (len(audio) - audio_before) // 2})
                with wave.open(str(args.output / f'turn-{turn_number}.wav'), 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(audio[audio_before:])
                await asyncio.sleep(0.25)
            if args.backend == 'nemotron':
                try:
                    await asyncio.wait_for(receiver, 30)
                except websockets.ConnectionClosedError as error:
                    # The official server can close TCP without a WS close frame.
                    # Accept only after its explicit session-end and completion events.
                    if summary.get('session_end_stats') is None or summary.get('response_status') != 'completed': raise
                    summary['transport_close_warning'] = str(error)
                if summary.get('session_end_stats') is None or summary.get('response_status') != 'completed':
                    raise RuntimeError('NVIDIA session.close did not produce completion and session-end evidence')
                summary['completion_semantics'] = 'Utterance text done; official response.done/session.end collected on session.close'
            summary["status"] = "PASS" if all(turn['status'] == 'PASS' for turn in summary['turns']) else "PARTIAL"
            if any(turn['status'] == 'FAIL' for turn in summary['turns']): summary['status'] = 'FAIL'
        finally:
            if 'interrupter' in locals() and interrupter:
                interrupter.cancel()
                await asyncio.gather(interrupter, return_exceptions=True)
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
            with wave.open(str(args.output / "response.wav"), "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(audio)
            summary.update(times=times, event_types=event_types, user_transcripts=users,
                           assistant_transcripts=assistants, output_samples=len(audio) // 2)
            if "speech_end_ms" in times and "first_audio_received_ms" in times:
                summary["speech_end_to_first_audio_received_ms"] = times["first_audio_received_ms"] - times["speech_end_ms"]
                if args.backend == 'nemotron':
                    summary['speech_end_to_first_pcm_chunk_ms'] = summary['speech_end_to_first_audio_received_ms']
                    summary['speech_end_to_first_audio_received_ms'] = None
                    summary['audio_timing_semantics'] = 'Continuous PCM includes silence; first chunk is not assistant onset'
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--backend", choices=["modular", "nemotron", "mock"], required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--next-wav", type=Path, action='append', default=[], help='Additional turn in the same warm session; repeat for multiple turns')
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--silence", type=float)
    parser.add_argument("--chunk-ms", type=int, choices=[20, 40, 80])
    parser.add_argument("--connect-timeout", type=float, default=10)
    parser.add_argument("--event-timeout", type=float, default=15)
    parser.add_argument("--response-timeout", type=float, default=90)
    parser.add_argument("--total-timeout", type=float, default=180)
    parser.add_argument("--interrupt", action="store_true")
    args = parser.parse_args()
    if args.interrupt and args.backend == "nemotron": parser.error("NVIDIA response.cancel is not verified; use an audio barge-in test")
    if args.silence is not None and args.silence < 0: parser.error("Silence must be non-negative")
    try:
        result = asyncio.run(asyncio.wait_for(run(args), args.total_timeout))
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 1
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "FAIL", "error_type": type(error).__name__, "error": str(error)}
        (args.output / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        print(json.dumps(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
