import base64
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from scripts.realtime_wav import load_pcm, sanitized, session_update


class WAVTests(unittest.TestCase):
    def write_wav(self, path, channels=1, rate=16000):
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes(struct.pack("<h", 1200) * rate * channels)

    def test_resampling_changes_samples_and_preserves_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.wav"
            self.write_wav(path)
            raw = load_pcm(path)
            self.assertEqual(len(raw), 24000 * 2)
            samples = struct.unpack("<24000h", raw)
            self.assertAlmostEqual(sum(samples[100:-100]) / len(samples[100:-100]), 1200, delta=2)

    def test_reject_stereo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.wav"
            self.write_wav(path, channels=2)
            with self.assertRaises(ValueError): load_pcm(path)

    def test_pcm_bytes_unchanged_at_contract_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.wav"
            self.write_wav(path, rate=24000)
            self.assertEqual(load_pcm(path), struct.pack("<h", 1200) * 24000)

    def test_audio_recording_redaction(self):
        event = {"type": "response.output_audio.delta", "delta": base64.b64encode(b"\0\0").decode(), "response_id": "r"}
        result = sanitized(event)
        self.assertEqual(result["delta"], "")
        self.assertEqual(result["audio_metadata"]["bytes"], 2)
        self.assertEqual(result["response_id"], "r")
        self.assertTrue(event["delta"])

    def test_vad_is_nested_and_not_sent_to_nvidia(self):
        hf = session_update("modular")["session"]
        nv = session_update("nemotron")["session"]
        self.assertEqual(hf["audio"]["input"]["turn_detection"]["type"], "server_vad")
        self.assertNotIn("turn_detection", nv["audio"]["input"])


if __name__ == "__main__": unittest.main()
