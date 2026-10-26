#!/usr/bin/env bash
# Synthesize local test utterances with espeak+ffmpeg into ignored artifacts/.
# These are synthetic inputs for ASR/browser exercises, never ASR result fixtures.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$root/scripts/common.sh"

voice_demo_require_cmd espeak
voice_demo_require_cmd ffmpeg

outdir="$VOICE_DEMO_ROOT/artifacts/input"
mkdir -p "$outdir"

espeak -s 145 -w "$outdir/short.wav" 'What is the capital of Germany?'
espeak -s 145 -w "$outdir/long.wav" 'Please explain in one short sentence how a microphone converts sound into an electrical signal.'
espeak -s 145 -w "$outdir/greeting.wav" 'Hello, please introduce yourself briefly.'
espeak -s 145 -w "$outdir/context.wav" 'What city did you just mention?'

printf '%s\n' \
  'short.wav: What is the capital of Germany?' \
  'long.wav: Please explain in one short sentence how a microphone converts sound into an electrical signal.' \
  'greeting.wav: Hello, please introduce yourself briefly.' \
  'context.wav: What city did you just mention?' \
  'note: synthetic espeak audio for local tests; not model outputs' \
  >"$outdir/reference.txt"

ffmpeg -loglevel error -y -i "$outdir/short.wav" -ar 16000 -ac 1 -c:a pcm_s16le "$outdir/short-16k.wav"
ffmpeg -loglevel error -y -i "$outdir/long.wav" -af 'apad=pad_dur=20' -ar 48000 -ac 1 -c:a pcm_s16le "$outdir/browser-long.wav"
ffmpeg -loglevel error -y -i "$outdir/short.wav" -af 'apad=pad_dur=20' -ar 48000 -ac 1 -c:a pcm_s16le "$outdir/browser.wav"

echo "Synthetic test audio written under $outdir (gitignored artifacts)."
