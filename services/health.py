"""Probe official model readiness without creating or restarting sessions."""
import concurrent.futures
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def probe(name, url):
    """Interpret each backend's readiness payload without opening a voice session."""
    if not url: return {"state": "NOT CONFIGURED"}
    parsed = urllib.parse.urlsplit(url)
    if parsed.path == "/mock": return {"state": "SIMULATED"}
    path = "/health" if name == "moshi" else "/v1/realtime/health" if name == "nemotron" else "/v1/pool"
    http_url = urllib.parse.urlunsplit(("https" if parsed.scheme == "wss" else "http", parsed.netloc, path, "", ""))
    try:
        with urllib.request.urlopen(http_url, timeout=3) as response:
            payload = json.loads(response.read(65536))
        if name == "moshi":
            if payload.get('measurement') == 'synthetic': return {'state': 'SIMULATED'}
            ready = payload.get('status') == 'ok' and payload.get('native_available') and payload.get('inference_validated')
        elif name == "nemotron":
            ready = payload.get("status") == "ok" and payload.get("triton_status") == "ready"
            if payload.get("mode") == "loopback": return {"state": "SIMULATED"}
        else:
            ready = payload.get("size", 0) > 0 and any(u.get("state") in ("idle", "active") for u in payload.get("units", []))
        return {"state": "READY" if ready else "STARTING"}
    except urllib.error.HTTPError as error:
        return {"state": "STARTING" if error.code == 503 else "UNAVAILABLE", "http_status": error.code}
    except (OSError, ValueError, TypeError, AttributeError): return {"state": "UNAVAILABLE"}


class HealthMonitor:
    """Cache independent probes so a slow backend does not block the UI handler."""
    def __init__(self):
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.states = {name: {"state": "CHECKING"} for name in ("nemotron", "modular", "moshi")}
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            while not self.stop.is_set():
                names = ("nemotron", "modular", "moshi")
                futures = {name: executor.submit(probe, name, os.environ.get(f"VOICE_DEMO_{name.upper()}_URL", "")) for name in names}
                states = {name: task.result() for name, task in futures.items()}
                with self.lock: self.states = states
                self.stop.wait(5)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=8)

    def snapshot(self):
        with self.lock: return dict(self.states)
