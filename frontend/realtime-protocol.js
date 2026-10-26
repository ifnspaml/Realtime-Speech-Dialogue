export const PCM_RATE = 24000;

/** Decode the real HF extension; never infer equivalent end-to-end stages. */
export function modularStageTimings(event) {
  const value = event?.response?.metadata?.['speech_to_speech.turn_latency'];
  if (!value) return null;
  try {
    const timings = typeof value === 'string' ? JSON.parse(value) : value;
    const ms = key => typeof timings[key] === 'number' && Number.isFinite(timings[key]) && timings[key] >= 0 ? timings[key] * 1000 : null;
    return { sttMs: ms('stt_s'), llmMs: ms('llm_s'), ttsFirstAudioMs: ms('tts_ttfa_s') };
  } catch { return null; }
}

/** Keep the common event surface small; preserve unknown fields for debug/replay. */
export function normalizeEvent(event) {
  if (!event || typeof event !== 'object' || typeof event.type !== 'string') {
    throw new TypeError('Realtime event must be an object with a type');
  }
  return { ...event, backendEventType: event.type };
}

export function sessionUpdate({ mode, instructions }) {
  const session = {
    type: 'realtime',
    instructions,
    audio: {
      input: { format: { type: 'audio/pcm', rate: PCM_RATE } },
      output: { format: { type: 'audio/pcm', rate: PCM_RATE } },
    },
    tools: [],
  };
  // The modular server uses `voice` and `turn_detection`; NVIDIA documents
  // these as silently ignored. Do not imply that they have equal semantics.
  if (mode === 'modular') session.audio.input.turn_detection = { type: 'server_vad', interrupt_response: true };
  return { type: 'session.update', session };
}

/** Read explicit little-endian samples, including slices of larger buffers. */
export function pcm16BytesToFloat32(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength % 2 !== 0) throw new TypeError('PCM16 data must contain complete samples');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const samples = new Float32Array(bytes.byteLength / 2);
  for (let i = 0; i < samples.length; i += 1) {
    const value = view.getInt16(i * 2, true);
    samples[i] = value < 0 ? value / 32768 : value / 32767;
  }
  return samples;
}

/** Browser receipt/render timestamps; missing boundaries remain null. */
export class EventMetrics {
  reset() { this.times = {}; this.response = 'idle'; }
  constructor() { this.reset(); }
  apply(event, at = performance.now()) {
    const type = normalizeEvent(event).type;
    const names = {
      'input_audio_buffer.speech_started': 'speechStart',
      'input_audio_buffer.speech_stopped': 'speechEnd',
      'conversation.item.input_audio_transcription.delta': 'firstTranscript',
      'response.output_audio_transcript.delta': 'firstAssistantText',
      'response.output_audio_transcript.done': 'assistantTextEnd',
      'response.output_audio.delta': 'firstAssistantAudio',
      'demo.playback.started': 'firstPlayback',
      'response.created': 'responseStart',
      'response.done': 'responseEnd',
    };
    // Deltas can repeat; keep the first observation for each metric in a turn.
    if (names[type] && this.times[names[type]] === undefined) this.times[names[type]] = at;
    if (type === 'conversation.item.input_audio_transcription.completed' && this.times.firstTranscript === undefined) this.times.firstTranscript = at;
    if (type === 'response.output_audio_transcript.done' && this.times.firstAssistantText === undefined) this.times.firstAssistantText = at;
    if (type === 'response.created') this.response = 'in_progress';
    if (type === 'response.done') this.response = event.response?.status || 'completed';
    return this.snapshot();
  }
  snapshot() {
    const times = this.times;
    const diff = (end, start) => times[end] === undefined || times[start] === undefined ? null : times[end] - times[start];
    return {
      ...times,
      speechStartToFirstAudioMs: diff('firstAssistantAudio', 'speechStart'),
      speechEndToFirstAudioMs: diff('firstAssistantAudio', 'speechEnd'),
      responseDurationMs: diff('responseEnd', 'responseStart'),
      speechEndToResponseEndMs: diff('responseEnd', 'speechEnd'),
      receivedToPlaybackMs: diff('firstPlayback', 'firstAssistantAudio'),
      response: this.response,
    };
  }
}
