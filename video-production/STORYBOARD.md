# Storyboard and English recording scripts

Target: 90 seconds, 1920×1080, 30 fps. Dark slate/teal/orange visual language,
original institutional logos, camera off. Durations are an edit target, not a
promise about how quickly a model responds. Actual exchanges may require a longer
cut. Never accelerate speech or remove an interaction gap to meet a slot.

## Release trailer — 00:00–01:30

| Time | Picture and source | Sound / text | Evidence gate |
| --- | --- | --- | --- |
| 00:00–00:04 | GENERATED title, selected cover style, original TU Braunschweig and IfN marks | Real-Time Speech Dialogue. Compare modular and full-duplex voice AI in one interface. | Logo public-use rights before public upload |
| 00:04–00:10 | GENERATED split diagram: Moshi + Mimi versus Silero VAD → Smart Turn → ASR → LLM → TTS | Narrator: “Two approaches to voice AI. One shared interface.” | Diagram is explanatory, not recorded model activity |
| 00:10–00:28 | REAL full-duplex screen, mic and model audio, one complete short exchange | Human prompt A below; exact recorded model answer, reviewed captions | Backend is real Moshi; uninterrupted synchronized take; no invented user transcript |
| 00:28–00:41 | REAL natural barge-in with both voices audible at the overlap | Human prompt B; annotate actual overlap only after review | Include only if real take demonstrates it. No playback-clear button masquerading as barge-in |
| 00:41–00:45 | GENERATED modular diagram with independent VAD and turn detection | “Detect. Recognize. Respond. Speak.” | Highlighting explains stages, not stage timings |
| 00:45–01:02 | REAL modular exchange, user and assistant text visible | Human prompt C; exact model output | Real configured models, complete exchange; no replay or synthetic response |
| 01:02–01:12 | REAL switch to the other architecture, show session readiness and a fresh turn if it fits | Human prompt D; overlay “New session · warm backends” | Both backends already resident; do not claim seamless context transfer or zero delay |
| 01:12–01:22 | REAL Details close-up, preserve full timing context | Narrator after dialogue: “Measurements follow backend capabilities. Unsupported fields stay N/A.” | Explain Demo time versus latency; avoid comparative latency numbers |
| 01:22–01:27 | GENERATED end card with project name and repository address | “Try the interface. Explore both architectures. If it helps your work, consider a star.” | Keep private cut private; public upload only after approval |
| 01:27–01:30 | GENERATED credit card, matching cover design | Kyutai Moshi/Mimi · Hugging Face Speech-to-Speech · configured model teams · IfN / TU Braunschweig | Full references and separate licenses in repository/video description |

All REAL slots preserve native chronological audio/video at 1×. GENERATED slots
may animate, but must not create fake conversations, model activity, latency
readouts or a false live view. Actual response captions come from the recording.
If natural barge-in fails, mark that shot unresolved; use a clearly explanatory
capability/limitation card in a revised timeline and remove any claim of demonstrated
interruption. Do not stitch a successful-looking interruption from separate takes.

## Human demonstration scripts

The lines below are scripts for the human demonstrator, not scripts for model
responses. Responses are nondeterministic. Use fresh sessions and neutral English;
record several complete takes, retain originals privately and document selection.

**A — Natural full-duplex conversation (Moshi).**

1. Start with microphone on: “Hi! I'm planning a quiet afternoon. What is one
   simple thing I could do?”
2. Let the actual response finish, or use a clearly audible natural pause.
3. Follow up: “That sounds good. What should I bring?”
4. Optional acknowledgment: “Thanks, I'll try that.”

Capture 30–60 seconds. Select one complete short exchange for the trailer and
keep the longer conversation for the walkthrough. Leave the mic on throughout.
Do not add a user transcript to the UI; editorial captions are visibly separate.
Avoid claims that Moshi follows unsupported custom system instructions.

**B — User barge-in, with an observable change of request.**

1. Ask: “Could you describe three easy activities for a rainy afternoon?”
2. After the model has audibly started its answer, speak over it naturally:
   “Sorry, just one outdoor idea instead.”
3. Keep recording without touching Clear local playback or Interrupt.
4. Let the model's actual subsequent speech play out. If useful, ask:
   “What was the outdoor idea?”

Capture at least five seconds before overlap and ten seconds after it. Keep mic
and model tracks separate so overlap and later behavior can be assessed. Review
whether output audibly changes and whether the next answer addresses the revised
request. Distinguish semantic adaptation, silence, continued speech and mere local
muting. No success is assumed. Record an equivalent modular take for the walkthrough
if authorized resources are available; its VAD-triggered cancellation differs from
Moshi's continuous model. Demonstrate the explicit Interrupt button separately
and label it as a control, not natural barge-in.

**C — Modular dialogue and turn detection.**

1. Select Modular Pipeline and wait for readiness. Start the microphone.
2. Say: “I have bread and tomatoes. Suggest one quick lunch.”
3. Keep a natural pause; do not click a button to manufacture end-of-turn.
4. Let the full spoken answer finish. Ask: “Can I make it without an oven?”
5. For the longer cut, optionally pause mid-sentence once: “I would like a simple
   lunch … with no oven.” Show the actual endpointing outcome, including a premature
   turn if it occurs; one successful take is not a robustness benchmark.

Frame user and assistant transcripts clearly. Explain VAD and semantic turn
detection separately. Do not animate fake per-stage completion events over a real
take. Use only actual available timings in Details and label their clock semantics.

**D — Mode switching, reset and reconnect.**

1. With both services independently confirmed warm, stop speaking and select the
   other architecture. Keep the entire click/readiness transition in the take.
2. Restart microphone capture if the interface requires it; the switch disconnects
   the old session and clears transient conversation state.
3. Say: “Hello again. Give me one short greeting.” Capture the actual response.
4. In the walkthrough, explain: “Switching connects a new session to an already
   loaded backend. Conversation context is not transferred.”
5. Show Reset with narration “This clears the view and local audio”; show Reconnect
   separately with narration “This starts a fresh backend session.” Do not ask the
   model to prove server-context deletion through Reset.

## Technical walkthrough — initial 04:00 cut

| Time | Content | Source |
| --- | --- | --- |
| 00:00–00:20 | Purpose, project contribution, real versus explanatory visuals | Generated title plus narrator |
| 00:20–00:50 | Two architectures, named configured models; separate VAD/turn detection; CPU proxy versus GPU inference | Generated diagram; cite manifest |
| 00:50–01:50 | Full-duplex natural conversation and uncut barge-in attempt, discuss actual outcome | Real screen + mic + Moshi audio |
| 01:50–02:45 | Modular exchange, transcripts, real endpointing and optionally interruption | Real screen + mic + modular audio |
| 02:45–03:15 | Warm switch; new session; Reset versus Reconnect; optional TV view | Real interface with narration between interactions |
| 03:15–03:45 | Details, supported measurements and N/A, latency method with caveats | Real Details + generated explanatory annotations |
| 03:45–04:00 | One-session limitation, optional Nemotron not shown, credits, code/citation link | Generated close |

The final walkthrough may extend to five minutes for intact evidence. A three-minute
version trims explanations and complete exchanges, never model thinking time inside
an exchange. No montage is presented as a matched performance comparison.
