#!/usr/bin/env python3
"""Serve the shared UI, realtime routes, mock and opt-in model-control API."""
from __future__ import annotations

import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.mock.server import serve_upgraded_socket  # noqa: E402
from services.proxy import proxy_websocket  # noqa: E402
from services.health import HealthMonitor  # noqa: E402
from services.end_to_end import request_model, read_json  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    """Keep browser endpoints on one origin; inference remains in backend jobs."""
    def do_POST(self):
        """Publish explicit replacement requests without owning any GPU process."""
        if self.path != '/api/model' or os.environ.get('VOICE_DEMO_SLOT_CONTROL') != '1':
            self.send_error(404)
            return
        # Operator control is opt-in and intended for the private SSH endpoint.
        from urllib.parse import urlsplit
        origin = self.headers.get('Origin', '')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.send_error(403, 'Cross-origin model replacement is disabled')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256:
                raise ValueError('Invalid request length')
            model = json.loads(self.rfile.read(length))['model']
            directory = os.environ.get('VOICE_DEMO_SLOT_DIRECTORY', str(ROOT / 'runtime/end-to-end'))
            state = read_json(Path(directory) / 'state.json', {})
            if not state or time.time() - state.get('updated_at', 0) > 120:
                self.send_error(503, 'End-to-end supervisor is not running')
                return
            payload = json.dumps(request_model(directory, model)).encode()
        except (ValueError, KeyError, TypeError):
            self.send_error(400, 'Select moshi or nemotron')
            return
        self.send_response(202)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

    def do_GET(self):
        if self.path == "/api/status":
            # Overlay the mutually exclusive slot on endpoint health so an
            # unloaded model is not mistaken for a second warming backend.
            monitor = getattr(self.server, "health_monitor", None)
            states = monitor.snapshot() if monitor else {}
            directory = os.environ.get('VOICE_DEMO_SLOT_DIRECTORY', str(ROOT / 'runtime/end-to-end'))
            slot = read_json(Path(directory) / 'state.json') if os.environ.get('VOICE_DEMO_SLOT_CONTROL') == '1' else None
            if slot:
                if time.time() - slot.get('updated_at', 0) > 120:
                    slot = {**slot, 'state': 'UNAVAILABLE'}
                states['slot'] = slot
                for name in ('moshi', 'nemotron'):
                    if slot.get('model') != name:
                        states[name] = {'state': 'UNLOADED'}
                    elif slot.get('state') != 'READY':
                        states[name] = {'state': slot['state']}
            payload = json.dumps(states).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(payload)
            return
        if self.path == "/mock" and self.headers.get("Upgrade", "").lower() == "websocket":
            try:
                serve_upgraded_socket(self.connection, self.headers, self.client_address, self.server)
            except (ConnectionError, OSError):
                pass
            return
        if self.path in ("/backend/nemotron", "/backend/modular", "/backend/moshi") and self.headers.get("Upgrade", "").lower() == "websocket":
            variable = "VOICE_DEMO_" + self.path.rsplit('/', 1)[1].upper() + "_URL"
            upstream = os.environ.get(variable, "")
            if not upstream:
                self.send_error(503, "Backend URL is not configured")
                return
            try:
                proxy_websocket(self.connection, self.headers, upstream)
            except (ConnectionError, OSError, ValueError) as error:
                print("[proxy] %s" % error)
                self.close_connection = True
            return
        if self.path == "/api/config":
            ui_port = self.server.server_address[1]
            protocol = "wss" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else "ws"
            host = self.headers.get("Host", "localhost:%d" % ui_port)
            same_origin = "%s://%s" % (protocol, host)
            directory = os.environ.get('VOICE_DEMO_SLOT_DIRECTORY', str(ROOT / 'runtime/end-to-end'))
            slot = read_json(Path(directory) / 'state.json', {}) if os.environ.get('VOICE_DEMO_SLOT_CONTROL') == '1' else {}
            # Return browser-reachable routes, not private compute-node URLs.
            # Reading config never loads a model; follow an existing resident
            # model, otherwise use Moshi as the frontend's default selection.
            payload = json.dumps({
                "mockUrl": same_origin + "/mock",
                "nemotronUrl": same_origin + "/backend/nemotron" if os.environ.get("VOICE_DEMO_NEMOTRON_URL") else "",
                "modularUrl": same_origin + "/backend/modular" if os.environ.get("VOICE_DEMO_MODULAR_URL") else "",
                "moshiUrl": same_origin + "/backend/moshi" if os.environ.get("VOICE_DEMO_MOSHI_URL") else "",
                "replay": os.environ.get('VOICE_DEMO_REPLAY') == '1',
                "modelControl": os.environ.get('VOICE_DEMO_SLOT_CONTROL') == '1',
                "defaultEndToEndModel": slot.get('model') or 'moshi',
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, fmt, *args):
        print("[ui] " + fmt % args)


def main():
    server = ThreadingHTTPServer((os.environ.get("VOICE_DEMO_UI_HOST", "127.0.0.1"), int(os.environ.get("VOICE_DEMO_UI_PORT", "7860"))), Handler)
    server.health_monitor = HealthMonitor()
    print("UI:   http://localhost:%s" % server.server_address[1])
    print("Mock: ws://localhost:%s/mock" % server.server_address[1])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping demo")
    finally:
        server.health_monitor.close()
        server.server_close()


if __name__ == "__main__":
    main()
