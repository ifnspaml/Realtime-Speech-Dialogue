#!/usr/bin/env bash
#SBATCH --job-name=voice-end-to-end
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#
# Generic resident end-to-end GPU template (default Moshi). Caller must supply
# partition, QoS, chdir, logs, and exactly one typed --gres=gpu:<type>:1.
# One supervised resident E2E model; UI switches never sbatch or replace weights.
# Prefer scripts/submit_slurm.sh --service end-to-end --gres gpu:TYPE:1 ...

set -euo pipefail
ROOT="${VOICE_DEMO_ROOT:-$PWD}"
cd "$ROOT"
# shellcheck disable=SC1091
source scripts/common.sh

if [[ -z "${SLURM_JOB_GPUS:-}" && -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  echo "Submit with --gres=gpu:<type>:1 so SLURM_JOB_GPUS or CUDA_VISIBLE_DEVICES is set" >&2
  exit 2
fi

mkdir -p artifacts/end-to-end

exec "$VOICE_DEMO_TOOLS_PYTHON" -u -m services.end_to_end --initial "${VOICE_DEMO_INITIAL_MODEL:-moshi}"
