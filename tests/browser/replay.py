#!/usr/bin/env python3
"""Run checksum-verified developer fixtures through the browser; no live inference."""
import argparse
import asyncio
import os
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services.mock.server import Server
from services.replay import ReplayHandler
from tests.browser.real_backend import main
from tests.browser.moshi import main as moshi_main


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['modular', 'nemotron', 'moshi'], required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    os.environ['VOICE_DEMO_REPLAY'] = '1'
    source_status = json.loads((args.fixture / 'summary.json').read_text())['status']
    with Server(('127.0.0.1', 0), ReplayHandler) as replay:
        replay.fixture_directory = args.fixture
        threading.Thread(target=replay.serve_forever, daemon=True).start()
        try:
            if args.backend == 'moshi':
                asyncio.run(moshi_main(argparse.Namespace(mock=False, switch=False, ui_url=None, measurement='replay',
                    url=f'ws://127.0.0.1:{replay.server_address[1]}/replay', wav=ROOT/'artifacts/input/browser.wav',
                    output=ROOT/'artifacts/replay/moshi')))
            else:
                asyncio.run(main(argparse.Namespace(backend=args.backend,
                url=f'ws://127.0.0.1:{replay.server_address[1]}/replay',
                wav=ROOT / 'artifacts/input/browser.wav',
                output=ROOT / f"artifacts/replay/{args.backend}", measurement='replay', source_validation_status=source_status)))
        finally:
            replay.shutdown()
