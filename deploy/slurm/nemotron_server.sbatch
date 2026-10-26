#!/usr/bin/env bash
#SBATCH --job-name=voice-nemotron
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#
# Optional direct Nemotron GPU template. Caller must supply partition, QoS,
# chdir, logs, and exactly one typed --gres=gpu:<type>:1.
# Prefer scripts/submit_slurm.sh --service nemotron --gres gpu:TYPE:1 ...
# Requires prior explicit scripts/prepare_nemotron.sh (NGC license/access).

set -euo pipefail
ROOT="${VOICE_DEMO_ROOT:-$PWD}"
cd "$ROOT"
# shellcheck disable=SC1091
source scripts/common.sh

if [[ -z "${SLURM_JOB_GPUS:-}" && -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  echo "Submit with --gres=gpu:<type>:1 so SLURM_JOB_GPUS or CUDA_VISIBLE_DEVICES is set" >&2
  exit 2
fi

mkdir -p artifacts/nemotron

exec bash scripts/run_nemotron.sh
