#!/usr/bin/env bash
# Reusable Nemotron VoiceChat launch (Singularity/Apptainer/Docker) or health probe.
# Does not download models/images; prepare_nemotron.sh must have been run explicitly.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
cd "$VOICE_DEMO_ROOT"

mode=launch
if [[ "${1:-}" == "--health" ]]; then
  mode=health
  shift
fi

NEMOTRON_MODEL_DIR="${NEMOTRON_MODEL_DIR:-${VOICE_DEMO_ROOT}/models/nemotron-labs-voicechat_v1.0.0}"
runtime="${VOICE_DEMO_CONTAINER_RUNTIME:-singularity}"
if [[ -n "${VOICE_DEMO_NEMOTRON_IMAGE:-}" ]]; then
  image="$VOICE_DEMO_NEMOTRON_IMAGE"
elif [[ "$runtime" == docker ]]; then
  digest="$("$VOICE_DEMO_TOOLS_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["manifest_digest"])' "$VOICE_DEMO_ROOT/services/nemotron/runtime.json")"
  image="docker://nvcr.io/nim/nvidia/nemotron-labs-voicechat@${digest}"
else
  image="${VOICE_DEMO_ROOT}/models/voicechat.sif"
fi
export NIM_HTTP_API_PORT="${NIM_HTTP_API_PORT:-9000}"
endpoint="${VOICE_DEMO_NEMOTRON_HTTP:-http://127.0.0.1:${NIM_HTTP_API_PORT}}"

if [[ "$mode" == health ]]; then
  deadline=$((SECONDS + ${VOICE_DEMO_READY_TIMEOUT:-1500}))
  echo "Checking Nemotron VoiceChat health at ${endpoint}/v1/realtime/health"
  until response="$(curl -fsS --max-time 5 "${endpoint}/v1/realtime/health")" && \
    python3 -c 'import json,sys; p=json.load(sys.stdin); sys.exit(0 if p.get("status")=="ok" and p.get("triton_status")=="ready" and p.get("mode")=="triton" else 1)' <<<"$response"; do
    if (( SECONDS >= deadline )); then
      echo "Nemotron readiness timed out" >&2
      exit 1
    fi
    echo "Nemotron is not ready yet; waiting 10 seconds"
    sleep 10
  done
  echo "$response"
  echo "Set VOICE_DEMO_NEMOTRON_URL=ws://<reachable-host>:${NIM_HTTP_API_PORT}/v1/realtime for the UI."
  exit 0
fi

[[ -f "$NEMOTRON_MODEL_DIR/verification.json" ]] || {
  echo "Official model repository not verified at $NEMOTRON_MODEL_DIR" >&2
  echo "Run scripts/prepare_nemotron.sh explicitly (NGC access and license required)." >&2
  exit 2
}
[[ -e "$image" || "$image" == docker://* ]] || {
  echo "Container image missing: $image (run scripts/prepare_nemotron.sh)" >&2
  exit 2
}

if [[ -z "${SLURM_JOB_GPUS:-${CUDA_VISIBLE_DEVICES:-}}" ]]; then
  echo "GPU visibility required: set CUDA_VISIBLE_DEVICES or submit with --gres so SLURM_JOB_GPUS is set" >&2
  exit 2
fi

mkdir -p artifacts/nemotron
voice_job_cache="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}/voicechat-${SLURM_JOB_ID:-$$}"
mkdir -p "$voice_job_cache"

export SINGULARITYENV_NIM_HTTP_API_PORT="$NIM_HTTP_API_PORT"
export APPTAINERENV_NIM_HTTP_API_PORT="$NIM_HTTP_API_PORT"
export SINGULARITYENV_CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:?CUDA_VISIBLE_DEVICES must expose the allocated GPU}"
export SINGULARITYENV_XDG_CACHE_HOME=/voice-cache
export SINGULARITYENV_VLLM_CACHE_ROOT=/voice-cache/vllm
export SINGULARITYENV_HF_HUB_OFFLINE=1
export APPTAINERENV_CUDA_VISIBLE_DEVICES="$SINGULARITYENV_CUDA_VISIBLE_DEVICES"
export APPTAINERENV_XDG_CACHE_HOME=/voice-cache
export APPTAINERENV_VLLM_CACHE_ROOT=/voice-cache/vllm
export APPTAINERENV_HF_HUB_OFFLINE=1

if [[ "$runtime" == apptainer || "$runtime" == singularity ]]; then
  command -v "$runtime" >/dev/null || {
    echo "$runtime is not available on this node" >&2
    exit 2
  }
  exec "$runtime" exec --cleanenv --nv --writable-tmpfs \
    --bind "$NEMOTRON_MODEL_DIR:/data/models,$voice_job_cache:/voice-cache" \
    "$image" /s2s/run_s2s_server.sh
elif [[ "$runtime" == docker ]]; then
  command -v docker >/dev/null || {
    echo "docker is not available on this node" >&2
    exit 2
  }
  docker_image="$image"
  if [[ "$docker_image" == docker://* ]]; then
    docker_image="${docker_image#docker://}"
  fi
  exec docker run --pull=never --rm --runtime=nvidia --gpus "device=${SLURM_JOB_GPUS:-${CUDA_VISIBLE_DEVICES}}" \
    --shm-size=8GB \
    -e NIM_HTTP_API_PORT \
    -p "$NIM_HTTP_API_PORT:$NIM_HTTP_API_PORT" \
    -v "$NEMOTRON_MODEL_DIR:/data/models" \
    --entrypoint /s2s/run_s2s_server.sh \
    "$docker_image"
else
  echo "Set VOICE_DEMO_CONTAINER_RUNTIME to singularity, apptainer, or docker" >&2
  exit 2
fi
