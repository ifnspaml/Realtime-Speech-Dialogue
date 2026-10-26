# Validation and limitations

This publication preserves the reviewed runtime configuration and changes its
public-facing content, branding, privacy checks and release metadata. Its source
identifiers are recorded in [Provenance](../PROVENANCE.md).

## What the preview establishes

The README animation/static image is a CPU-only simulation of the actual
frontend and transports. Text and tones are synthetic; the camera is off.
No screenshot, badge or simulated timing is a model inference result or a
latency/quality benchmark. Preview assets are reviewed for private information.

The publication preparation checks documentation links, original artwork,
branding/resource references, secret/artifact patterns, author metadata and the
resulting Git history. The manual CPU-check workflow retains the unit, protocol,
integration and synthetic browser checks for future runtime changes. It is not
automatically dispatched by a documentation push.

## Existing inference validation

The reviewed source release previously exercised real Modular and Moshi
speech-to-speech, streaming browser playback, readiness and architecture
switching on isolated NVIDIA resources. That historical validation does not
constitute a new test of every host/GPU configuration in this publication.
No GPU inference, training, backend rebuild or model download is required for
the public-facing content changes. Original operational logs and recordings
are not included here.

## Remaining limitations

- Moshi emits assistant text/audio but not the modular user transcripts, speech
  boundaries, stage times or per-turn completion. Those fields remain N/A.
- Current backends support one active dialogue session each. Switching opens a
  fresh session on warm weights. Reset clears presentation; Reconnect starts a
  fresh model session.
- Queues and watchdogs are bounded. Stalls and streaming underruns can occur;
  this demo does not claim glitch-free audio or validated subjective quality.
- Physical microphone/speaker acoustics and comparative model accuracy are not
  established by a fake-microphone browser check.
- Optional Nemotron VoiceChat retains its official preparation/runtime path,
  but is separately prepared, not default-loaded and not newly validated here.
- The pinned modular dependencies have known advisories. See
  [dependency notes](dependency-notes.md). The manual CPU workflow is not a
  blanket security certification.
- Package version locks do not include wheel hashes. Index availability,
  supported drivers and model licensing/access remain deployment prerequisites.
- Services provide no public multi-user authentication. Keep backend and
  operator routes on trusted networks or behind appropriate access controls.

See [Troubleshooting](troubleshooting.md) for synthetic and authorized live
checks. Model files remain outside Git and are pinned/checksummed explicitly.

## Current content update

The original supplied TU Braunschweig and IfN marks were restored in the private
publication UI and cover. Their separate rights and future public-use clearance
are recorded in assets/branding/README.md; the code license does not relicense them.
Targeted branding checks (3) and privacy unit checks (5) passed. The refreshed
24-frame browser preview passed with camera off, synthetic measurement labels,
no JavaScript errors and no model-replacement requests. Documentation links, SVG
syntax, the 90-second/240-second timeline arithmetic and ignored private recording
paths were checked. No broad backend rebuild or fresh GPU validation was run.

The separate video-production directory contains a Phase 1 audit and proposal,
not a finished renderer or real demonstration film. Real OBS takes, natural
barge-in outcomes, placeholder/release rendering and public asset/voice clearance
remain NOT RUN or pending. See [Video production](../video-production/VIDEO_PRODUCTION_PLAN.md).
