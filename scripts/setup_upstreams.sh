#!/usr/bin/env bash
# Clone and freeze pinned upstreams. Dirty or non-git trees fail instead of overwriting.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

dest="${VOICE_DEMO_UPSTREAM_DIR}"
mkdir -p "$dest"

with_nemotron=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nemotron) with_nemotron=1 ;;
    -h|--help)
      echo "Usage: scripts/setup_upstreams.sh [--nemotron]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

checkout() {
  local url="$1" name="$2" commit="$3"
  local path="$dest/$name"
  if [[ -e "$path" && ! -d "$path/.git" ]]; then
    echo "Upstream path exists but is not a git checkout: $path" >&2
    exit 2
  fi
  if [[ ! -d "$path/.git" ]]; then
    git clone "$url" "$path"
  fi
  if [[ -n "$(git -C "$path" status --porcelain)" ]]; then
    echo "Upstream checkout is modified: $path. Preserve local edits before freezing a revision." >&2
    exit 2
  fi
  local current
  current="$(git -C "$path" rev-parse HEAD 2>/dev/null || true)"
  if [[ "$current" == "$commit" ]]; then
    echo "Upstream already at $commit: $path"
    return 0
  fi
  git -C "$path" fetch --depth 1 origin "$commit" 2>/dev/null \
    || git -C "$path" fetch origin "$commit"
  git -C "$path" checkout --detach "$commit"
  echo "Frozen $name at $commit"
}

# Required for modular backend.
checkout \
  https://github.com/huggingface/speech-to-speech.git \
  hf-speech-to-speech \
  81b688b452ee6b64ff5745b91985e9eb653fcc9f

# Optional Nemotron-related upstream; not pulled during normal UI setup.
if (( with_nemotron )); then
  checkout \
    https://github.com/NVIDIA-NeMo/Speech.git \
    nvidia-speech \
    097dfe9e2f55baf653b83035868bdc89849f1b47
fi
