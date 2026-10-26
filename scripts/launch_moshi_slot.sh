#!/usr/bin/env bash
# Supervisor-owned Moshi slot: official server + CPU PCM/Opus adapter (no diagnostics).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

: "${VOICE_DEMO_SLOT_RUN:?VOICE_DEMO_SLOT_RUN must be supplied by the end-to-end supervisor}"

export MOSHI_HOST="${MOSHI_HOST:-127.0.0.1}"
export MOSHI_PORT="${MOSHI_PORT:-8998}"
adapter_host="${VOICE_DEMO_MOSHI_ADAPTER_HOST:-127.0.0.1}"
adapter_port="${VOICE_DEMO_MOSHI_ADAPTER_PORT:-9005}"
ready_file="${VOICE_DEMO_SLOT_RUN}/validation/summary.json"
mkdir -p "$(dirname "$ready_file")"

bash "$root/scripts/run_moshi.sh" &
voice_native_pid=$!
tools_python="${VOICE_DEMO_TOOLS_PYTHON}"
"$tools_python" -m services.moshi.adapter \
  --native-url "ws://127.0.0.1:${MOSHI_PORT}/api/chat" \
  --host "$adapter_host" \
  --port "$adapter_port" \
  --ready-file "$ready_file" &
voice_adapter_pid=$!

cleanup() {
  kill "$voice_native_pid" "$voice_adapter_pid" 2>/dev/null || true
  wait "$voice_native_pid" 2>/dev/null || true
  wait "$voice_adapter_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# If either process exits, tear down the slot process group.
wait -n "$voice_native_pid" "$voice_adapter_pid"
exit_code=$?
trap - EXIT INT TERM
cleanup
exit "$exit_code"
