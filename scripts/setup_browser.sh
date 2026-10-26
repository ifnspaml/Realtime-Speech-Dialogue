#!/usr/bin/env bash
# Install project-pinned Playwright Chromium into PLAYWRIGHT_BROWSERS_PATH.
# Does not run apt-get or install system packages; host libraries are documented.
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
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"

"$VOICE_DEMO_TOOLS_PYTHON" -m playwright install chromium

cat <<EOF
Playwright Chromium installed under: $PLAYWRIGHT_BROWSERS_PATH

Host libraries are NOT installed by this script. On typical Linux desktops/CI
images you may need packages providing (names vary by distro):
  libnss3, libnspr4, libatk-1.0, libatk-bridge-2.0, libcups2, libdrm2,
  libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3, libxrandr2,
  libgbm1, libasound2, libpango-1.0, libcairo2, libgtk-3-0

Operators may export an additional LD_LIBRARY_PATH for local library trees.
See docs/dependency-notes.md. Cluster-specific deb unpacking is optional and
not required by this portable setup.
EOF
