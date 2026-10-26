# Installation and deployment

## Environments and ownership

Use Linux x86_64 with uv and Git. `scripts/setup.sh` creates only `.venv-tools`
(Python 3.11); flags opt into `.venv-modular` (3.11) and `.venv-moshi` (3.12).
Each environment is installed from an exact package-version lock. These are
version locks, not wheel-hash locks; indexes and compatible wheels must remain
available. No installer imports packages from an existing external virtualenv.
Tools uses aiohttp/websockets/sphn and Playwright without Torch.

`setup_upstreams.sh` freezes Hugging Face speech-to-speech at
`81b688b452ee6b64ff5745b91985e9eb653fcc9f`. Optional NVIDIA source is pinned
separately. Dirty checkouts are rejected; use a project-owned `third_party` tree.
Do not point installation or preparation scripts at shared or running resources.

Modular uses Torch 2.11.0+cu130 and torchaudio 2.11.0+cu130; its Qwen GGML binary
also needs the pinned CUDA 12 runtime/cuBLAS/NVRTC packages. The launcher scopes
these native libraries to modular only. Moshi uses moshi 0.2.13 and Torch
2.7.1+cu128. Their Python/CUDA environments cannot be merged safely. An NVIDIA
driver supporting CUDA 13.0 is needed for modular (Linux R580 or later; verify
against the [NVIDIA compatibility documentation](https://docs.nvidia.com/deploy/cuda-compatibility/)).
Moshi requires a CUDA 12.8 compatible driver; the modular requirement is stricter.
No system CUDA toolkit is required by the pinned wheels, but a working NVIDIA
driver is. CPU-only mock mode needs none of these GPU packages.

48 GB VRAM per service is a conservative deployment starting point, not a minimum
memory guarantee or a matched benchmark. Measure actual device memory, driver,
startup/warmup peaks, conversation growth, host RAM and CPU limits. The BF16
GGUF and FP16 LLM defaults must not be silently quantized or changed to fit.
Separate GPU services are required for persistent warm switching; a CPU UI/proxy
can run anywhere able to reach both. Always record device provenance when comparing.

## Models and environment configuration

Run the getting-started guide's explicit model preparation step only after reviewing model
licenses. `config/models.json` pins source commits, runtime files, sizes and
hashes. HF snapshots use exact revisions; project-owned offline `refs/main`
aliases are needed because some upstream loaders do not accept revision options.
Silero's pinned checkout is staged under Torch Hub's expected directory name;
NLTK punkt_tab and averaged_perceptron_tagger_eng come from pinned, checksummed archives. Launchers run offline.

`--verify-only --checksum` reads existing models without changing caches. Normal
preparation refuses nonempty unmarked caches. Caches with the ownership marker
are treated as project-owned. Never add that marker to someone else's cache.
For local read-only reuse, stage a **new** private snapshot tree and symlink
verified immutable model files; keep aliases, compiler state and lock files in
the new tree. Do not run download tools against shared caches.

Copy `.env.example` to `.env`; shell launchers source it. Use absolute paths for
external cache/interpreter overrides and keep backend health URLs reachable
from the UI process. `VOICE_DEMO_SLOT_DIRECTORY` must be the same absolute path
for UI/operator tooling and supervisor if replacement control is enabled.
Use unique ports and runtime directories for independent deployments.

| Service | Default bind / port | Browser-facing route |
| --- | --- | --- |
| CPU UI/proxy | 127.0.0.1:7860 | HTTP and same-origin WebSockets |
| Modular | 0.0.0.0:8765 | `/backend/modular` → `/v1/realtime` |
| Native Moshi | 127.0.0.1:8998 | Internal `/api/chat` only |
| Moshi adapter | 127.0.0.1:9005 | `/backend/moshi` → `/v1/realtime` |
| Optional VoiceChat | configured port, normally 9000 | `/backend/nemotron` → `/v1/realtime` |

For separate machines set `VOICE_DEMO_MOSHI_ADAPTER_HOST=0.0.0.0`, then restrict
network access. Set the UI's `VOICE_DEMO_MODULAR_URL` and `VOICE_DEMO_MOSHI_URL`
to the respective adapter hosts. Never use a wildcard bind address as a client
URL. Missing routes remain unavailable rather than falling back to synthetic.

## Slurm

Follow the cluster's live capacity, account-wide QoS, locking and preemption
policy **before every submission**. The generic helper does not implement a
site's automatic placement policy. It takes explicit choices, creates logs,
records a submission intent and receipt, and never cancels or modifies a job.
Use a shared operator lock spanning fresh capacity checks through durable receipt;
if the caller already holds it, do not reacquire it through the helper.

```bash
bash scripts/submit_slurm.sh --service modular   --partition PARTITION --qos QOS --gres gpu:TYPE:1   --time 02:00:00 --cpus 16 --mem 64G
bash scripts/submit_slurm.sh --service end-to-end   --partition PARTITION --qos QOS --gres gpu:TYPE:1   --time 02:00:00 --cpus 12 --mem 64G
bash scripts/submit_slurm.sh --service ui   --partition PARTITION --qos QOS --time 02:00:00
```

Choose realistic measured walltimes with headroom. GPU templates require exactly
one typed GPU supplied by the operator; UI requests no GPU. Templates can also
be used with `sbatch --chdir=/ABSOLUTE/REPO --output=... --error=...` after creating
log directories and adding partition/QoS/GRES options. No node is pinned.
Scripts use the actual job working directory unless `VOICE_DEMO_ROOT` is set.

Logs and immutable local receipts are in ignored `logs/` and `artifacts/slurm/`.
If submission output is lost, reconcile the intent's unique `speech-demo:`
comment against squeue/sacct before retrying. A submission receipt is not proof
of running or completed inference. Inspect initial queue state, then service
health, final sacct exit code and actual outputs.

Preemptible services have no training state; restart rebuilds their own warm
processes, loses the active dialogue and requires browser reconnect. Treat
preemption as interruption, not completion. Keep runtime state on durable storage,
never start duplicate writers in one slot, and preserve logs. Slurm/site policy
controls requeue eligibility; these templates do not promise transparent session
resumption or automatically promote/rebalance jobs.

## Remote browser

Set `VOICE_DEMO_UI_HOST=0.0.0.0` only on a private reachable interface, or colocate
UI with the SSH endpoint and keep loopback. Forward only the UI port, for example with
`ssh -N -L 7860:UI_NODE:7860 USER@LOGIN_HOST`. Open localhost in the workstation browser; it supplies the real
microphone/speaker. Camera permission is optional. SSH/HTTPS supplies transport
security; these demo services have no public multi-user authentication.

## Browser tests

`setup_browser.sh` downloads Chromium pinned by Playwright into project-local
`models/browsers`. It does not install system packages. Linux host libraries
include NSS, NSPR, ATK, AT-SPI, CUPS, DRM, xkbcommon, Xcomposite, Xdamage, Xfixes,
Xrandr, GBM, ALSA, Pango, Cairo and GTK; install the matching distro packages
through your administrator or use a compatible container. On Ubuntu the usual
packages include libnss3, libnspr4, libatk1.0-0, libatk-bridge2.0-0, libcups2,
libdrm2, libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3, libxrandr2,
libgbm1, libasound2, libpango-1.0-0, libcairo2 and libgtk-3-0 (names vary).
`VOICE_DEMO_BROWSER_LD_LIBRARY_PATH` optionally points to an operator-managed
local library tree, scoped to browser tests. Do not install packages or change
LD_LIBRARY_PATH in shared running environments.

## Optional NVIDIA VoiceChat

The Modular/Moshi memory guidance does not size this optional container. Verify
its separate official GPU, driver and runtime requirements before allocating.

See [official runtime notes](../services/nemotron/README.md). Keep model files
and the official image outside Git. No optional model is downloaded or loaded by
default. Licensing/runtime availability and a new real inference test are
prerequisites before advertising this alternative as ready.

## Moshi HTTP compatibility patch

The upstream moshi 0.2.13 package requires aiohttp <3.12, which prevents installing
the audited fixes. `scripts/build_moshi.py` verifies the exact upstream source
archive SHA256, preserves its licenses and inference implementation, and builds
`0.2.13+ifn.1` with only the aiohttp bound raised to >=3.14.5,<4, a local version
identifier and pinned build tooling. Setup installs that wheel alongside locked
aiohttp 3.14.5. This is a documented downstream packaging patch, not an official
Kyutai release. The generated wheel and provenance remain outside Git. Compatibility
is subject to the real inference results in docs/validation.md.
