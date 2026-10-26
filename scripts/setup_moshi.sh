#!/usr/bin/env bash
# Project-owned Moshi/Moshiko runtime from requirements-moshi.lock (Python 3.12).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

voice_demo_require_cmd uv
mkdir -p "$UV_CACHE_DIR" artifacts/moshi

if [[ ! -x "$VOICE_DEMO_MOSHI_PYTHON" ]]; then
  uv venv --python 3.12 "$root/.venv-moshi"
fi

"$VOICE_DEMO_TOOLS_PYTHON" "$root/scripts/build_moshi.py"

# Exact lock. Torch 2.7.1+cu128 from the official cu128 wheel index.
uv pip sync \
  --python "$VOICE_DEMO_MOSHI_PYTHON" \
  --link-mode=copy \
  --find-links "$root/artifacts/moshi/wheels" \
  --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  requirements-moshi.lock

uv pip freeze --python "$VOICE_DEMO_MOSHI_PYTHON" >artifacts/moshi/environment.lock
echo "Moshi environment ready: $VOICE_DEMO_MOSHI_PYTHON"
echo "Download the pinned Moshiko snapshot with scripts/prepare_models.py --backend moshi"
