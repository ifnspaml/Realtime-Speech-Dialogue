"""Generate an explicitly synthetic replay fixture without speech or inference."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import wave


def create_fixture(directory, backend="modular"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pcm = b"".join(struct.pack("<h", round(4000 * math.sin(2 * math.pi * 440 * n / 24000))) for n in range(4800))
    with wave.open(str(directory / "response.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(pcm)
    continuous = backend in ("moshi", "nemotron")
    events = [
        {"type": "session.created", "session": {"id": "synthetic-session", "model": backend, "measurement": "synthetic", "capabilities": {"user_transcript": not continuous, "speech_boundaries": not continuous, "response_scope": "session" if continuous else "turn"}}},
        {"type": "session.updated", "session": {"id": "synthetic-session"}},
    ]
    if not continuous:
        events += [
            {"type": "input_audio_buffer.speech_started", "item_id": "synthetic-user"},
            {"type": "conversation.item.input_audio_transcription.completed", "item_id": "synthetic-user", "transcript": "Synthetic test question."},
            {"type": "input_audio_buffer.speech_stopped", "item_id": "synthetic-user"},
        ]
    events += [
        {"type": "response.created", "response": {"id": "synthetic-response", "status": "in_progress", "scope": "session" if continuous else "turn"}},
        {"type": "response.output_audio_transcript.delta", "response_id": "synthetic-response", "item_id": "synthetic-assistant", "delta": "This is a synthetic fixture tone, not a model response."},
        {"type": "response.output_audio.delta", "response_id": "synthetic-response", "item_id": "synthetic-assistant", "audio_metadata": {"bytes": len(pcm), "sha256": hashlib.sha256(pcm).hexdigest()}},
    ]
    if not continuous:
        events += [{"type": "response.output_audio_transcript.done", "response_id": "synthetic-response", "item_id": "synthetic-assistant", "transcript": "This is a synthetic fixture tone, not a model response."}, {"type": "response.output_audio.done", "response_id": "synthetic-response", "item_id": "synthetic-assistant"}, {"type": "response.done", "response": {"id": "synthetic-response", "status": "completed"}}]
    events += [{"type": "session.end", "origin": "moshi_adapter" if backend == "moshi" else "synthetic_fixture", "stats": {"output_samples": 4800}}]
    records = [{"received_ms": index * 30, "event": event} for index, event in enumerate(events)]
    (directory / "events.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records))
    (directory / "summary.json").write_text(json.dumps({"status": "PASS", "measurement": "synthetic", "backend": backend, "note": "Fixture generation only; no GPU inference or model accuracy claim."}, indent=2) + "\n")
    (directory / "provenance.json").write_text(json.dumps({"origin": "Deterministic 440 Hz oscillator and handwritten protocol events", "privacy": "No human speech, camera data, model voice or external recording", "measurement": "synthetic", "audio_sha256": hashlib.sha256((directory / "response.wav").read_bytes()).hexdigest()}, indent=2) + "\n")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=["modular", "moshi", "nemotron"], default="modular")
    args = parser.parse_args()
    create_fixture(args.output, args.backend)
    print("Created synthetic replay fixture; no model inference was run.")
