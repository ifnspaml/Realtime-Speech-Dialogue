"""Guard model/cache provenance without downloads, Torch or GPU use."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.prepare_models import own_directory, safe_extract, validate_snapshot


class ManifestTests(unittest.TestCase):
    def test_read_only_verification_pins_revision_and_checks_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            entry = {"repo_id": "test/model", "revision": "frozen", "files": {"weight": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}}}
            model = home / "hub/models--test--model"
            snapshot = model / "snapshots/frozen"
            snapshot.mkdir(parents=True)
            (snapshot / "weight").write_bytes(b"abc")
            (model / "refs").mkdir()
            (model / "refs/main").write_text("frozen")
            reference = model / "refs/main"
            reference.write_text(entry["revision"] + "\n")
            with self.assertRaises(ValueError):
                validate_snapshot(entry, home)
            reference.write_text(entry["revision"])
            before = {str(p.relative_to(home)) for p in home.rglob("*")}
            self.assertEqual(validate_snapshot(entry, home, True)["status"], "PASS")
            self.assertEqual(before, {str(p.relative_to(home)) for p in home.rglob("*")})
            (model / "refs/main").write_text("floating")
            with self.assertRaisesRegex(ValueError, "revision"):
                validate_snapshot(entry, home)
            (model / "refs/main").write_text("frozen")
            (snapshot / "weight").write_bytes(b"xyz")
            with self.assertRaisesRegex(ValueError, "Checksum"):
                validate_snapshot(entry, home, True)

    def test_download_setup_does_not_adopt_shared_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "someone-elses-data").write_text("keep")
            with self.assertRaisesRegex(ValueError, "unmanaged"):
                own_directory(directory)

    def test_tokenizer_archive_cannot_escape_target(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape", "bad")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                safe_extract(archive, Path(directory) / "target")
