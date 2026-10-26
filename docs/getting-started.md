# Run the real speech backends

The README's quick start prepares only the CPU UI/tools environment. Real
inference is separate and requires compatible NVIDIA resources. Review the
model licenses and deployment requirements before model preparation.

## Install separate environments and pinned models

From the repository root:

```bash
bash scripts/setup.sh --modular --moshi
bash scripts/prepare_models.sh --backend all
bash scripts/prepare_test_audio.sh
bash scripts/prepare_models.sh --backend all --verify-only --checksum
```

Setup creates independent Python environments. The explicit model-preparation
step downloads pinned runtime artifacts into new project-owned caches. It
refuses to adopt nonempty unmarked caches. No weights are versioned in Git.
`.env.example` documents cache paths, interpreters, addresses and ports.

## Start warm inference services

Start these separately on allocated GPU resources, from the repository root:

```bash
bash scripts/run_modular.sh
```

```bash
bash scripts/run_end_to_end.sh
```

The second launcher starts the default Moshi supervisor, official native server
and CPU PCM/Opus adapter. A generated WAV transport check runs before READY;
it checks streamed text/nonzero audio, not semantic answer quality. Both model
services stay warm while the browser switches sessions.

## Connect the CPU UI

In a CPU shell, configure reachable backend addresses and start the UI:

```bash
export VOICE_DEMO_MODULAR_URL=ws://MODULAR_HOST:8765/v1/realtime
export VOICE_DEMO_MOSHI_URL=ws://MOSHI_HOST:9005/v1/realtime
bash scripts/run_demo.sh
```

Replace the host placeholders. If services are on different machines, set the
Moshi adapter's listen host explicitly and restrict access to a trusted network.
Native Moshi can stay on loopback. Use the generic Slurm and SSH examples in
[Deployment](deployment.md) for a cluster. Local browser microphone access needs
localhost or HTTPS. These services do not implement public multi-user auth.

Use the architecture selector to open a session on either warm backend. Reset
clears presentation and local audio. Reconnect in Details starts a fresh model
session. Optional camera preview stays in the browser and is not inference input.
Moshi does not provide all the modular backend's user transcript or event metrics.

[Models](models.md) lists exact revisions/hashes and rounded size labels.
[Troubleshooting](troubleshooting.md) covers readiness, audio and live checks.
Optional NVIDIA VoiceChat uses separate official preparation/runtime requirements;
see services/nemotron/README.md. It is not loaded by default.
