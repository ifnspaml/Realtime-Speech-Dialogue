#!/usr/bin/env bash
# Project-owned modular backend venv from requirements-modular.lock (no shared env reuse).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

voice_demo_require_cmd uv
mkdir -p "$UV_CACHE_DIR" artifacts/modular

if [[ ! -d "$HF_S2S_REPO/.git" ]]; then
  echo "Missing pinned upstream at $HF_S2S_REPO; run scripts/setup_upstreams.sh first" >&2
  exit 2
fi

[[ "$(git -C "$HF_S2S_REPO" rev-parse HEAD)" == 81b688b452ee6b64ff5745b91985e9eb653fcc9f ]] || { echo "Upstream revision differs from the release pin" >&2; exit 2; }

if [[ ! -x "$VOICE_DEMO_BACKEND_PYTHON" ]]; then
  uv venv --python 3.11 "$root/.venv-modular"
fi

# Exact lock install. Torch 2.11.0+cu130 comes from the official cu130 index.
uv pip sync \
  --python "$VOICE_DEMO_BACKEND_PYTHON" \
  --link-mode=copy \
  --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cu130 \
  requirements-modular.lock

# Editable pinned upstream without resolving transitive deps from PyPI.
uv pip install \
  --python "$VOICE_DEMO_BACKEND_PYTHON" \
  --link-mode=copy \
  --no-deps \
  --editable "$HF_S2S_REPO"

mkdir -p artifacts/modular
uv pip freeze --python "$VOICE_DEMO_BACKEND_PYTHON" >artifacts/modular/environment.lock
echo "Modular environment ready: $VOICE_DEMO_BACKEND_PYTHON"
echo "Download model revisions separately with scripts/prepare_models.py --backend modular"
