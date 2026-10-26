"""Verify replay integrity using generated tones, without retained voice data."""
import json
from pathlib import Path
import tempfile
import unittest
from services.replay import load_trace
from tests.fixtures.replay_fixture import create_fixture


class ReplayTests(unittest.TestCase):
    def test_fixtures_reconstruct_both_architectures(self):
        for backend in ("modular", "moshi", "nemotron"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                create_fixture(directory, backend)
                records = load_trace(directory)
                chunks = [r["event"] for r in records if r["event"]["type"] == "response.output_audio.delta"]
                self.assertTrue(chunks)
                self.assertTrue(all(e["delta"] and e["audio_metadata"]["bytes"] % 2 == 0 for e in chunks))

    def test_changed_audio_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            records = create_fixture(directory)
            next(r["event"]["audio_metadata"] for r in records if "audio_metadata" in r["event"])["sha256"] = "0" * 64
            Path(directory, "events.jsonl").write_text("\n".join(json.dumps(r) for r in records))
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_trace(directory)
