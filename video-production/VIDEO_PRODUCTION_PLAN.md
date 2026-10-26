# Video production plan — Phase 1

Status: audit and design, 26 October 2026. No real dialogue was recorded and no
production inference service was changed for this work. The current README GIF
is a labeled synthetic interface preview, not footage for a real-inference claim.

Deliver two edits from the same approved takes: a 60–90 second release trailer
(the storyboard targets exactly 90 seconds) and a 3–5 minute technical walkthrough
(the initial timeline targets four minutes). Use real screen and synchronized
audio for every model interaction. Generate only explanatory material around it.

## Repository audit

Audited the publication source exported from release commit
`709bc66c05c4ed51f7cc81ebc62d4c29c9a104ff`, especially
`frontend/index.html`, `frontend/app.js`, `frontend/backends.js`,
`frontend/realtime-protocol.js`, `services/moshi/adapter.py`,
`scripts/run_modular.sh`, `scripts/backend_entry.py`, and `config/models.json`.
Also inspected the existing local Hugging Face upstream at its pinned commit
`81b688b452ee6b64ff5745b91985e9eb653fcc9f`, including
`src/speech_to_speech/api/openai_realtime/websocket_router.py` and
`handlers/audio.py`. Findings below come from implementation and pinned metadata,
not obsolete experiment reports. No live residency or hardware state was queried;
configured defaults must be matched against the deployment at recording time.

| Component | Configured implementation | Honest size label |
| --- | --- | --- |
| Full-duplex | `kyutai/moshiko-pytorch-bf16` with Mimi and SentencePiece | Moshi 7B family; 7,687,729,152 checkpoint tensor entries, not a fresh trainable-parameter measurement |
| VAD | Silero VAD 6.2.3 | No verified parameter count asserted |
| Turn detection | Smart Turn v3.2 CPU ONNX from `pipecat-ai/smart-turn-v3` | Approximately 8M refers to Smart Turn, not Silero |
| ASR/STT | `nvidia/parakeet-tdt-0.6b-v3`, nano-parakeet runtime | 0.6B family; 627,057,286 tensor entries |
| LLM | `Qwen/Qwen3-4B-Instruct-2507`, Transformers FP16 | 4B family; 4,022,468,096 tensor entries |
| TTS | Qwen3-TTS-12Hz-1.7B-CustomVoice; pinned Serveurperso GGUF talker/tokenizer, BF16 | 1.7B family; full upstream checkpoint has 1,916,676,352 entries including additional components |

Exact immutable revisions and hashes remain in [the model manifest](../config/models.json).
Do not sum the rounded labels into a total or advertise every checkpoint entry
as a unique trainable parameter. Recheck environment overrides and verified local
files before naming a model in the final film; do not download weights for this audit.
Nemotron VoiceChat is optional, not the primary demonstration or a claimed resident.

| Claim | Implementation evidence | Recording/publication gate |
| --- | --- | --- |
| Streaming microphone and playback | Browser worklets, 24 kHz PCM transport; Moshi adapter uses persistent Opus state | Capture real input and output together; fake-mic checks are not inference evidence |
| Shared landscape UI, history, diagrams, Details, TV mode | Existing frontend presentation and controls | Show both modes; camera off; preserve internal transcript scrolling |
| Warm architecture switching | `chooseBackend` disconnects, clears view and connects to an existing endpoint; no model-replacement call | Show switch plus new-session behavior; privately verify both backends resident before and after |
| Modular speech interruption | Session requests `interrupt_response: true`; pinned upstream cancels active responses on eligible speech start; frontend clears queued playback | Real overlapping speech take required; button cancellation and natural barge-in are different demonstrations |
| Moshi full-duplex and barge-in | Continuous input/output; adapter sends no VAD boundaries and implements no `response.cancel` | Record natural overlap and the model's actual subsequent behavior; natural interruption quality is not established by code inspection |
| Clear local playback | Moshi control clears browser audio; it does not send inference cancellation | Never describe the button as stopping the model or proof of semantic interruption |
| Capability-aware measurements | Moshi lacks user transcript, turn completion, speech boundaries and stage times; UI uses N/A | Explain that Demo time is cumulative microphone time, not latency; no cross-mode latency ranking |
| Reset and reconnect | Reset clears view/local audio/timer; reconnect opens a fresh session | Reset does not promise erased server context; show the distinction in walkthrough |
| Camera | Explicit local preview, no audiovisual inference path | Keep off for filming; do not claim audiovisual understanding |
| Deployment readiness and response quality | Status polling exists; source validation is historical | Verify the actual recorded deployment and retain failed takes privately; no current GPU-quality or performance PASS claimed here |

## Visual and editorial direction

Retain the dark slate, teal and warm-orange cover style already selected. Use the
original TU Braunschweig and IfN marks without redrawing, distortion or recoloring;
keep the IfN white backing. Code Apache-2.0 does not grant rights to these marks.
They are authorized for inclusion in this private repository by the maintainer;
public video/logo redistribution clearance remains a separate recorded gate.
Use original vector diagrams, restrained highlights and a legible sans-serif font
with a recorded license. Prefer a music-free first edit. Never place a voice-over
on top of a response needed to assess turn taking. Closing credit: shared interface
and integration by this project; models by the credited upstream teams.

## FFmpeg and Remotion evaluation

