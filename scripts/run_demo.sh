#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
cd "$VOICE_DEMO_ROOT"
[[ -x "$VOICE_DEMO_TOOLS_PYTHON" ]] || {
  echo "Tools Python missing. Run: bash scripts/setup.sh" >&2
  exit 2
}
exec "$VOICE_DEMO_TOOLS_PYTHON" scripts/run_demo.py "$@"
