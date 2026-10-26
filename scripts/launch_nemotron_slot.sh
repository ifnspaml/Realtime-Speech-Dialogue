#!/usr/bin/env bash
# Supervisor-owned Nemotron slot: launch the official container (never re-enters sbatch).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

export VOICE_DEMO_SKIP_GPU_MONITOR="${VOICE_DEMO_SKIP_GPU_MONITOR:-1}"
exec bash "$root/scripts/run_nemotron.sh"
