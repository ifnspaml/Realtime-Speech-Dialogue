"""Replay checksum-verified developer fixtures; never claim fresh inference."""
import base64
import hashlib
import json
import os
import threading
import time
import wave
from pathlib import Path
from services.mock.server import Handler, Server


def load_trace(directory):
    """Restore PCM deltas from the WAV after checking each recorded chunk hash."""
    directory = Path(directory)
    records = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
    with wave.open(str(directory / 'response.wav'), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 24000, "NONE"):
            raise ValueError("Replay requires 24 kHz mono PCM16 WAV")
        audio = wav.readframes(wav.getnframes())
    offset = 0
    for record in records:
        event = record['event']
        metadata = event.get('audio_metadata')
        if metadata:
            chunk = audio[offset:offset + metadata['bytes']]
            if hashlib.sha256(chunk).hexdigest() != metadata['sha256']:
                raise ValueError('Replay audio checksum mismatch')
            event['delta'] = base64.b64encode(chunk).decode()
            offset += len(chunk)
    if offset != len(audio):
        raise ValueError('Replay audio length mismatch')
    return records


class ReplayHandler(Handler):
    def handle(self):
        try:
            self.setup_connection()
            records = load_trace(self.server.fixture_directory)
            created = next(record['event'] for record in records if record['event']['type'] == 'session.created')
            created = {**created, 'session': {**created.get('session', {}), 'measurement': 'replay'}}
            self.send(created)
            replaying = False
            def playback():
                # Relative recorded receipt times reproduce event order and gaps;
                # they are historical observations, not new model latency data.
                playable = [r for r in records if r['event']['type'] not in ('session.created', 'session.updated')]
                start = time.monotonic()
                first = playable[0]['received_ms']
                for record in playable:
                    if self.closed or self.cancel.is_set(): return
                    time.sleep(max(0, start + (record['received_ms'] - first) / 1000 - time.monotonic()))
                    self.send(record['event'])
            while not self.closed:
                opcode, payload = self.recv_frame()
                if opcode is None or opcode == 8: break
                if opcode != 1: continue
                event = json.loads(payload)
                if event['type'] == 'session.update':
                    self.send(next(record['event'] for record in records if record['event']['type'] == 'session.updated'))
                if event['type'] == 'input_audio_buffer.append' and not replaying:
                    replaying = True
                    threading.Thread(target=playback, daemon=True).start()
                if event['type'] == 'response.cancel': self.cancel.set()
        except (OSError, ConnectionError, ValueError):
            pass
        finally:
            self.closed = True
            self.cancel.set()


if __name__ == '__main__':
    with Server(('127.0.0.1', int(os.environ.get('VOICE_DEMO_REPLAY_PORT', '8767'))), ReplayHandler) as server:
        server.fixture_directory = os.environ['VOICE_DEMO_REPLAY_FIXTURE']
        server.serve_forever()
