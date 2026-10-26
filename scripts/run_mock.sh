#!/usr/bin/env bash
# Local UI with mock backends only (no model downloads or GPU).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
cd "$VOICE_DEMO_ROOT"
[[ -x "$VOICE_DEMO_TOOLS_PYTHON" ]] || {
  echo "Tools Python missing. Run: bash scripts/setup.sh" >&2
  exit 2
}
# UI-only mode must not inherit real backend or model-control routes.
unset VOICE_DEMO_MODULAR_URL VOICE_DEMO_MOSHI_URL VOICE_DEMO_NEMOTRON_URL
unset VOICE_DEMO_SLOT_CONTROL VOICE_DEMO_SLOT_DIRECTORY VOICE_DEMO_REPLAY
export VOICE_DEMO_UI_HOST="${VOICE_DEMO_UI_HOST:-127.0.0.1}"
export VOICE_DEMO_UI_PORT="${VOICE_DEMO_UI_PORT:-7860}"
exec "$VOICE_DEMO_TOOLS_PYTHON" scripts/run_demo.py "$@"
