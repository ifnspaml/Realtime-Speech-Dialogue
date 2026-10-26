#!/usr/bin/env bash
# Shared environment for Speech Dialogue Demo launchers (project-local only).
# shellcheck disable=SC2034

VOICE_DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export VOICE_DEMO_ROOT

# Optional trusted shell-compatible env file. Override path with VOICE_DEMO_ENV_FILE.
voice_demo_env_file="${VOICE_DEMO_ENV_FILE:-${VOICE_DEMO_ROOT}/.env}"
if [[ -f "$voice_demo_env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$voice_demo_env_file"
  set +a
fi
unset voice_demo_env_file

export VOICE_DEMO_UPSTREAM_DIR="${VOICE_DEMO_UPSTREAM_DIR:-${VOICE_DEMO_ROOT}/third_party}"
export HF_S2S_REPO="${HF_S2S_REPO:-${VOICE_DEMO_UPSTREAM_DIR}/hf-speech-to-speech}"

export VOICE_DEMO_TOOLS_PYTHON="${VOICE_DEMO_TOOLS_PYTHON:-${VOICE_DEMO_ROOT}/.venv-tools/bin/python}"
export VOICE_DEMO_BACKEND_PYTHON="${VOICE_DEMO_BACKEND_PYTHON:-${VOICE_DEMO_ROOT}/.venv-modular/bin/python}"
export VOICE_DEMO_MOSHI_PYTHON="${VOICE_DEMO_MOSHI_PYTHON:-${VOICE_DEMO_ROOT}/.venv-moshi/bin/python}"

export HF_HOME="${VOICE_DEMO_HF_HOME:-${HF_HOME:-${VOICE_DEMO_ROOT}/models/huggingface}}"
export HF_HUB_CACHE="${HF_HOME}/hub"
export HUGGINGFACE_HUB_CACHE="$HF_HUB_CACHE"
export TORCH_HOME="${VOICE_DEMO_TORCH_HOME:-${TORCH_HOME:-${VOICE_DEMO_ROOT}/models/torch}}"
export NLTK_DATA="${VOICE_DEMO_NLTK_DATA:-${NLTK_DATA:-${VOICE_DEMO_ROOT}/models/nltk_data}}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${VOICE_DEMO_ROOT}/.cache/uv}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PYTHONPATH="${VOICE_DEMO_ROOT}:${HF_S2S_REPO}/src"

# Scope native CUDA libraries to the modular process only.
voice_demo_modular_libraries() {
# Project-local CUDA 13 + CUDA 12 libs from the modular venv (GGML native binary).
voice_demo_modular_site="$("$VOICE_DEMO_BACKEND_PYTHON" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
if [[ -d "$voice_demo_modular_site" ]]; then
  for voice_demo_library in \
    nvidia/cuda_runtime/lib \
    nvidia/cuda_runtime_cu12/lib \
    nvidia/cublas/lib \
    nvidia/cublas_cu12/lib \
    nvidia/cuda_nvrtc/lib \
    nvidia/cuda_nvrtc_cu12/lib \
    nvidia/cudnn/lib \
    nvidia/cudnn_cu13/lib \
    nvidia/cu13/lib \
    nvidia/cuda_cupti/lib \
    nvidia/cufft/lib \
    nvidia/curand/lib \
    nvidia/cusolver/lib \
    nvidia/cusparse/lib \
    nvidia/nvjitlink/lib \
    nvidia/nvtx/lib
  do
    voice_demo_directory="${voice_demo_modular_site}/${voice_demo_library}"
    if [[ -d "$voice_demo_directory" ]]; then
      export LD_LIBRARY_PATH="${voice_demo_directory}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
    fi
  done
fi
unset voice_demo_modular_site voice_demo_library voice_demo_directory

}

voice_demo_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 2
  }
}

voice_demo_moshi_snapshot() {
  local snap="${VOICE_DEMO_MOSHI_SNAPSHOT:-}"
  if [[ -z "$snap" ]]; then
    snap="${HF_HOME}/hub/models--kyutai--moshiko-pytorch-bf16/snapshots/2bfc9ae6e89079a5cc7ed2a68436010d91a3d289"
  fi
  printf '%s\n' "$snap"
}
