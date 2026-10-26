#!/usr/bin/env python3
"""Heuristic publication gate for private data, artifacts and author metadata.

Findings include filenames/categories only, never matched credential values.
This gate complements manual review; it does not certify every possible secret.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'models', 'third_party', 'artifacts', 'runtime', 'logs', 'node_modules', '.cache', '.git', '__pycache__', '.pytest_cache'}
MAX_ASSET_BYTES = 2 * 1024 * 1024
PROHIBITED = {'.safetensors', '.ckpt', '.pt', '.pth', '.onnx', '.gguf', '.ggml', '.sif', '.wav', '.mp4', '.zip', '.tar', '.deb', '.pem', '.key', '.p12', '.pfx'}
PATTERNS = {
    'private key': re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    'access token': re.compile(rb'\b(?:hf_[A-Za-z0-9]{25,}|gh[pousr]_[A-Za-z0-9]{25,}|glpat-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b'),
    'personal absolute path': re.compile(rb'/(?:home|Users)/[A-Za-z0-9_.-]+/|/beegfs/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/'),
    'internal repository host': re.compile(rb'git\.rz\.tu-bs\.de', re.I),
    'operational node name': re.compile(rb'\b(?:gpu|compute|login)[0-9]{2,}\b', re.I),
    'credential in URL': re.compile(rb'https?://[^\s/\x22\x27:@]+:[^\s/\x22\x27@]+@', re.I),
}
IPV4 = re.compile(rb'(?<![A-Za-z0-9_.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![A-Za-z0-9_.])')
EXAMPLE_NETWORKS = tuple(ipaddress.ip_network(v) for v in ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24'))


def find_sensitive(content):
    findings = {label for label, pattern in PATTERNS.items() if pattern.search(content)}
    for match in IPV4.finditer(content):
        line_start = content.rfind(b'\n', 0, match.start()) + 1
        # A four-part pinned package version is not a network endpoint.
        if re.fullmatch(rb'[A-Za-z0-9_.\-\[\],]+==', content[line_start:match.start()]):
            continue
        try:
            address = ipaddress.ip_address(match.group().decode('ascii'))
        except ValueError:
            continue
        if not (address.is_loopback or address.is_unspecified or any(address in network for network in EXAMPLE_NETWORKS)):
            findings.add('non-example network address')
    return sorted(findings)


def packaged_files():
    if (ROOT / '.git').exists():
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        return [ROOT / name for name in names if name]
    result = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in GENERATED and not d.startswith('.venv')]
        result.extend(Path(base) / name for name in names if name != '.env' and not name.endswith(('.pyc', '.log')))
    return sorted(result)


def inspect_files(files):
    failures = []
    digest = hashlib.sha256()
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            failures.append([name, 'tracked symlink requires review'])
            continue
        if path.stat().st_size > MAX_ASSET_BYTES or path.suffix in PROHIBITED:
            failures.append([name, 'large/generated/model/credential artifact'])
        if path.name.startswith('.env') and path.name != '.env.example':
            failures.append([name, 'local environment file'])
        content = path.read_bytes()
        failures.extend([name, label] for label in find_sensitive(content))
        digest.update(name.encode() + b'\0' + hashlib.sha256(content).digest())
    return failures, digest.hexdigest()


def inspect_history():
    """Inspect all reachable commits, including data deleted in a later commit."""
    if not (ROOT / '.git').exists():
        return [], 0
    commits = subprocess.check_output(['git', 'rev-list', '--all'], cwd=ROOT, text=True).splitlines()
    failures = []
    seen = set()
    for commit in commits:
        meta = subprocess.check_output(['git', 'show', '-s', '--format=%ae%n%ce', commit], cwd=ROOT, text=True).splitlines()
        if any(not email.endswith('@users.noreply.github.com') for email in meta):
            failures.append(['(commit metadata)', 'non-no-reply author email'])
        message = subprocess.check_output(['git', 'show', '-s', '--format=%B', commit], cwd=ROOT)
        failures.extend(['(commit message)', label] for label in find_sensitive(message))
        entries = subprocess.check_output(['git', 'ls-tree', '-r', '-z', commit], cwd=ROOT).split(b'\0')
        for entry in entries:
            if not entry:
                continue
            header, raw_name = entry.split(b'\t', 1)
            mode, kind, blob = header.decode().split()
            if kind != 'blob' or blob in seen:
                continue
            seen.add(blob)
            name = raw_name.decode()
            data = subprocess.check_output(['git', 'cat-file', 'blob', blob], cwd=ROOT)
            failures.extend([name + ' (history)', label] for label in find_sensitive(data))
            if mode == '120000' or len(data) > MAX_ASSET_BYTES or Path(name).suffix in PROHIBITED or (Path(name).name.startswith('.env') and Path(name).name != '.env.example'):
                failures.append([name + ' (history)', 'prohibited historical artifact'])
    return failures, len(commits)


def main():
    files = packaged_files()
    findings, digest = inspect_files(files)
    historical, commits = inspect_history()
    findings.extend(historical)
    print(json.dumps({'status': 'FAIL' if findings else 'PASS', 'files': len(files),
                      'history_commits': commits, 'content_sha256': digest,
                      'findings': findings,
                      'note': 'Heuristic scan; manual asset/privacy review remains required.'}, indent=2))
    raise SystemExit(bool(findings))


if __name__ == '__main__':
    main()
