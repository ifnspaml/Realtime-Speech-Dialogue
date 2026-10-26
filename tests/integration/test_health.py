import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from services.health import probe


class HealthTests(unittest.TestCase):
    def test_real_readiness_requires_official_ready_payload(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = {"status": "ok", "triton_status": "ready", "mode": "triton"} if self.path.endswith("health") else {"size": 1, "units": [{"state": "idle"}]}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(payload).encode())
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"ws://127.0.0.1:{server.server_address[1]}/v1/realtime"
            self.assertEqual(probe("nemotron", url)["state"], "READY")
            self.assertEqual(probe("modular", url)["state"], "READY")
        finally: server.shutdown(); server.server_close()

    def test_configured_url_is_not_a_readiness_claim(self):
        self.assertEqual(probe("nemotron", "")["state"], "NOT CONFIGURED")
        self.assertEqual(probe("nemotron", "ws://127.0.0.1:1/v1/realtime")["state"], "UNAVAILABLE")
        self.assertEqual(probe("nemotron", "ws://127.0.0.1:1/mock")["state"], "SIMULATED")

    def test_stalled_health_does_not_block_the_ui_indefinitely(self):
        release = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                release.wait(5)
                try:
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
                except OSError: pass
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            started = time.monotonic()
            result = probe('nemotron', f'ws://127.0.0.1:{server.server_address[1]}/v1/realtime')
            self.assertEqual(result['state'], 'UNAVAILABLE')
            self.assertLess(time.monotonic() - started, 4)
        finally:
            release.set(); server.shutdown(); server.server_close()
