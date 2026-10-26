#!/usr/bin/env bash
# Run browser validation using the project-pinned Playwright Chromium.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

[[ -x "$VOICE_DEMO_TOOLS_PYTHON" ]] || {
  echo "Tools Python missing. Run: bash scripts/setup.sh" >&2
  exit 2
}

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${VOICE_DEMO_ROOT}/models/browsers}"
# Optional operator-supplied library path (no mandatory cluster unpack).
if [[ -n "${VOICE_DEMO_BROWSER_LD_LIBRARY_PATH:-}" ]]; then
  export LD_LIBRARY_PATH="${VOICE_DEMO_BROWSER_LD_LIBRARY_PATH}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi

exec "$VOICE_DEMO_TOOLS_PYTHON" tests/browser/validate.py "$@"
