# Recording guide — Windows / OBS

This guide prepares recording without changing the dialogue pipeline. Record
actual model interaction only against an authorized, available demo. Phase 1 does
not start services, allocate a GPU, change model settings or record a real speaker.

## OBS setup

Use a maintained official OBS Studio build on Windows 11 (or a supported Windows
10 setup), with a dedicated profile and scene collection. Record the exact OBS,
browser, Windows, GPU driver and encoder versions privately for reproducibility.

| Setting | Starting configuration | Verification |
| --- | --- | --- |
| Canvas and output | 1920×1080, 30 fps, no rescale; browser 100% zoom | Text is legible; both landscape columns and controls visible |
| Video encoder | Hardware H.264 if available; quality mode around CQP 18–22 as a starting point | Short calibration has no OBS rendering/encoding lag; adjust quality to the actual encoder |
| Recording container | MKV for recoverability; remux a copy to MP4 if needed | Keep original MKV and separated audio privately |
| Audio | 48 kHz; speech sources 192–320 kb/s AAC where available | Both sources audible, no clipping or duplicated audio |
| Browser video | Window Capture of a dedicated browser window; use full-screen presentation to omit address bar | No URL, notifications, private tabs, bookmarks, password prompts or taskbar |
| Microphone | Explicit Audio Input Capture for a headset/external mic | Same physical mic as demo; allow browser/OBS access; no exclusive-device lock |
| Model audio | One Application Audio Capture source targeting the dedicated demo browser | Includes model voice, excludes unrelated apps and OBS monitoring |
| Desktop audio | Disable when using per-app capture | No second copy/echo of browser output |
| Monitoring | Off by default; headphones for the demonstrator | Model voice cannot feed back acoustically into the mic |

OBS supports per-application capture on suitable Windows versions and can include
application audio in Window Capture on newer builds. Choose one audio capture
path, not both. See the official [Application Audio Capture guide](https://obsproject.com/kb/application-audio-capture-guide).
Test the actual browser; if app capture fails, use an isolated desktop-audio device
as a documented fallback, with other apps muted. Do not install virtual audio
routing or alter the server merely for this recording.

In Advanced Audio Properties, route sources as follows:

| OBS track | Contents | Purpose |
| --- | --- | --- |
| 1 | Microphone + model/browser output | Ready-to-watch reference mix |
| 2 | Microphone only | Human speech, interruption onset |
| 3 | Model/browser output only | Response audio and overlap assessment |
| 4, optional | Narration only, preferably recorded in a separate session | Explanations between real exchanges |

Enable these tracks in Output → Recording. Most players select one track, so
check each in an editor/probe, not just the default playback. See the official
[Multiple Audio Track guide](https://obsproject.com/kb/multiple-audio-track-recording-guide).
OBS track numbers are not assumed to equal FFmpeg stream indexes; inspect the
actual file and record selected indexes in the private asset binding.

Set microphone gain so normal peaks are approximately −12 to −6 dBFS and never
clip. Match model output audibility without changing its timing. Avoid a noise
gate that clips initial consonants; avoid compression/denoising that masks overlap.
Record a 15-second calibration, inspect sync and both isolated tracks, and check
OBS dropped-frame statistics. Choose headphones and a quiet room; no music during
response, barge-in or timing evidence.

## Recording session checklist

1. Obtain the human speaker's consent and confirm public use of each planned
   voice, logo and asset. Use fictional nonsensitive prompts, not personal data.
2. Use a clean browser profile. Disable notifications, camera, password autofill,
   unrelated tabs/extensions and private desktop overlays. Keep operator controls
   disabled. Frame the demo only; no login, cluster monitor or internal URL.
3. Privately verify backend readiness, resident model identifiers/revisions,
   precision and any launch overrides. Confirm both services warm and no other
   active session. Do not infer residency from a selectable model name alone.
4. Confirm model audio comes from real inference: no Run simulated turn, replay
   fixture, fake mic or synthetic badge. Camera remains off. Do not use the README
   mock preview as recording evidence.
5. Start OBS, speak a take ID before the selected clip, and perform a simple
   synchronization marker if useful. Allow a few seconds before and after every
   exchange. Keep originals intact, including failures and stalls.
6. Record scripts A–D from STORYBOARD.md. Film each natural barge-in uncut. Record
   separate ordinary interruption-button behavior only if labeled explicitly.
7. Film Details while explaining unavailable Moshi fields and the meaning of
   browser receipt, audio delivery and rendered playback times. No made-up values.
8. Stop, verify source tracks and duration, compute a SHA256, and store originals
   under external VIDEO_ASSET_ROOT. Record take/model/session settings privately.
9. Review pixels and speech for sensitive content. Export only approved crops,
   captions and selected media. Do not upload originals or an unreviewed rough cut.

## Optional event timestamps and latency verification

No pipeline instrumentation is required for the trailer. Use OBS's single media
timeline and isolated audio first: manually mark the end of human speech and the
first audible model response. Retain the exact uncut evidence interval. This
measures recorded conversational response delay, not GPU inference time. Threshold,
room noise, endpointing, browser/OBS buffering and frame granularity affect it.

For optional deeper analysis, collect only already exposed, consented browser
events in an external sidecar: take ID, event type, session/response alias,
monotonic browser timestamp and recording-time alignment marker. Candidate events
are modular speech_started/speech_stopped, first audio received and first rendered
playback; confirm each event actually exists and retain its definition. The existing
`getDiagnostics()` ES-module export in `frontend/app.js` can provide a read-only snapshot, but does not establish a
persisted event log or a shared server/browser clock. Do not enable a private
operator API, inject patches or record message payloads for this purpose.

Moshi supplies no speech boundaries or per-turn completion: leave those values
unavailable. An audio waveform annotation may show human overlap; it must be
labeled editorial analysis rather than a model-produced event. Server timings
cannot be subtracted from browser times without clock alignment; browser receipt
time is not acoustic output time. A single OBS capture reduces cross-device clock
mismatch, but does not remove device buffering or drift. Verify start/end sync.

If reporting a number later, define endpoints, sample count, selection, hardware,
models/precision, browser, transport, errors and uncertainty. Keep values absent
from the initial trailer unless this validation is complete. One attractive take
is a demonstration, not a latency benchmark. Never cut silence, shift one audio
track, time-stretch or speed the picture to imply faster responses.
