#!/usr/bin/env bash
# Generic Slurm submit helper. Operators supply partition, QoS, and typed GRES.
# Does not scan accounts, auto-promote QoS, or claim cluster-capacity scheduling.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

service=""
partition="${VOICE_DEMO_SLURM_PARTITION:-}"
qos="${VOICE_DEMO_SLURM_QOS:-}"
gres=""
time_limit=""
cpus=""
mem=""
job_name=""

usage() {
  cat <<'EOF'
Usage: scripts/submit_slurm.sh --service ui|modular|end-to-end|nemotron \
  --partition <name> --qos <name> [--gres gpu:<type>:1] [options]

Required operator choices (never inferred from a personal cluster policy):
  --service      ui (CPU), modular, end-to-end, or nemotron
  --partition    Slurm partition
  --qos          Slurm QoS
  --gres         Exactly one typed GPU for GPU services (e.g. gpu:TYPE:1)

Optional:
  --time         Walltime override (default from template / service)
  --cpus         CPUs-per-task override
  --mem          Memory override
  --job-name     Job name override

Environment:
  VOICE_DEMO_SUBMIT_LOCK   Optional shared flock path for cooperating operators
  Logs under logs/; durable receipts under artifacts/slurm/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service) service="${2:?}"; shift 2 ;;
    --partition) partition="${2:?}"; shift 2 ;;
    --qos) qos="${2:?}"; shift 2 ;;
    --gres) gres="${2:?}"; shift 2 ;;
    --time) time_limit="${2:?}"; shift 2 ;;
    --cpus) cpus="${2:?}"; shift 2 ;;
    --mem) mem="${2:?}"; shift 2 ;;
    --job-name) job_name="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$service" && -n "$partition" && -n "$qos" ]] || {
  echo "Require --service, --partition, and --qos as explicit operator choices." >&2
  usage >&2
  exit 2
}

case "$service" in
  ui)
    script="deploy/slurm/demo_ui.sbatch"
    default_time="08:00:00"
    default_cpus=2
    default_mem=4G
    default_name="voice-demo-ui"
    needs_gpu=0
    log_prefix="ui"
    ;;
  modular)
    script="deploy/slurm/modular_server.sbatch"
    default_time="04:00:00"
    default_cpus=16
    default_mem=64G
    default_name="voice-modular"
    needs_gpu=1
    log_prefix="modular"
    ;;
  end-to-end)
    script="deploy/slurm/end_to_end_server.sbatch"
    default_time="04:00:00"
    default_cpus=12
    default_mem=128G
    default_name="voice-end-to-end"
    needs_gpu=1
    log_prefix="end-to-end"
    ;;
  nemotron)
    script="deploy/slurm/nemotron_server.sbatch"
    default_time="04:00:00"
    default_cpus=12
    default_mem=128G
    default_name="voice-nemotron"
    needs_gpu=1
    log_prefix="nemotron"
    ;;
  *)
    echo "Unknown service: $service" >&2
    exit 2
    ;;
esac

if (( needs_gpu )); then
  [[ -n "$gres" ]] || {
    echo "GPU service '$service' requires exactly one typed --gres (e.g. --gres gpu:TYPE:1)" >&2
    exit 2
  }
  if [[ ! "$gres" =~ ^gpu:[A-Za-z0-9_]+:1$ ]]; then
      echo "Expected a single typed GPU GRES like gpu:<type>:1, got: $gres" >&2
      exit 2
  fi
else
  [[ -z "$gres" ]] || {
    echo "UI/proxy submission is CPU-only; omit --gres" >&2
    exit 2
  }
fi

mkdir -p logs artifacts/slurm
bash -n "$script"

time_limit="${time_limit:-$default_time}"
cpus="${cpus:-$default_cpus}"
mem="${mem:-$default_mem}"
job_name="${job_name:-$default_name}"
outfile="logs/${log_prefix}-%j.out"
errfile="logs/${log_prefix}-%j.err"

# Optional cooperating-operator lock (path chosen by operators; not a baked policy).
lock_fd=""
if [[ -n "${VOICE_DEMO_SUBMIT_LOCK:-}" ]]; then
  mkdir -p "$(dirname "$VOICE_DEMO_SUBMIT_LOCK")"
  exec {lock_fd}<>"$VOICE_DEMO_SUBMIT_LOCK"
  flock -w 120 "$lock_fd" || {
    echo "Could not acquire VOICE_DEMO_SUBMIT_LOCK=$VOICE_DEMO_SUBMIT_LOCK" >&2
    exit 2
  }
fi

sbatch_args=(
  --parsable
  --partition="$partition"
  --qos="$qos"
  --chdir="$VOICE_DEMO_ROOT"
  --job-name="$job_name"
  --cpus-per-task="$cpus"
  --mem="$mem"
  --time="$time_limit"
  --output="$VOICE_DEMO_ROOT/$outfile"
  --error="$VOICE_DEMO_ROOT/$errfile"
  --export=ALL
)
if (( needs_gpu )); then
  sbatch_args+=(--gres="$gres")
fi

request_id="$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
intent="artifacts/slurm/request-${request_id}.json"
python3 - "$intent" "$service" "${sbatch_args[@]}" "$script" <<'PY'
import hashlib, json, os, sys, time
path, service, *args = sys.argv[1:]
payload = {"service": service, "arguments": args,
           "script_sha256": hashlib.sha256(open(args[-1], "rb").read()).hexdigest(),
           "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
with open(path, "x", encoding="utf-8") as stream:
    stream.write(json.dumps(payload, indent=2) + "\n")
    stream.flush()
    os.fsync(stream.fileno())
PY
if ! job_id="$(sbatch "${sbatch_args[@]}" --comment="speech-demo:${request_id}" "$script")"; then
  echo "Submission outcome may be uncertain. Inspect squeue/sacct for comment speech-demo:${request_id} before retrying; intent: $intent" >&2
  exit 1
fi
job_id="${job_id%%;*}"
[[ "$job_id" =~ ^[0-9]+$ ]] || {
  echo "Unexpected sbatch response. Reconcile request $request_id with squeue/sacct before retrying." >&2
  exit 1
}
receipt="artifacts/slurm/${log_prefix}-${job_id}.json"
python3 - "$receipt" "$job_id" "$service" "$partition" "$qos" "$gres" "$intent" <<'PY'
import json, os, sys, time
path, job_id, service, partition, qos, gres, intent = sys.argv[1:8]
payload = {
    "job_id": job_id,
    "service": service,
    "partition": partition,
    "qos": qos,
    "gres": gres or None,
    "intent": intent,
    "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "note": "Operator-supplied partition/QoS/GRES; not auto cluster-capacity scheduling.",
}
with open(path, "x", encoding="utf-8") as stream:
    stream.write(json.dumps(payload, indent=2) + "\n")
    stream.flush()
    os.fsync(stream.fileno())
PY

echo "Submitted $service job $job_id (partition=$partition qos=$qos gres=${gres:-none})"
echo "Receipt: $receipt"
echo "Follow cluster operator policy externally; this helper does not change QoS or scan accounts."
