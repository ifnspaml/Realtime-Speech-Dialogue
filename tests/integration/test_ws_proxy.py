from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import threading
import unittest
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_demo import Handler  # noqa: E402
from services.mock.server import Handler as MockHandler, Server as MockServer  # noqa: E402


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise EOFError
        data.extend(part)
    return bytes(data)


def send_json(sock: socket.socket, obj: dict) -> None:
    data = json.dumps(obj).encode()
    mask = os.urandom(4)
    size = len(data)
    if size < 126:
        head = bytes([0x81, 0x80 | size])
    else:
        head = bytes([0x81, 0x80 | 126]) + struct.pack("!H", size)
    sock.sendall(head + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))


def recv_json(sock: socket.socket) -> dict:
    first, second = read_exact(sock, 2)
    size = second & 0x7F
    if size == 126:
        size = struct.unpack("!H", read_exact(sock, 2))[0]
    elif size == 127:
        size = struct.unpack("!Q", read_exact(sock, 8))[0]
    return json.loads(read_exact(sock, size))


class SameOriginWebSocketProxy(unittest.TestCase):
    def test_mock_and_page_share_one_http_port(self):
        ui = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        ui_thread = threading.Thread(target=ui.serve_forever, daemon=True)
        ui_thread.start()
        with urlopen("http://127.0.0.1:%d/" % ui.server_address[1], timeout=3) as page:
            self.assertIn(b"<title>Real-Time Speech Dialogue", page.read())
        with urlopen("http://127.0.0.1:%d/api/config" % ui.server_address[1], timeout=3) as response:
            config = json.loads(response.read())
        self.assertEqual(config["mockUrl"], "ws://127.0.0.1:%d/mock" % ui.server_address[1])
        self.assertEqual(config['defaultEndToEndModel'], 'moshi')
        client = socket.create_connection(ui.server_address, timeout=3)
        client.settimeout(3)
        key = base64.b64encode(os.urandom(16))
        client.sendall(b"GET /mock HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + b"\r\n\r\n")
        response = bytearray()
        while b"\r\n\r\n" not in response:
            response.extend(client.recv(1))
        self.assertIn(b"101 Switching Protocols", response)
        self.assertEqual(recv_json(client)["type"], "session.created")
        send_json(client, {"type": "session.update", "session": {}})
        self.assertEqual(recv_json(client)["type"], "session.updated")
        client.close()
        ui.shutdown(); ui.server_close()

    def test_browser_uses_ui_port_for_upstream_realtime_socket(self):
        mock = MockServer(("127.0.0.1", 0), MockHandler)
        mock_thread = threading.Thread(target=mock.serve_forever, daemon=True)
        mock_thread.start()
        old_upstream = os.environ.get("VOICE_DEMO_NEMOTRON_URL")
        os.environ["VOICE_DEMO_NEMOTRON_URL"] = "ws://127.0.0.1:%d/mock" % mock.server_address[1]
        ui = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        ui_thread = threading.Thread(target=ui.serve_forever, daemon=True)
        ui_thread.start()
        client = socket.create_connection(ui.server_address, timeout=3)
        client.settimeout(3)
        key = base64.b64encode(os.urandom(16))
        client.sendall(b"GET /backend/nemotron HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + b"\r\n\r\n")
        response = bytearray()
        while b"\r\n\r\n" not in response:
            response.extend(client.recv(1))
        self.assertIn(b"101 Switching Protocols", response)
        self.assertEqual(recv_json(client)["type"], "session.created")
        send_json(client, {"type": "session.update", "session": {"instructions": "proxy test"}})
        self.assertEqual(recv_json(client)["type"], "session.updated")
        client.close()
        ui.shutdown(); ui.server_close()
        mock.shutdown(); mock.server_close()
        if old_upstream is None:
            os.environ.pop("VOICE_DEMO_NEMOTRON_URL", None)
        else:
            os.environ["VOICE_DEMO_NEMOTRON_URL"] = old_upstream


if __name__ == "__main__":
    unittest.main()
