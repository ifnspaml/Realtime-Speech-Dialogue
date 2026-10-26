# Optional official NVIDIA VoiceChat runtime

This alternative is excluded from default model preparation and startup. Moshi
remains the primary resident end-to-end model. Use Nemotron only when the frozen
official runtime remains accessible, licensed and compatible with your driver/GPU.
No fresh Nemotron inference validation is claimed by this release.

`runtime.json` records the source's official OCI digest, model version 1.0.0,
and extracted official client/server hashes. `config/nemotron-files.json` pins
model-file metadata. Review NVIDIA's official model/container terms and obtain
required NGC access before explicit preparation:

```bash
bash scripts/setup.sh --nemotron
bash scripts/prepare_nemotron.sh
# On an independently allocated compatible GPU:
bash scripts/run_nemotron.sh
bash scripts/run_nemotron.sh --health
```

Preparation downloads official artifacts outside Git, verifies model checksums,
and extracts unmodified client sources for attribution verification. It never
runs during UI or Moshi setup. Singularity, Apptainer or Docker must be installed
and configured by the operator; no restricted image/model is vendored.

The official container's own entrypoint provides inference. The frontend adapts
its continuous lifecycle without inventing modular stage metrics. If this is
used in the supervised end-to-end slot, replacement is an explicit operator
operation; architecture switching cannot load it. Missing or nonresident routes
must remain unavailable/unloaded. Do not replace an inaccessible frozen image
with latest and claim the same environment was reproduced.
