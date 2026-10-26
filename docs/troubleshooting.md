# Troubleshooting and validation commands

## Readiness or connection failure

Check `/api/config` and `/api/status` on the CPU UI, then `/health` on the Moshi
adapter or the upstream readiness route. A configured but unreachable URL is not
READY. Ensure the UI process can reach each backend host and port, and the
browser uses same-origin `/backend/...` routes. Use the correct listen host for
services on different machines. Keep backend and operator endpoints private.

Offline cache verification errors require explicit model preparation or a new
private snapshot tree; do not disable offline mode and let a live demo replace
models automatically. Run `prepare_models.py --backend all --verify-only
--checksum`. Revision, size or checksum failures must be investigated rather
than overwritten in a shared cache.

CUDA or GGML load failures: use the correct separate Python environment and a
driver supporting its CUDA version. Check `uv pip check --python ENV/bin/python`.
Do not borrow another installation's site-packages or add external `.pth` files.
The modular launcher adds its own CUDA 12/13 native libraries only for modular.

## Microphone, audio and reset

Use localhost or HTTPS, grant microphone permission, and check the selected OS
input/output device. Details shows captured PCM level/duration and accepted-send
duration; neither proves recognition. Browser autoplay can require a user click.
Moshi has no user transcription, so an empty user transcript is expected.

Reset clears UI history and local playback but keeps model context. Reconnect
starts a new session; switching architecture also starts a new session without
reloading weights. After preemption or a network stall, reconnect explicitly.
Only one session can own each current backend. Continuous Moshi audio and
long modular responses can exceed the bounded playback queue; keep prompts
short for a live presentation and inspect visible overflow counters.

## CPU/browser checks

Run README unit/integration tests first. Install Chromium and generate fresh
synthetic WAV inputs before browser tests. With project-local browser binaries:

```bash
export PLAYWRIGHT_BROWSERS_PATH="$PWD/models/browsers"
.venv-tools/bin/python tests/browser/presentation.py
.venv-tools/bin/python tests/browser/demo_timer.py
.venv-tools/bin/python tests/browser/moshi.py --mock --switch --output artifacts/browser-moshi-mock
```

These use synthetic backends and a fake microphone/camera. Reports and screenshots
are ignored artifacts, not model evidence. For all browser scripts requiring an
extra local host-library tree, set `LD_LIBRARY_PATH` only in that command's
environment; `run_browser_tests.sh` also accepts `VOICE_DEMO_BROWSER_LD_LIBRARY_PATH`.

A synthetic replay can be generated locally, never mistaken for live inference:

```bash
.venv-tools/bin/python -m tests.fixtures.replay_fixture --output artifacts/replay-synthetic
VOICE_DEMO_REPLAY_FIXTURE=artifacts/replay-synthetic .venv-tools/bin/python -m services.replay
```

Check fixture/backend options with `--help`. No real voice recording is shipped.

## Live checks on independently allocated services

Only run these against a backend you own or are authorized to occupy; they
consume its single dialogue session. No script should replace a model:

```bash
.venv-tools/bin/python scripts/moshi_wav.py --help
.venv-tools/bin/python scripts/realtime_wav.py --help
.venv-tools/bin/python tests/browser/real_backend.py --backend modular   --url ws://MODULAR_HOST:8765/v1/realtime --output artifacts/browser-modular-real
VOICE_DEMO_MODULAR_URL=ws://MODULAR_HOST:8765/v1/realtime   .venv-tools/bin/python tests/browser/moshi.py   --url ws://MOSHI_HOST:9005/v1/realtime --switch --output artifacts/browser-switch-real
```

Fake microphone input exercises real inference but does not verify physical
microphone/speaker acoustics or subjective dialogue quality. Do not report mock,
replay or a transport-only WAV probe as real semantic validation. Record software
and device provenance, final scheduler exit codes and actual output hashes.
Optional Nemotron requires its official runtime plus separate live validation.