| Option | Fit | Dependencies and terms | Recommendation |
| --- | --- | --- | --- |
| FFmpeg + generated SVG/HTML | Reliable trimming, audio-track mapping, captions, compositing and encoding; simple architecture animation | Base is LGPL-2.1-or-later; enabled components can make a build GPL. `libx264` commonly requires GPL-enabled FFmpeg. Nonfree builds are not redistributable. Record exact version/configuration and do not vendor binaries | Default local renderer in Phase 2; invoke as a subprocess with explicit arguments |
| Remotion | React compositions, frame-exact SVG motion, reusable titles, overlays and preview player | Custom Remotion license, not Apache/MIT. Current free eligibility includes nonprofits and individuals; other organizations may need a Company License. Version 5 changes licensing/telemetry. Verify the selected version and legal entity, rather than assuming all institutional use is free | Optional graphics renderer only after version/license review; isolated Node package/lockfile, no runtime dependency |

This is a tooling assessment, not legal clearance. Encoder software and codec
patent/distribution obligations need separate review if shipping a renderer.
Rendering with an external GPL tool does not itself change this project's source
license; do not redistribute its binaries under the project's Apache label.
Official references checked for this plan: [FFmpeg licensing](https://ffmpeg.org/doxygen/trunk/md_LICENSE.html),
[Remotion license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md),
[Remotion licensing/telemetry](https://www.remotion.dev/docs/licensing).
Recheck terms when pinning the implementation. No Remotion package is installed now.

## Isolated automation design

Version only scripts, design sources, schemas, approved subtitle text and rights
summaries inside this directory. Keep all original recordings in an external
`VIDEO_ASSET_ROOT`. The proposed layout is:

```text
video-production/
  VIDEO_PRODUCTION_PLAN.md   STORYBOARD.md
  RECORDING_GUIDE.md         ASSET_CHECKLIST.md
  timeline.json             assets.example.json
  schema/                   # Phase 2: timeline and asset schemas
  tools/                    # Phase 2: validate, probe, render, quality checks
  graphics/                 # Phase 2: SVG/HTML titles and architecture sources
  captions/                 # Phase 3: reviewed public-safe VTT/SRT
  remotion/                 # Optional later; independent package and lockfile
  cache/ rendered/ exports/  # Ignored; build products only
external VIDEO_ASSET_ROOT/
  raw/ normalized/ private/  # Never placed in this Git repository
```

`timeline.json` is the Phase 1 machine-readable editing contract, using integer
frames at 30 fps. Each shot identifies generated graphics versus real dialogue,
its source in-frame, duration, caption/overlay and evidence claim. Private asset
bindings give file hashes, stream indexes, recording provenance, permissions and
in/out points. Bindings are excluded from Git; `assets.example.json` contains no
recordings or private metadata. Real-shot speed is always 1.0.

Phase 2 entry points (proposed, not implemented commands): validate, render
`--mode placeholder`, and render `--mode release`. Placeholder mode uses obvious
slates labeled PLACEHOLDER — NO MODEL INFERENCE with silence or a slate tone;
it must not impersonate dialogue. It works with no raw recordings and exercises
all durations/transitions. Release mode fails closed on a missing/unapproved
recording, unresolved barge-in claim, missing consent, checksum mismatch, private
metadata or a placeholder. Existing synthetic README previews cannot bind a real slot.

Build process: validate timeline and bindings → probe media → normalize resolution
and sample rate while preserving real-time duration → render generated cards and
annotations → trim complete real exchanges → compose/caption → audio mix → export
MP4 and sidecar VTT → run publication checks. Cache each segment by input hash,
selected streams, in/out frames, graphics source, tool version and render settings.
Replace a clip by changing its private binding; only dependent segments rebuild.
Store private provenance outside Git, and a sanitized export manifest with the
final film. No processing imports or patches the dialogue server.

Generated cuts use cut/fade transitions within their allocated frame windows;
durations never silently overlap. Default to hard cuts around real interaction
segments. No internal cuts, speed changes, shortened thinking gaps or displaced
audio inside timing/interrupt evidence. Opening/closing silences may be trimmed
outside evidence windows with the edit decision recorded. Independently captured
voice-over must be labeled narration, never substituted as model output.

Exports: 1920×1080, 30 fps, H.264/yuv420p MP4 with faststart and one AAC stereo mix,
48 kHz audio; archive an editing master and separate lossless source audio privately.
Optional web derivative and silent short GIF are presentation exports, labeled
accordingly. Keep captions as VTT/SRT plus an optional burned-in variant; subtitles
quote recorded speech after manual review, not anticipated answers from the scripts.

## Concrete implementation phases and acceptance

1. **Phase 1 — this delivery:** repository audit; 90-second storyboard and four-minute
   walkthrough outline; English human prompts; OBS guide; rights/asset checklist;
   timeline and asset-binding examples. Timeline arithmetic and references checked.
   Real recording, renderer and final video are NOT RUN/not built.
2. **Phase 2 — separate renderer:** pin available FFmpeg build and fonts; implement
   schemas, safe asset resolution, hash/probe checks and cached rendering; render
   every shot with placeholders on CPU. Accept only an exact-duration, synchronized,
   visibly watermarked export and a release build that rejects placeholder inputs.
   Add Remotion only if the graphics benefit and reviewed license justify it.
3. **Phase 3 — recording:** obtain speaker/asset permissions; verify actual resident
   models and settings; record uninterrupted takes with original separated audio;
   record both successful and failed barge-in attempts; review privacy; bind approved
   takes and write subtitles. Make no new deployment changes merely for the film.
4. **Phase 4 — real assembly and verification:** render trailer and walkthrough from
   the same verified sources. Check AV sync at the start/end, dropped frames,
   speaker attribution, N/A metrics and every performance/interruption statement.
   Reject evidence clips that exceed a slot; choose a complete shorter take or revise
   the timeline openly. Do not speed speech up to fit a storyboard.
5. **Phase 5 — publication:** confirm public-use rights, review pixels/audio/subtitles
   and metadata, scan final files/history, approve platform upload separately, and
   publish the reviewed export with source/code credits and limitations. The present
   GitHub push remains private; no workflow changes visibility or uploads raw media.
