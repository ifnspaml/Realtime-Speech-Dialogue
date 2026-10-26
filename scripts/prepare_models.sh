#!/usr/bin/env bash
# Explicit pinned model preparation, honoring the same trusted .env as launchers.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
exec "$VOICE_DEMO_TOOLS_PYTHON" "$VOICE_DEMO_ROOT/scripts/prepare_models.py" "$@"
