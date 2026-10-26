#!/usr/bin/env python3
"""Request an explicit model replacement; architecture selection never calls this."""
import argparse
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.end_to_end import request_model
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('model', choices=['moshi', 'nemotron'])
parser.add_argument('--directory', type=Path, default=Path(os.environ.get('VOICE_DEMO_SLOT_DIRECTORY', ROOT / 'runtime/end-to-end')))
args = parser.parse_args()
print(json.dumps(request_model(args.directory, args.model), indent=2))
