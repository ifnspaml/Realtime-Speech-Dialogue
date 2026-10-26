#!/usr/bin/env bash
# Start one warm resident end-to-end model, using the shared trusted .env.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
cd "$VOICE_DEMO_ROOT"
exec "$VOICE_DEMO_TOOLS_PYTHON" -u -m services.end_to_end --initial "${VOICE_DEMO_INITIAL_MODEL:-moshi}" "$@"
