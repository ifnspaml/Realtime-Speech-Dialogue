#!/usr/bin/env python3
"""Build a pinned Moshi wheel with a documented HTTP dependency compatibility patch.

No inference implementation is changed. Retains upstream MIT/Audiocraft notices.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.2.13+ifn.1'
URL = 'https://files.pythonhosted.org/packages/12/22/7caa82b67ef874d7dc126b91591b7a8349250b48d2e999aa1d5284446c9b/moshi-0.2.13.tar.gz'
SHA256 = 'f0c83aea037b1e2e3aefe5f9c2e77a0d6b5ec9b7d4e986e259990f6636706eac'


def main():
    output = ROOT / 'artifacts/moshi/wheels'
    output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Upstream Moshi source archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='moshi-wheel-') as temporary:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for item in archive.getmembers():
                if Path(item.name).is_absolute() or '..' in Path(item.name).parts or item.issym() or item.islnk():
                    raise ValueError('Unsafe Moshi source archive entry')
            archive.extractall(temporary)
        source = Path(temporary) / 'moshi-0.2.13'
        project = source / 'pyproject.toml'
        text = project.read_text()
        old = '"aiohttp>=3.10.5, <3.12"'
        assert text.count(old) == 1, 'Upstream dependency metadata changed'
        text = text.replace(old, '"aiohttp>=3.14.5, <4"')
        text = text.replace('requires = ["setuptools"]', 'requires = ["setuptools==83.0.0", "wheel==0.45.1"]')
        project.write_text(text)
        version = source / 'moshi/__init__.py'
        original = version.read_text()
        assert original.count('__version__ = "0.2.13"') == 1
        version.write_text(original.replace('__version__ = "0.2.13"', f'__version__ = "{VERSION}"'))
        environment = dict(os.environ, SOURCE_DATE_EPOCH='1792368000')
        subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(output), str(source)], check=True, env=environment)
    wheel = output / ('moshi-' + VERSION + '-py3-none-any.whl')
    provenance = {'source_url': URL, 'source_sha256': SHA256, 'version': VERSION,
                  'changes': ['aiohttp dependency >=3.14.5,<4', 'local package version', 'pinned build tooling'],
                  'inference_code_changes': False,
                  'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print('Built dependency-patched Moshi wheel; inference code is unchanged.')


if __name__ == '__main__':
    main()
