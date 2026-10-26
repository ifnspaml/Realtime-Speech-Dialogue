# Models and provenance

`config/models.json` is the machine-readable manifest. It records full immutable
HF revisions and every selected file's byte count plus SHA256 (LFS) or Git blob
SHA1 (small Git objects). The source revision for each model card is pinned too.
No weights are versioned here. `prepare_models.py --backend all --verify-only
--checksum` verifies local runtime files and offline aliases without downloading.

| Role | Repository | Exact revision | License |
| --- | --- | --- | --- |
| Moshi + Mimi + tokenizer | kyutai/moshiko-pytorch-bf16 | `2bfc9ae6e89079a5cc7ed2a68436010d91a3d289` | CC-BY-4.0 |
| STT | nvidia/parakeet-tdt-0.6b-v3 | `541d1f99c6b0c3cd0b11a95167540bb8edefd82b` | CC-BY-4.0 |
| LLM | Qwen/Qwen3-4B-Instruct-2507 | `cdbee75f17c01a7cc42f958dc650907174af0554` | Apache-2.0 |
| TTS family/config | Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice | `0c0e3051f131929182e2c023b9537f8b1c68adfe` | Apache-2.0 |
| Converted TTS BF16 weights | Serveurperso/Qwen3-TTS-GGUF | `b7ee2e8c7459c3bea99da23e3d178125a7d1713c` | Apache-2.0 |
| Endpointing | pipecat-ai/smart-turn-v3 | `f766f81d3cfdf7737ac64aad813d91bbfd56bf93` | BSD-2-Clause |
| VAD source/checkpoint | snakers4/silero-vad | `5cd7945676eb32225748052e2e6a0580e4686a08` (6.2.3) | MIT |

## Size labels

These are rounded upstream family labels, not the sum of all resident stages.
The pinned Hugging Face safetensors metadata records 7,687,729,152 entries for
Moshiko, 627,057,286 for Parakeet, 4,022,468,096 for Qwen3 LLM, and 1,916,676,352
for the full Qwen3-TTS checkpoint. Metadata entries are not a measured trainable
parameter count; tied weights, auxiliary heads and codecs can differ. In
particular Moshi's 7B Temporal Transformer is accompanied by a Depth Transformer
and Mimi. The TTS 1.7B family label does not count every predictor/codec component
as a separate advertised model. GGUF runtime contains talker and tokenizer files.

Approximately 8M refers to [Smart Turn](https://github.com/pipecat-ai/smart-turn)
endpointing, which complements Silero speech activity detection. This release
therefore labels the VAD stage without an unsupported 8M parameter claim.
See [Moshi](https://github.com/kyutai-labs/moshi) and the pinned model cards:
[Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/blob/541d1f99c6b0c3cd0b11a95167540bb8edefd82b/README.md),
[Qwen3](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/cdbee75f17c01a7cc42f958dc650907174af0554/README.md),
[Qwen3-TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/blob/0c0e3051f131929182e2c023b9537f8b1c68adfe/README.md).

## Runtime details

The modular path reads Parakeet's `.nemo` through nano-parakeet, Qwen3 through
Transformers (FP16), and Qwen3-TTS through qwentts GGML (BF16 converted talker
and tokenizer). It does not download the unused original TTS weights. No model
size, quantization or effective precision is silently changed for smaller GPUs.

Moshi uses the upstream Python package pinned in `requirements-moshi.lock`, the
BF16 Moshiko checkpoint, bundled Mimi checkpoint and 32k SentencePiece tokenizer.
There are no local diagnostic patches to its inference loop. The adapter only
translates transport. Moshi cannot produce modular user transcripts or stage
metrics; the UI does not fabricate them.

NLTK punkt_tab and averaged_perceptron_tagger_eng is pinned to nltk_data commit
`550b6625bcef1f2abff2ff770a5a0d272c9c6b2a`; its archive checksum is in the
manifest. Silero runtime files are fetched from the pinned commit and its JIT checksum is
verified. The frozen HF upstream asks Torch Hub for a master-named directory;
preparation fills that **project-owned** directory from the immutable commit.
Runtime is offline and does not fetch the moving branch.

## Optional Nemotron VoiceChat

`services/nemotron/runtime.json` preserves the source's official OCI manifest
digest, model version 1.0.0 and official client checksums. The file list and
checksums are frozen in `config/nemotron-files.json`. No model or image is
vendored. NVIDIA model/container licenses and access requirements are separate
from this repository's code. Reproduction is optional and unvalidated until the
operator can retrieve the frozen official image/model and pass a fresh inference
test; changing to an unpinned latest image is not a reproducibility fix.

## Moshi HTTP compatibility patch

The upstream moshi 0.2.13 package requires aiohttp <3.12, which prevents installing
the audited fixes. `scripts/build_moshi.py` verifies the exact upstream source
archive SHA256, preserves its licenses and inference implementation, and builds
`0.2.13+ifn.1` with only the aiohttp bound raised to >=3.14.5,<4, a local version
identifier and pinned build tooling. Setup installs that wheel alongside locked
aiohttp 3.14.5. This is a documented downstream packaging patch, not an official
Kyutai release. The generated wheel and provenance remain outside Git. Compatibility
is subject to the real inference results in docs/validation.md.
