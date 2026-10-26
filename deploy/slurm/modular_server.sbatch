#!/usr/bin/env bash
#SBATCH --job-name=voice-modular
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#
# Generic modular GPU template. Caller must supply partition, QoS, chdir, logs,
# and exactly one typed --gres=gpu:<type>:1.
# Prefer scripts/submit_slurm.sh --service modular --gres gpu:TYPE:1 ...

set -euo pipefail
ROOT="${VOICE_DEMO_ROOT:-$PWD}"
cd "$ROOT"
# shellcheck disable=SC1091
source scripts/common.sh

export VOICE_DEMO_MODULAR_HOST="${VOICE_DEMO_MODULAR_HOST:-0.0.0.0}"
export VOICE_DEMO_MODULAR_PORT="${VOICE_DEMO_MODULAR_PORT:-8765}"
export VOICE_DEMO_LLM_DEVICE="${VOICE_DEMO_LLM_DEVICE:-cuda}"

if [[ -z "${SLURM_JOB_GPUS:-}" && -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  echo "Submit with --gres=gpu:<type>:1 so SLURM_JOB_GPUS or CUDA_VISIBLE_DEVICES is set" >&2
  exit 2
fi

mkdir -p artifacts/modular

exec bash scripts/run_modular.sh
