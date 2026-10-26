"""Dependency-free WebSocket mock for the browser demo (RFC 6455 text frames)."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import random
import socketserver
import struct
import threading
import time
import uuid


def _frame(payload: bytes, opcode: int = 1) -> bytes:
    size = len(payload)
    head = bytes([0x80 | opcode])
    if size < 126:
        head += bytes([size])
    elif size < 65536:
        head += bytes([126]) + struct.pack("!H", size)
    else:
        head += bytes([127]) + struct.pack("!Q", size)
    return head + payload


def _pcm_tone(seconds: float = 0.35) -> str:
    count = int(24000 * seconds)
    raw = bytearray(count * 2)
    for i in range(count):
        envelope = min(1.0, i / 400, (count - i) / 800)
        sample = int(1800 * max(0.0, envelope) * math.sin(2 * math.pi * 440 * i / 24000))
        struct.pack_into("<h", raw, i * 2, sample)
    return base64.b64encode(raw).decode("ascii")


class Handler(socketserver.BaseRequestHandler):
    """Simulate ordered realtime events and bounded delays without inference."""
    def setup(self):
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.closed = False
        self.mic_in_speech = False
        self.mic_silence_frames = 0
        self.response_active = False
        self.random = random.Random(0)
        self.network_delay = 0
        self.network_jitter = 0

    def send(self, event):
        payload = json.dumps(event, separators=(",", ":")).encode()
        try:
            with self.lock:
                # Event-level simulation preserves order and has no pending queue.
                time.sleep(max(0, self.network_delay + self.random.uniform(-self.network_jitter, self.network_jitter)))
                self.request.sendall(_frame(payload))
        except OSError:
            self.closed = True

    def event(self, kind, **values):
        self.send({"type": kind, "event_id": str(uuid.uuid4()), **values})

    def setup_connection(self, headers=None):
        if headers is None:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = self.request.recv(2048)
                if not chunk:
                    raise ConnectionError("connection closed during handshake")
                data += chunk
                if len(data) > 16384:
                    raise ConnectionError("oversized handshake")
            headers = {}
            for line in data.split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    headers[key.strip().lower()] = value.strip()
            key = headers.get(b"sec-websocket-key")
        else:
            key = headers.get("Sec-WebSocket-Key")
            if isinstance(key, str):
                key = key.encode("ascii")
        if not key:
            raise ConnectionError("missing WebSocket key")
        accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        self.request.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")

    def recv_frame(self):
        first = self._recv_exact(2)
        if first is None:
            return None, None
        opcode = first[0] & 0x0F
        masked = first[1] & 0x80
        size = first[1] & 0x7F
        if size == 126:
            size = struct.unpack("!H", self._recv_exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self._recv_exact(8))[0]
        if size > 2_000_000:
            raise ConnectionError("frame too large")
        mask = self._recv_exact(4) if masked else None
        payload = self._recv_exact(size)
        if masked and payload is not None:
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.request.recv(size - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def respond_to_turn(self, message, include_input=True):
        self.cancel.set()
        self.cancel = threading.Event()
        self.response_active = True
        cancel = self.cancel
        delay = max(0, min(2000, int(message.get("delayMs", 180)))) / 1000
        jitter = max(0, min(1000, int(message.get("jitterMs", 25)))) / 1000
        stall = max(0, min(2000, int(message.get("stallMs", 0)))) / 1000
        user_id = "mock-user-" + str(uuid.uuid4())
        assistant_id = "mock-assistant-" + str(uuid.uuid4())
        transcript = str(message.get("transcript") or "This is a simulated user utterance.")[:300]

        if include_input:
            self.event("input_audio_buffer.speech_started", item_id=user_id)
            if cancel.wait(0.02):
                return
            self.event("conversation.item.input_audio_transcription.delta", item_id=user_id, delta=transcript)
            self.event("input_audio_buffer.speech_stopped", item_id=user_id)
            self.event("conversation.item.input_audio_transcription.completed", item_id=user_id, transcript=transcript)

        def answer():
            if cancel.wait(delay + (jitter * 0.35)) or self.closed:
                return
            response_id = str(uuid.uuid4())
            self.send({"type": "response.created", "event_id": str(uuid.uuid4()), "response": {"id": response_id, "status": "in_progress"}})
            self.send({"type": "response.output_item.added", "event_id": str(uuid.uuid4()), "response_id": response_id, "output_index": 0, "item": {"id": assistant_id, "type": "message", "role": "assistant"}})
            self.send({"type": "response.content_part.added", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "output_index": 0, "content_index": 0, "part": {"type": "audio"}})
            text = "The end-to-end model handles speech in one model. The modular system connects separate VAD, speech recognition, language model, and speech synthesis stages."
            for part in (text[:61], text[61:]):
                text_gap = max(0, 0.04 + self.random.uniform(-jitter, jitter))
                if cancel.wait(text_gap) or self.closed:
                    break
                self.send({"type": "response.output_audio_transcript.delta", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "delta": part})
            if cancel.is_set() or self.closed:
                return
            tone = base64.b64decode(_pcm_tone())
            frame_bytes = 24000 * 2 // 8  # 125 ms of 24 kHz mono PCM16.
            for index, offset in enumerate(range(0, len(tone), frame_bytes)):
                audio_gap = max(0, frame_bytes / (24000 * 2) + self.random.uniform(-jitter, jitter))
                if index and (cancel.wait(audio_gap) or self.closed):
                    return
                if index == 1 and stall and (cancel.wait(stall) or self.closed):
                    return
                chunk = base64.b64encode(tone[offset:offset + frame_bytes]).decode("ascii")
                self.send({"type": "response.output_audio.delta", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "content_index": 0, "delta": chunk})
            self.send({"type": "response.output_audio.done", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "content_index": 0})
            self.send({"type": "response.output_audio_transcript.done", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "transcript": text})
            self.send({"type": "response.content_part.done", "event_id": str(uuid.uuid4()), "response_id": response_id, "item_id": assistant_id, "output_index": 0, "content_index": 0, "part": {"type": "audio"}})
            self.send({"type": "response.output_item.done", "event_id": str(uuid.uuid4()), "response_id": response_id, "output_index": 0, "item": {"id": assistant_id, "type": "message", "role": "assistant"}})
            self.send({"type": "response.done", "event_id": str(uuid.uuid4()), "response": {"id": response_id, "status": "completed"}})
            self.response_active = False

        threading.Thread(target=answer, daemon=True).start()

    def handle(self):
        try:
            self.setup_connection(getattr(self, "pre_handshake_headers", None))
            self.event("session.created", session={"type": "realtime", "id": str(uuid.uuid4()), "model": "mock-realtime", "audio": {"input": {"format": {"type": "audio/pcm", "rate": 24000}}, "output": {"format": {"type": "audio/pcm", "rate": 24000}}}})
            while not self.closed:
                opcode, payload = self.recv_frame()
                if opcode is None or opcode == 8:
                    break
                if opcode == 9:
                    with self.lock:
                        self.request.sendall(_frame(payload or b"", 10))
                    continue
                if opcode != 1:
                    continue
                try:
                    message = json.loads(payload.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    self.event("error", error={"code": "invalid_json", "message": "Malformed event"})
                    continue
                kind = message.get("type")
                if kind == "session.update":
                    self.event("session.updated", session=message.get("session", {}))
                elif kind == "demo.mock_turn":
                    self.network_delay = max(0, min(200, int(message.get("networkDelayMs", 0)))) / 1000
                    self.network_jitter = max(0, min(50, int(message.get("networkJitterMs", 0)))) / 1000
                    self.respond_to_turn(message)
                elif kind == "input_audio_buffer.append":
                    # Amplitude drives a synthetic turn detector only. The text
                    # below is deterministic, not recognition of microphone words.
                    try:
                        pcm = base64.b64decode(message.get("audio", ""), validate=True)
                        count = len(pcm) // 2
                        energy = 0
                        for offset in range(0, len(pcm) - 1, 2):
                            sample = struct.unpack_from("<h", pcm, offset)[0]
                            energy += sample * sample
                        rms = math.sqrt(energy / max(1, count)) / 32768
                    except (ValueError, struct.error):
                        continue
                    if rms >= 0.012:
                        if not self.mic_in_speech:
                            if self.response_active:
                                self.cancel.set()
                                self.response_active = False
                                self.event("response.done", response={"status": "cancelled", "status_details": {"reason": "turn_detected"}})
                            self.mic_in_speech = True
                            self.mic_item_id = "mock-mic-user-" + str(uuid.uuid4())
                            self.mic_silence_frames = 0
                            self.event("input_audio_buffer.speech_started", item_id=self.mic_item_id)
                            self.event("conversation.item.input_audio_transcription.delta", item_id=self.mic_item_id, delta="This is a simulated microphone turn.")
                            self.event("conversation.item.input_audio_transcription.completed", item_id=self.mic_item_id, transcript="This is a simulated microphone turn.")
                        self.mic_silence_frames = 0
                    elif self.mic_in_speech:
                        self.mic_silence_frames += 1
                        if self.mic_silence_frames >= 8:
                            self.mic_in_speech = False
                            self.event("input_audio_buffer.speech_stopped", item_id=self.mic_item_id)
                            self.respond_to_turn({"delayMs": 180, "jitterMs": 25, "transcript": "This is a simulated microphone turn."}, include_input=False)
                elif kind in ("response.cancel", "demo.interrupt"):
                    self.cancel.set()
                    self.response_active = False
                    self.event("response.done", response={"status": "cancelled"})
                elif kind == "demo.disconnect":
                    break
                elif kind == "session.close":
                    self.event("session.end", stats={"chunks_received": 0, "chunks_sent": 0, "chunks_dropped": 0})
                    break
                elif kind == "demo.malformed":
                    with self.lock:
                        self.request.sendall(_frame(b"{malformed"))
        except (ConnectionError, OSError, struct.error):
            pass
        finally:
            self.closed = True


def serve_upgraded_socket(sock, headers, address=None, server=None):
    """Serve a WebSocket already parsed/upgraded by an HTTP request handler."""
    handler = object.__new__(Handler)
    handler.request = sock
    handler.client_address = address
    handler.server = server
    handler.setup()
    handler.pre_handshake_headers = headers
    handler.handle()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(host="127.0.0.1", port=8766):
    with Server((host, port), Handler) as server:
        server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    serve(os.environ.get("VOICE_DEMO_MOCK_HOST", "127.0.0.1"), int(os.environ.get("VOICE_DEMO_MOCK_PORT", "8766")))
