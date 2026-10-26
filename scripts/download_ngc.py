#!/usr/bin/env python3
"""Download the documented public NGC model files and verify every SHA256.

Requires network access and NGC/NVIDIA license acceptance by the operator.
Does not log secrets. Paths from the remote manifest must stay relative.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = (
    "https://api.ngc.nvidia.com/v2/models/nim/nvidia/"
    "nemotron-labs-voicechat/versions/1.0.0/files"
)
DEFAULT_TARGET = ROOT / "models" / "nemotron-labs-voicechat_v1.0.0"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode()


def safe_relative_path(raw: str, target: Path) -> Path:
    """Reject absolute paths and traversal outside the target directory."""
    if not raw or raw.startswith("/") or raw.startswith("\\"):
        raise ValueError(f"Rejecting absolute manifest path: {raw!r}")
    if ":" in raw.split("/", 1)[0] and len(raw) > 1 and raw[1] == ":":
        raise ValueError(f"Rejecting drive-absolute manifest path: {raw!r}")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Rejecting unsafe manifest path: {raw!r}")
    resolved = (target / candidate).resolve()
    target_resolved = target.resolve()
    try:
        resolved.relative_to(target_resolved)
    except ValueError as exc:
        raise ValueError(f"Manifest path escapes target directory: {raw!r}") from exc
    return resolved


def download_item(item: dict, base: str, target: Path) -> dict:
    relative = item["path"]
    path = safe_relative_path(relative, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = item["sha256_base64"]
    size = int(item["sizeInBytes"])
    if path.exists() and path.stat().st_size == size and checksum(path) == expected:
        return {"path": relative, "verified": True, "cached": True}
    partial = path.with_name(path.name + ".part")
    url = f"{base.rstrip('/')}/{relative}"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                append = offset > 0 and getattr(response, "status", 200) == 206
                digest = hashlib.sha256()
                if append:
                    with partial.open("rb") as previous:
                        for chunk in iter(lambda: previous.read(8 * 1024 * 1024), b""):
                            digest.update(chunk)
                mode = "ab" if append else "wb"
                with partial.open(mode) as output:
                    for chunk in iter(lambda: response.read(8 * 1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
            if partial.stat().st_size != size or base64.b64encode(digest.digest()).decode() != expected:
                partial.unlink(missing_ok=True)
                raise ValueError(f"Size or SHA256 mismatch for {relative}")
            os.replace(partial, path)
            print(f"Verified {relative}", flush=True)
            return {"path": relative, "verified": True, "bytes": size}
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Download failed for {relative}: {last_error}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("NEMOTRON_MODEL_DIR", DEFAULT_TARGET)),
        help="Destination directory for official NGC model files",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VOICE_DEMO_NGC_FILES_URL", DEFAULT_BASE),
        help="NGC files API base URL (no credentials are logged)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Parallel download workers",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target: Path = args.target.expanduser()
    if not target.is_absolute():
        target = (ROOT / target).resolve()
    else:
        target = target.resolve()
    base = args.base_url
    parsed = urlsplit(base)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("Use an HTTPS files endpoint without embedded credentials or query parameters")
    manifest = json.loads((ROOT / "config/nemotron-files.json").read_text())
    files = manifest.get("files")
    if not isinstance(files, list):
        raise SystemExit("Unexpected frozen NGC manifest shape: missing files list")
    for item in files:
        safe_relative_path(item["path"], target)
    target.mkdir(parents=True, exist_ok=True)
    (target / "download-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(lambda item: download_item(item, base, target), files))
    (target / "verification.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Verified {len(results)} official NGC files under {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
