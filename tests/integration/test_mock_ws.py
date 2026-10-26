from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services.mock.server import Handler, Server  # noqa: E402


def send_text(sock: socket.socket, text: str) -> None:
    payload = text.encode()
    mask = os.urandom(4)
    size = len(payload)
    head = bytes([0x81, 0x80 | size]) if size < 126 else bytes([0x81, 0x80 | 126]) + struct.pack("!H", size)
    payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    sock.sendall(head + mask + payload)


def read_exact(sock: socket.socket, size: int) -> bytes:
    out = b""
    while len(out) < size:
        part = sock.recv(size - len(out))
        if not part:
            raise EOFError
        out += part
    return out


def receive_text(sock: socket.socket) -> dict:
    first, second = read_exact(sock, 2)
    size = second & 0x7F
    if size == 126:
        size = struct.unpack("!H", read_exact(sock, 2))[0]
    elif size == 127:
        size = struct.unpack("!Q", read_exact(sock, 8))[0]
    payload = read_exact(sock, size)
    return json.loads(payload.decode())


class MockWebSocketIntegration(unittest.TestCase):
    def test_realtime_handshake_and_mock_turn(self):
        server = Server(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        sock = socket.create_connection(server.server_address, timeout=3)
        sock.settimeout(3)
        key = base64.b64encode(os.urandom(16))
        sock.sendall(b"GET /mock HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + b"\r\n\r\n")
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(1)
        self.assertIn(b"101 Switching Protocols", response)
        self.assertIn(base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()), response)
        self.assertEqual(receive_text(sock)["type"], "session.created")
        send_text(sock, json.dumps({"type": "session.update", "session": {"instructions": "test"}}))
        self.assertEqual(receive_text(sock)["type"], "session.updated")
        send_text(sock, json.dumps({"type": "demo.mock_turn", "delayMs": 0, "jitterMs": 0, "transcript": "Replay check"}))
        seen = set()
        for _ in range(24):
            event = receive_text(sock)
            seen.add(event["type"])
            if event["type"] == "response.done":
                break
        self.assertIn("conversation.item.input_audio_transcription.completed", seen)
        self.assertIn("response.output_audio.delta", seen)
        self.assertIn("response.output_item.added", seen)
        self.assertIn("response.content_part.added", seen)
        self.assertIn("response.output_item.done", seen)
        self.assertIn("response.done", seen)
        send_text(sock, json.dumps({"type": "demo.mock_turn", "delayMs": 0, "jitterMs": 1000, "transcript": "Interrupt test"}))
        while True:
            event = receive_text(sock)
            if event["type"] == "response.created":
                break
        send_text(sock, json.dumps({"type": "response.cancel"}))
        while True:
            event = receive_text(sock)
            if event["type"] == "response.done":
                self.assertEqual(event["response"]["status"], "cancelled")
                break
        sock.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    unittest.main()
