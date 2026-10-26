# Asset, privacy and release checklist

Status at Phase 1: plans and specifications exist. No real screen/audio takes,
public voice permission records or finished trailer/walkthrough have been collected.
The existing animated README preview is synthetic and remains labeled accordingly.

| Asset | Current status | Required before public video use |
| --- | --- | --- |
| Project cover and diagram artwork | Original project sources available | Retain authorship; check final pixels and readable contrast |
| TU Braunschweig seal and IfN logo | Original supplied files restored for the maintainer-requested private repository | Separate public-use clearance, correct context, aspect ratio and IfN white backing; no implied broad trademark license |
| Human demonstration voice | NOT RECORDED | Consent for recording, editing, public distribution and chosen platforms; store consent privately |
| Moshi/model-generated speech | NOT RECORDED for this production | Preserve exact configured model provenance and applicable model/output terms; no imitation of a real person or voice substitution |
| Optional narration voice | NOT RECORDED | Human consent or explicit synthetic-voice commercial/publication permissions; label synthetic narration where appropriate; never impersonate model output |
| Music/sound effects | None selected | Prefer no music. Otherwise verify synchronization/distribution/platform license; keep proof privately and credits publicly where required |
| Fonts | System fonts currently used in preview artwork | Pin a redistributable font/license in the video renderer, or document local use; do not assume installed fonts can be vendored |
| Real Moshi, modular, switching and Details takes | MISSING | Real inference, safe screen/audio, uncut evidence windows and reviewed claims |
| Captions and subtitle files | Planned only | Transcribe actual audio, review names, speaker attribution and privacy; no anticipated model replies |
| Upstream references | Repository notices present | Include Moshi/Mimi, Hugging Face Speech-to-Speech and configured model teams in description/credits; retain code and model license separation |

## Per-take private record

Use external VIDEO_ASSET_ROOT/private, not this repository, for recording date,
consenting speaker identity, source file and SHA256, actual model revisions,
precision/settings, verified GPU/driver, browser/OBS configuration, track/stream
mapping, sync marker, take outcomes and edit decisions. Use a public-safe take alias
in editing specs. Consent documents, internal endpoints, event logs and full device
metadata do not belong in the public export manifest.

## Recording and editorial integrity

- [ ] Every model interaction is a real, synchronized screen/audio take.
- [ ] Generated diagrams/cards are distinguishable from recorded activity.
- [ ] Placeholder/simulation footage cannot pass the release-render gate.
- [ ] Barge-in outcome is reviewed, with both voices audible and no button substitution.
- [ ] No audio replacement, speed change, shortened response gap or hidden cut inside evidence.
- [ ] Subtitles quote actual audio; any clarification is labeled editorial text.
- [ ] Warm switching is supported by private residency evidence; new session/context loss is explained.
- [ ] Unsupported Moshi metrics remain unavailable; no invented result or latency ranking.
- [ ] Source take length permits a complete exchange; revise the timeline instead of accelerating it.

## Privacy and packaging

- [ ] Raw recordings, private bindings, consents and operational evidence are outside Git.
- [ ] Reviewed crops contain no internal URL/IP, credentials, job IDs, usernames, notifications or private speech.
- [ ] Camera stays off; no unconsenting bystander appears or speaks.
- [ ] Captions, thumbnails, metadata, frame edges and all audio tracks are inspected.
- [ ] Export includes only intended public mix/subtitle tracks; source/unused private tracks are absent.
- [ ] Sanitize container metadata and filenames; inspect the result with ffprobe.
- [ ] Preserve raw originals privately; metadata cleaning never destroys the audit original.
- [ ] Code notices and model terms remain intact; logos and other assets have separate permission records.
- [ ] Git tree/history contain no raw media, weights, environments, consent records or internal history.
- [ ] Public upload and repository visibility are explicit maintainer actions. This publication remains private.

## Phase 1 acceptance record

PASS: current code/configuration audit and claim gates; 90-second trailer and
four-minute walkthrough specifications; recording/audio-track design; placeholder
and release-mode contracts; no production pipeline changes for recording.

NOT RUN: actual OBS capture, model inference, natural barge-in verification,
latency study, renderer execution, placeholder film export, final video rights
clearance and public video upload. These are subsequent phases, not failures
hidden behind an animation or synthetic test.
