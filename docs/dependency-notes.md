# Dependency lock maintenance

The three requirements-*.lock files pin separate Linux x86_64 environments.
Install using the matching setup script and Python minor version; they are not
interchangeable. They contain exact versions, not wheel hashes. Revalidate
availability, dependency consistency, licenses, vulnerability advisories and
real inference after updates. The editable modular upstream is installed with
`--no-deps` at the commit in config/models.json after its locked dependencies.

CUDA wheel indexes are official PyTorch cu130 (modular) and cu128 (Moshi).
CUDA 12 native libraries in modular support its GGML binary alongside Torch's
CUDA 13 libraries. Do not add a personal environment through .pth or PYTHONPATH.
Runtime launchers use project-owned caches and offline pinned model aliases.
Playwright's browser binary and Linux host libraries are separate prerequisites.
Optional NVIDIA container/model preparation is separate and requires official
runtime compatibility and license/access review.

## Moshi HTTP compatibility patch

The upstream moshi 0.2.13 package requires aiohttp <3.12, which prevents installing
the audited fixes. `scripts/build_moshi.py` verifies the exact upstream source
archive SHA256, preserves its licenses and inference implementation, and builds
`0.2.13+ifn.1` with only the aiohttp bound raised to >=3.14.5,<4, a local version
identifier and pinned build tooling. Setup installs that wheel alongside locked
aiohttp 3.14.5. This is a documented downstream packaging patch, not an official
Kyutai release. The generated wheel and provenance remain outside Git. Compatibility
is subject to the real inference results in docs/validation.md.

## Remaining modular advisories

The audit reports PYSEC-2026-3804 (Accelerate checkpoint-index path traversal),
PYSEC-2026-3740 (NLTK caller-supplied model path sandbox bypass), and
PYSEC-2026-3447 (setuptools source distribution file exclusion on macOS;
that platform-specific scenario is outside this Linux deployment). The first two have no published fix in the audit
feed. Torch 2.11 requires setuptools <82, preventing the reported >=83 fix
without a separately validated Torch/dependency change. This release keeps the
working dependency contract and reports these findings, rather than claiming
a clean modular vulnerability scan. Only pinned, checksum-verified model files
and trusted installation inputs are supported; model-path selection is not a
browser feature. Keep services private. These constraints limit exposure and
do not constitute fixes. Review current advisories before a broader deployment.
