export class BoundedPCMQueue {
  constructor({ sampleRate = 24000, maxMs = 8000 } = {}) {
    if (!Number.isFinite(sampleRate) || sampleRate <= 0 || !Number.isFinite(maxMs) || maxMs <= 0) throw new RangeError('Invalid PCM queue limits');
    this.sampleRate = sampleRate;
    this.maxSamples = Math.floor(sampleRate * maxMs / 1000);
    this.queuedSamples = 0;
  }
  enqueue(sampleCount) {
    if (!Number.isInteger(sampleCount) || sampleCount < 0) throw new TypeError('PCM sample count must be a non-negative integer');
    if (this.queuedSamples + sampleCount > this.maxSamples) return false;
    this.queuedSamples += sampleCount;
    return true;
  }
  reportQueuedMs(ms) {
    // Worklet reports correct the main-thread estimate as playback consumes PCM.
    this.queuedSamples = Math.max(0, Math.min(this.maxSamples, Math.round((Number(ms) || 0) * this.sampleRate / 1000)));
  }
  clear() { this.queuedSamples = 0; }
  get queuedMs() { return this.queuedSamples / this.sampleRate * 1000; }
}

export function microphoneConstraints(profile = 'voice') {
  // These are browser requests. Track settings report the effective values;
  // disabling them does not guarantee that hardware or OS processing is absent.
  return { echoCancellation: profile !== 'raw', noiseSuppression: profile === 'voice', autoGainControl: profile === 'voice' };
}

/** Metadata only: measure the exact PCM16 leaving the capture worklet.
 * Signal duration is an amplitude heuristic, not VAD or speech recognition.
 * A successful WebSocket send is not a server acknowledgement.
 */
export class PCMInputDiagnostics {
  constructor({ sampleRate = 24000, signalThresholdDb = -50 } = {}) {
    if (!Number.isFinite(sampleRate) || sampleRate <= 0 || !Number.isFinite(signalThresholdDb)) throw new RangeError('Invalid input diagnostic settings');
    this.sampleRate = sampleRate;
    this.signalThreshold = 10 ** (signalThresholdDb / 20);
    this.reset();
  }
  reset() {
    this.samples = 0; this.sentSamples = 0; this.signalSamples = 0;
    this.clippedSamples = 0; this.rms = 0; this.peak = 0;
  }
  observe(buffer) {
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength % 2) throw new TypeError('Expected complete PCM16 samples');
    const view = new DataView(buffer);
    const count = buffer.byteLength / 2;
    let energy = 0, peak = 0;
    for (let offset = 0; offset < buffer.byteLength; offset += 2) {
      const pcm = view.getInt16(offset, true);
      const magnitude = Math.abs(pcm / 32768);
      energy += magnitude * magnitude; peak = Math.max(peak, magnitude);
      if (pcm === -32768 || pcm === 32767) this.clippedSamples += 1;
    }
    this.rms = count ? Math.sqrt(energy / count) : 0;
    this.peak = peak; this.samples += count;
    if (this.rms >= this.signalThreshold) this.signalSamples += count;
    return count;
  }
  markSent(count) {
    // Keep transport accounting separate from capture, including silent chunks.
    if (!Number.isInteger(count) || count < 0 || this.sentSamples + count > this.samples) throw new RangeError('Invalid sent sample count');
    this.sentSamples += count;
  }
  snapshot() {
    return { capturedSeconds: this.samples / this.sampleRate,
      sentSeconds: this.sentSamples / this.sampleRate,
      signalSeconds: this.signalSamples / this.sampleRate,
      rmsDbfs: this.rms ? 20 * Math.log10(this.rms) : null,
      peak: this.peak, clippedSamples: this.clippedSamples };
  }
}

/** VoiceChat emits continuous PCM; a long output gap means input is unsafe. */
export function continuousStreamStalled({ startedAt, lastAudioAt, now }) {
  if (startedAt === null) return false;
  return now - (lastAudioAt ?? startedAt) >= (lastAudioAt === null ? 10000 : 5000);
}

/** Opt-in, bounded local recording of PCM successfully sent to the backend. */
export class LocalInputRecording {
  constructor({ sampleRate = 24000, maxSeconds = 30 } = {}) {
    if (!Number.isInteger(sampleRate) || sampleRate <= 0 || !Number.isFinite(maxSeconds) || maxSeconds <= 0 || maxSeconds > 30) throw new RangeError('Invalid local recording limit');
    this.sampleRate = sampleRate;
    this.maxBytes = Math.floor(sampleRate * maxSeconds) * 2;
    this.reset();
  }
  reset() { this.chunks = []; this.bytes = 0; this.active = false; }
  start() { this.reset(); this.active = true; }
  stop() { this.active = false; }
  append(buffer) {
    if (!this.active) return;
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength % 2) throw new TypeError('Expected complete PCM16 samples');
    const remaining = this.maxBytes - this.bytes;
    const length = Math.min(remaining, buffer.byteLength);
    // Own a bounded copy so worklet buffer transfers cannot alter the recording.
    if (length > 0) { this.chunks.push(new Uint8Array(buffer.slice(0, length))); this.bytes += length; }
    if (this.bytes >= this.maxBytes) this.stop();
  }
  get seconds() { return this.bytes / (this.sampleRate * 2); }
  wav() {
    // Write a standard mono PCM16 RIFF header followed by unchanged upload bytes.
    const output = new Uint8Array(44 + this.bytes);
    const view = new DataView(output.buffer);
    const text = (offset, value) => { for (let i = 0; i < value.length; i++) output[offset + i] = value.charCodeAt(i); };
    text(0, 'RIFF'); view.setUint32(4, 36 + this.bytes, true); text(8, 'WAVE');
    text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, this.sampleRate, true);
    view.setUint32(28, this.sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    text(36, 'data'); view.setUint32(40, this.bytes, true);
    let offset = 44;
    for (const chunk of this.chunks) { output.set(chunk, offset); offset += chunk.length; }
    return output;
  }
}
