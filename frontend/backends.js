/** Protocol capabilities describe real semantics, not inferred model stages. */
export const BACKENDS = Object.freeze({
  modular: { continuous: false, userTranscript: true, speechBoundaries: true, turnDone: true, instructions: true, chunkMs: 40 },
  nemotron: { continuous: true, userTranscript: true, speechBoundaries: true, turnDone: true, instructions: true, chunkMs: 80 },
  moshi: { continuous: true, userTranscript: false, speechBoundaries: false, turnDone: false, instructions: false, chunkMs: 80 },
});

// Event availability does not imply equal timing semantics. Nemotron can send
// completion events for a session while the UI hides per-turn duration metrics.
/** Build the smallest supported configuration for the selected transport. */
export function backendSessionUpdate(mode, instructions) {
  const session = { type: 'realtime', audio: {
    input: { format: { type: 'audio/pcm', rate: 24000 } },
    output: { format: { type: 'audio/pcm', rate: 24000 } },
  }, tools: [] };
  // Moshi's bridge rejects custom instructions/tools rather than pretending
  // that its native audio model implements an OpenAI-style prompt API.
  if (BACKENDS[mode].instructions) session.instructions = instructions;
  if (mode === 'modular') session.audio.input.turn_detection = { type: 'server_vad', interrupt_response: true };
  return { type: 'session.update', session };
}
