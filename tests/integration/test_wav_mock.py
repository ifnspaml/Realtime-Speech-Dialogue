import argparse
import asyncio
import tempfile
import threading
import unittest
import struct
import wave
from pathlib import Path
from services.mock.server import Handler, Server
from scripts.realtime_wav import run


class WAVMockTests(unittest.TestCase):
    def test_prerecorded_audio_produces_complete_stream_and_saved_pcm(self):
        server = Server(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                with wave.open(str(path / "input.wav"), "wb") as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                    wav.writeframes(struct.pack("<h", 1200) * 16000)
                args = argparse.Namespace(url=f"ws://127.0.0.1:{server.server_address[1]}/mock", backend="mock",
                    wav=path / "input.wav", next_wav=[path / "input.wav"], output=path / "result", silence=0.5, chunk_ms=40,
                    connect_timeout=3, event_timeout=3, response_timeout=3, interrupt=False)
                result = asyncio.run(run(args))
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["measurement"], "synthetic")
                self.assertEqual(len(result["turns"]), 2)
                self.assertEqual(len(result["user_transcripts"]), 2)
                self.assertGreater(result["output_samples"], 0)
                self.assertTrue((args.output / "response.wav").exists())
                self.assertIn("response.done", result["event_types"])
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__": unittest.main()
