#!/usr/bin/env bash
# Launch modular HF speech-to-speech offline from project caches (no downloads).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

[[ -x "$VOICE_DEMO_BACKEND_PYTHON" ]] || {
  echo "Modular Python missing ($VOICE_DEMO_BACKEND_PYTHON). Run: bash scripts/setup.sh --modular" >&2
  exit 2
}
[[ -d "$HF_S2S_REPO" ]] || {
  echo "Upstream repo missing ($HF_S2S_REPO). Run: bash scripts/setup_upstreams.sh" >&2
  exit 2
}
[[ "${VOICE_DEMO_STT:-parakeet-tdt}" == parakeet-tdt ]] || {
  echo "This demo requires the official default audio-only Parakeet STT (parakeet-tdt)" >&2
  exit 2
}

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

"$VOICE_DEMO_TOOLS_PYTHON" "$VOICE_DEMO_ROOT/scripts/prepare_models.py" --backend modular --verify-only
voice_demo_modular_libraries

cd "$HF_S2S_REPO"
echo "Official audio-only STT: parakeet-tdt; source: $HF_S2S_REPO; HF_HOME=$HF_HOME"
exec "$VOICE_DEMO_BACKEND_PYTHON" "$VOICE_DEMO_ROOT/scripts/backend_entry.py" serve \
  --device "${VOICE_DEMO_DEVICE:-cuda}" \
  --stt parakeet-tdt \
  --llm_backend "${VOICE_DEMO_LLM_BACKEND:-transformers}" \
  --tts "${VOICE_DEMO_TTS:-qwen3}" \
  --qwen3_tts_backend ggml \
  --model_name "${VOICE_DEMO_LLM_MODEL:-Qwen/Qwen3-4B-Instruct-2507}" \
  --llm_device "${VOICE_DEMO_LLM_DEVICE:-cuda}" \
  --llm_torch_dtype float16 \
  --enable_live_transcription \
  --host "${VOICE_DEMO_MODULAR_HOST:-0.0.0.0}" \
  --port "${VOICE_DEMO_MODULAR_PORT:-8765}" "$@"
