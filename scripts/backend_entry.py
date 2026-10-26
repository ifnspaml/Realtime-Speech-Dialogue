#!/usr/bin/env python3
"""Launch the unmodified official CLI with bounded startup diagnostics."""
import time

started = time.monotonic()
print("Importing the official CLI and pipeline", flush=True)
from speech_to_speech import cli, s2s_pipeline
print(f"Official CLI imports completed in {time.monotonic() - started:.1f}s", flush=True)
cli.main()
