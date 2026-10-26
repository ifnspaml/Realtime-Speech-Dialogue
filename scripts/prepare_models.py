#!/usr/bin/env python3
"""Explicitly prepare pinned models, or verify caches without changing them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/models.json"
MARKER = ".speech-dialogue-managed"


def file_digest(path, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        if algorithm == "sha1":
            digest.update(("blob " + str(Path(path).stat().st_size) + "\0").encode())
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def own_directory(path):
    """Download/setup commands must never adopt an unmarked shared cache."""
    path = Path(path)
    if path.exists() and any(path.iterdir()) and not (path / MARKER).is_file():
        raise ValueError("Refusing to change an unmanaged existing cache; choose an empty directory or use --verify-only")
    path.mkdir(parents=True, exist_ok=True)
    (path / MARKER).write_text("Speech Dialogue Demo: explicit model preparation owns this directory.\n")


def snapshot_directory(entry, home):
    return Path(home) / "hub" / ("models--" + entry["repo_id"].replace("/", "--")) / "snapshots" / entry["revision"]


def validate_snapshot(entry, home, checksum=False):
    snapshot = snapshot_directory(entry, home)
    reference = snapshot.parent.parent / "refs/main"
    if not reference.is_file() or reference.read_text() != entry["revision"]:
        raise ValueError("Offline main alias does not match the pinned revision: " + entry["repo_id"])
    for filename, metadata in entry["files"].items():
        path = snapshot / filename
        if not path.is_file() or path.stat().st_size != metadata["bytes"]:
            raise ValueError("Missing or incorrect-size pinned file: " + entry["repo_id"] + "/" + filename)
        if checksum:
            algorithm, expected = ("sha256", metadata["sha256"]) if "sha256" in metadata else ("sha1", metadata["git_blob_sha1"])
            if file_digest(path, algorithm) != expected:
                raise ValueError("Checksum mismatch: " + entry["repo_id"] + "/" + filename)
    return {"model": entry["repo_id"], "revision": entry["revision"], "files": len(entry["files"]), "checksum": checksum, "status": "PASS"}


def prepare_snapshot(entry, home):
    # Explicit setup may access the network; runtime launchers default offline.
    os.environ["HF_HUB_OFFLINE"] = "0"
    from huggingface_hub import hf_hub_download
    for filename in entry["files"]:
        hf_hub_download(repo_id=entry["repo_id"], filename=filename,
                        revision=entry["revision"], cache_dir=str(Path(home) / "hub"))
    # Several frozen upstream loaders request main rather than accepting a
    # revision argument. An owned cache plus an explicit offline alias pins
    # their resolution without modifying third-party inference code.
    reference = snapshot_directory(entry, home).parent.parent / "refs/main"
    reference.parent.mkdir(parents=True, exist_ok=True)
    temporary = reference.with_suffix(".tmp")
    temporary.write_text(entry["revision"])
    temporary.replace(reference)
    return validate_snapshot(entry, home, checksum=True)


def silero_directory(manifest, torch_home):
    return Path(torch_home) / "hub" / manifest["upstreams"]["silero"]["torch_hub_directory"]


def verify_auxiliary(manifest, torch_home, nltk_data):
    silero = manifest["upstreams"]["silero"]
    path = silero_directory(manifest, torch_home) / silero["jit_file"]
    if not path.is_file() or file_digest(path) != silero["jit_sha256"]:
        raise ValueError("Pinned Silero VAD checkpoint is missing or changed")
    for name, metadata in silero["files"].items():
        source = silero_directory(manifest, torch_home) / name
        if not source.is_file() or file_digest(source, "sha1") != metadata["git_blob_sha1"]:
            raise ValueError("Pinned Silero source/checkpoint changed: " + name)
    for name, metadata in manifest["nltk_data"]["archives"].items():
        directory = Path(nltk_data) / metadata["directory"] / name
        if not directory.is_dir() or not any(directory.rglob("*.txt" if name == "punkt_tab" else "*.json")):
            raise ValueError("NLTK data missing: " + name + "; run model preparation")


def safe_extract(archive, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Unsafe tokenizer archive path")
        bundle.extractall(destination)


def prepare_auxiliary(manifest, torch_home, nltk_data):
    own_directory(torch_home)
    own_directory(nltk_data)
    silero = manifest["upstreams"]["silero"]
    target = silero_directory(manifest, torch_home)
    target.mkdir(parents=True, exist_ok=True)
    for name, metadata in silero["files"].items():
        path = target / name
        if path.is_file() and file_digest(path, "sha1") == metadata["git_blob_sha1"]:
            continue
        url = f"https://raw.githubusercontent.com/snakers4/silero-vad/{silero['commit']}/{name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        if temporary.stat().st_size != metadata["bytes"] or file_digest(temporary, "sha1") != metadata["git_blob_sha1"]:
            temporary.unlink(missing_ok=True)
            raise ValueError("Pinned Silero file checksum mismatch: " + name)
        temporary.replace(path)
    for name, metadata in manifest["nltk_data"]["archives"].items():
        with tempfile.TemporaryDirectory(dir=nltk_data, prefix="tokenizer-setup-") as temporary:
            archive = Path(temporary) / (name + ".zip")
            with urllib.request.urlopen(metadata["url"], timeout=60) as response:
                archive.write_bytes(response.read())
            if file_digest(archive) != metadata["sha256"]:
                raise ValueError("NLTK tokenizer archive checksum mismatch")
            safe_extract(archive, Path(nltk_data) / metadata["directory"])
    verify_auxiliary(manifest, torch_home, nltk_data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["moshi", "modular", "all"], required=True)
    parser.add_argument("--verify-only", action="store_true", help="Read-only: never create locks, files, aliases or downloads")
    parser.add_argument("--checksum", action="store_true", help="Hash every selected model file during read-only verification")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--torch-home", type=Path)
    parser.add_argument("--nltk-data", type=Path)
    args = parser.parse_args()
    home = args.cache_dir or Path(os.environ.get("VOICE_DEMO_HF_HOME", os.environ.get("HF_HOME", ROOT / "models/huggingface")))
    torch_home = args.torch_home or Path(os.environ.get("TORCH_HOME", ROOT / "models/torch"))
    nltk_data = args.nltk_data or Path(os.environ.get("NLTK_DATA", ROOT / "models/nltk_data"))
    manifest = json.loads(MANIFEST.read_text())
    selected = [entry for entry in manifest["models"] if args.backend == "all" or entry["backend"] == args.backend]
    if not args.verify_only:
        own_directory(home)
        # Serialize only explicit preparation of this owned cache.
        import fcntl
        with (home / ".prepare.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for entry in selected:
                print(json.dumps(prepare_snapshot(entry, home)), flush=True)
            if args.backend in ("modular", "all"):
                prepare_auxiliary(manifest, torch_home, nltk_data)
    else:
        for entry in selected:
            print(json.dumps(validate_snapshot(entry, home, args.checksum)), flush=True)
        if args.backend in ("modular", "all"):
            verify_auxiliary(manifest, torch_home, nltk_data)
    print("PASS: pinned cache preparation/verification; no inference performed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Model cache verification failed: " + str(error) + "; use scripts/prepare_models.py for explicit preparation", file=sys.stderr)
        raise SystemExit(2)
