#!/usr/bin/env bash
#SBATCH --job-name=voice-demo-ui
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=08:00:00
#
# Generic CPU-only UI/proxy template. Caller must supply:
#   sbatch --partition=... --qos=... --chdir=<repo> -o <log> -e <log> ...
# Prefer scripts/submit_slurm.sh --service ui ...

set -euo pipefail
ROOT="${VOICE_DEMO_ROOT:-$PWD}"
cd "$ROOT"
# shellcheck disable=SC1091
source scripts/common.sh

# Static files, proxy sockets, and health/control APIs only. No GPU inference.
export VOICE_DEMO_UI_HOST="${VOICE_DEMO_UI_HOST:-0.0.0.0}"
export VOICE_DEMO_UI_PORT="${VOICE_DEMO_UI_PORT:-7860}"
exec "$VOICE_DEMO_TOOLS_PYTHON" -u scripts/run_demo.py
