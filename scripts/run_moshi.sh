#!/usr/bin/env bash
# Launch the pinned official Moshi server from a local snapshot (never downloads).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

voice_python="${VOICE_DEMO_MOSHI_PYTHON}"
[[ -x "$voice_python" ]] || {
  echo "Moshi Python missing ($voice_python). Run: bash scripts/setup.sh --moshi" >&2
  exit 2
}

voice_snapshot="$(voice_demo_moshi_snapshot)"
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1
export PYTHONNOUSERSITE=1
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-${VOICE_DEMO_ROOT}/models/moshi-compiler-cache}"
mkdir -p "$TORCHINDUCTOR_CACHE_DIR"

for voice_file in \
  model.safetensors \
  tokenizer-e351c8d8-checkpoint125.safetensors \
  tokenizer_spm_32k_3.model
do
  if [[ ! -f "$voice_snapshot/$voice_file" ]]; then
    echo "Moshi snapshot file missing: $voice_snapshot/$voice_file" >&2
    echo "Set VOICE_DEMO_MOSHI_SNAPSHOT or run scripts/prepare_models.py --backend moshi" >&2
    exit 2
  fi
done

"$VOICE_DEMO_TOOLS_PYTHON" - "$VOICE_DEMO_ROOT/config/models.json" "$voice_snapshot" <<'PYTHON'
import json, sys
from pathlib import Path
entry = next(v for v in json.load(open(sys.argv[1]))['models'] if v['key'] == 'moshi')
for name, metadata in entry['files'].items():
    if (Path(sys.argv[2]) / name).stat().st_size != metadata['bytes']:
        raise SystemExit('Moshi file size differs from the pinned release; verify checksums before launch')
PYTHON

cd "$VOICE_DEMO_ROOT"
exec "$voice_python" -m moshi.server \
  --host "${MOSHI_HOST:-127.0.0.1}" \
  --port "${MOSHI_PORT:-8998}" \
  --static none \
  --hf-repo kyutai/moshiko-pytorch-bf16 \
  --moshi-weight "$voice_snapshot/model.safetensors" \
  --mimi-weight "$voice_snapshot/tokenizer-e351c8d8-checkpoint125.safetensors" \
  --tokenizer "$voice_snapshot/tokenizer_spm_32k_3.model"
