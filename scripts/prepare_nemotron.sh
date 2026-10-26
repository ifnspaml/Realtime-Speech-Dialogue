#!/usr/bin/env bash
# Explicit-only Nemotron preparation: NGC model files + official container image.
# Requires operator NGC access and acceptance of NVIDIA license terms. Does not
# claim fresh inference validation. Not invoked by scripts/setup.sh.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

mkdir -p models artifacts logs
tools_python="${VOICE_DEMO_TOOLS_PYTHON}"
[[ -x "$tools_python" ]] || {
  echo "Tools Python missing. Run: bash scripts/setup.sh" >&2
  exit 2
}

model_dir="${NEMOTRON_MODEL_DIR:-${VOICE_DEMO_ROOT}/models/nemotron-labs-voicechat_v1.0.0}"
runtime="${VOICE_DEMO_CONTAINER_RUNTIME:-singularity}"
provenance_file="${VOICE_DEMO_ROOT}/services/nemotron/runtime.json"
[[ -f "$provenance_file" ]] || {
  echo "Missing frozen runtime provenance: $provenance_file" >&2
  exit 2
}

digest="$(python3 -c 'import json,pathlib,sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())["manifest_digest"])' "$provenance_file")"
image_ref="docker://nvcr.io/nim/nvidia/nemotron-labs-voicechat@${digest}"
if [[ -n "${VOICE_DEMO_NEMOTRON_IMAGE:-}" ]]; then
  image="$VOICE_DEMO_NEMOTRON_IMAGE"
elif [[ "$runtime" == docker ]]; then
  image="$image_ref"
else
  image="${VOICE_DEMO_ROOT}/models/voicechat.sif"
fi

"$tools_python" "$root/scripts/download_ngc.py" --target "$model_dir"

need_pull=0
if [[ "$runtime" == docker ]]; then
  need_pull=1
elif [[ ! -e "$image" ]]; then
  need_pull=1
fi

if (( need_pull )); then
  command -v "$runtime" >/dev/null || {
    echo "Container runtime '$runtime' is required to pull $image_ref" >&2
    exit 2
  }
  cache_dir="${VOICE_DEMO_CONTAINER_CACHE:-${VOICE_DEMO_ROOT}/models/container-cache}"
  mkdir -p "$cache_dir"
  voice_build_directory="$(mktemp -d "${TMPDIR:-/tmp}/voice-demo-container.XXXXXX")"
  trap 'rm -rf "$voice_build_directory"' EXIT
  case "$runtime" in
    singularity|apptainer)
      mkdir -p "$(dirname "$image")"
      SINGULARITY_CACHEDIR="$cache_dir" SINGULARITY_TMPDIR="$voice_build_directory" \
      APPTAINER_CACHEDIR="$cache_dir" APPTAINER_TMPDIR="$voice_build_directory" \
        "$runtime" pull "$image" "$image_ref"
      ;;
    docker)
      docker pull "nvcr.io/nim/nvidia/nemotron-labs-voicechat@${digest}"
      ;;
    *)
      echo "Set VOICE_DEMO_CONTAINER_RUNTIME to singularity, apptainer, or docker" >&2
      exit 2
      ;;
  esac
fi
export VOICE_DEMO_NEMOTRON_IMAGE="$image"

mkdir -p third_party/nvidia-client
if [[ "$runtime" == singularity || "$runtime" == apptainer ]]; then
  for voice_file in nemotron-voicechat-client.py audio_server.py; do
    if [[ ! -f "third_party/nvidia-client/$voice_file" ]]; then
      "$runtime" exec --cleanenv "$image" cat "/s2s/$voice_file" >"third_party/nvidia-client/$voice_file"
    fi
  done
fi

python3 - <<PY
import hashlib
import json
from pathlib import Path
provenance = json.loads(Path(${provenance_file@Q}).read_text())
directory = Path("third_party/nvidia-client")
if directory.is_dir() and any(directory.iterdir()):
    for name, expected in provenance["files"].items():
        path = directory / name
        if not path.is_file():
            raise SystemExit(f"Official client file missing: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(
                f"Official file checksum mismatch: {name}; "
                "preserve local edits before restoring the frozen source"
            )
    (directory / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
print("Nemotron artifacts prepared under", ${model_dir@Q})
print("Fresh end-to-end inference is not claimed by this preparation step.")
PY
