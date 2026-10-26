#!/usr/bin/env bash
# Default: UI/tools environment only. Pass --modular / --moshi / --nemotron for backends.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

with_modular=0
with_moshi=0
with_nemotron=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --modular) with_modular=1 ;;
    --moshi) with_moshi=1 ;;
    --nemotron) with_nemotron=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/setup.sh [--modular] [--moshi] [--nemotron]

By default installs the UI/tools Python environment only (no model downloads).
  --modular    prepare HF speech-to-speech upstream + .venv-modular
  --moshi      prepare .venv-moshi
  --nemotron   also clone optional NVIDIA-NeMo/Speech upstream (no container/model pull)
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (see --help)" >&2
      exit 2
      ;;
  esac
  shift
done

voice_demo_require_cmd uv
mkdir -p logs artifacts models "$UV_CACHE_DIR"

if [[ ! -x "$VOICE_DEMO_TOOLS_PYTHON" ]]; then
  uv venv --python 3.11 "$root/.venv-tools"
fi
uv pip sync --python "$VOICE_DEMO_TOOLS_PYTHON" --link-mode=copy requirements-tools.lock

upstream_args=()
if (( with_nemotron )); then
  upstream_args+=(--nemotron)
fi
if (( with_modular || with_nemotron )); then
  bash "$root/scripts/setup_upstreams.sh" "${upstream_args[@]}"
fi

if (( with_modular )); then
  bash "$root/scripts/setup_modular.sh"
fi
if (( with_moshi )); then
  bash "$root/scripts/setup_moshi.sh"
fi

echo "Tools environment ready: $VOICE_DEMO_TOOLS_PYTHON"
echo "Model weights are not downloaded here; use scripts/prepare_models.py --backend modular|moshi."
if (( ! with_modular && ! with_moshi )); then
  echo "Backends skipped (pass --modular and/or --moshi to prepare them)."
fi
