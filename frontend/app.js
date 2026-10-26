import { bindPresentation } from './presentation.js?v=publication-v2';
import { base64ToBytes, base64FromArrayBuffer } from './vendor/hf-demo/ws/codec.js';
import { EventMetrics, pcm16BytesToFloat32, modularStageTimings } from './realtime-protocol.js?v=publication-v2';
import { BACKENDS, backendSessionUpdate } from './backends.js?v=publication-v2';
import { BoundedPCMQueue, LocalInputRecording, PCMInputDiagnostics, microphoneConstraints, continuousStreamStalled } from './audio.js?v=publication-v2';

const FRONTEND_BUILD = 'publication-v2';

// One page owns the audio graph and active transport for every architecture.
// Model replacement is a separate operator action handled by the supervisor.
const $ = (id) => document.getElementById(id);
const ui = {
  modes: [...document.querySelectorAll('.mode')], architecture: $('architecture'),
  archLabel: $('architecture-label'), backendName: $('backend-name'), dot: $('status-dot'),
  status: $('status-text'), mic: $('mic-button'), mock: $('mock-button'), interrupt: $('interrupt-button'),
  messages: $('messages'), camera: $('camera'), cameraButton: $('camera-button'),
  metricsLabel: $('metrics-label'), nemotronUrl: $('nemotron-url'), modularUrl: $('modular-url'), moshiUrl: $('moshi-url'),
};
const labels = {
  nemotron: { name: 'NemotronLabs VoiceChat 11B', tag: 'END-TO-END · FULL-DUPLEX' },
  moshi: { name: 'Moshi (7B)', tag: 'END-TO-END · FULL-DUPLEX' },
  modular: { name: 'Hugging Face speech-to-speech', tag: 'MODULAR · CASCADED' },
};
let config = { mockUrl: 'ws://localhost:7860/mock', nemotronUrl: '', modularUrl: '' };
let mode = 'moshi';
let endToEndModel = 'moshi';
let backendChosenByUser = false;
let sessionReady = false;
let syntheticBackend = false;
let replayBackend = false;
function replayMode() { return Boolean(config.replay || replayBackend); }
let socket = null;
let audioContext = null;
let micStream = null;
let captureNode = null;
let captureSource = null;
let captureGain = null;
// Async permission requests and old socket callbacks must not revive a session
// after an architecture switch. Capture/connect callbacks retain this token.
let connectionGeneration = 0;
let activeResponseId = null;
let connectionTimer = null;
let audioSetupPromise = null;
const diagnostics = { droppedInputChunks: 0, droppedOutputChunks: 0, playbackUnderruns: 0, streamingUnderruns: 0, staleEvents: 0, workletQueuedMs: 0, peakQueuedMs: 0, workletPlayed: 0, clears: 0 };
let audioOutputComplete = false;
let playbackNode = null;
let muted = false;
let currentAssistant = null;
let turnStart = 0;
let speechEnd = 0;
// Real modular TTS can deliver a complete sentence much faster than playback.
const MAX_PLAYBACK_MS = 30000;
const playbackQueue = new BoundedPCMQueue({ sampleRate: 24000, maxMs: MAX_PLAYBACK_MS });
let responseActive = false;
let mockSession = false;
let suppressOutput = false;
const metrics = new EventMetrics();
const inputRecording = new LocalInputRecording();
const inputSignal = new PCMInputDiagnostics();
let receivedOutputSamples = 0;
let lastInputRenderAt = 0;
let inputChunksSent = 0;
let microphoneSettings = null;
let inputRecordingMode = mode;
let inputStreamTimer = null;
let captureStartedAt = null;
let lastAudioReceivedAt = null;
let sessionFailureReason = null;
// Presentation duration counts only successful microphone capture intervals.
// Keep it separate from the capture watchdog's start timestamp.
let demoElapsedMs = 0;
let demoStarted = false;
let demoIntervalStartedAt = null;
let playbackAnalyser = null;
const outputObservation = new Float32Array(256);
let technicalUser = null;
// Presentation reads existing state; it never sends protocol or model commands.
const presentation = bindPresentation(() => {
  let sum = 0;
  if (playbackAnalyser) {
    playbackAnalyser.getFloatTimeDomainData(outputObservation);
    for (const sample of outputObservation) sum += sample * sample;
  }
  return { mode, captureActive: Boolean(captureNode), sessionReady, responseActive,
    status: ui.status.textContent, error: ui.dot.classList.contains('error'),
    inputDbfs: inputSignal.snapshot().rmsDbfs ?? -60,
    outputRms: Math.sqrt(sum / outputObservation.length), demoStarted,
    demoElapsedMs: demoElapsedMs + (demoIntervalStartedAt === null ? 0 : performance.now() - demoIntervalStartedAt),
    responseMs: metrics.snapshot().speechEndToFirstAudioMs,
    measurement: replayMode() ? 'REPLAY · recorded session' : mockSession || syntheticBackend ? 'SIMULATION · synthetic' : '' };
});

/** Display transport activity without treating amplitude or sends as recognition. */
function renderInputDiagnostics() {
  $('download-input').disabled = inputRecording.bytes === 0;
  $('record-input').checked = inputRecording.active;
  $('input-diagnostics').textContent = `${inputChunksSent} input chunks queued for upload · ${inputRecording.seconds.toFixed(1)} s saved locally${inputRecording.active ? ' · recording' : ' · recording off'}.`;
  const signal = inputSignal.snapshot();
  const active = Boolean(captureNode);
  const level = signal.rmsDbfs === null ? 'silent PCM' : `${signal.rmsDbfs.toFixed(0)} dBFS`;
  $('input-level').value = active ? Math.max(-60, signal.rmsDbfs ?? -60) : -60;
  $('input-monitor-status').textContent = `Microphone ${active ? 'on' : 'stopped'} · ${active ? 'level' : 'last level'}: ${level} · captured ${signal.capturedSeconds.toFixed(1)} s · signal above −50 dBFS: ${signal.signalSeconds.toFixed(1)} s · queued for upload ${signal.sentSeconds.toFixed(1)} s · backend audio received ${(receivedOutputSamples / 24000).toFixed(1)} s${signal.clippedSamples ? ' · clipping detected' : ''}.`;
  lastInputRenderAt = performance.now();
}

function setStatus(text, kind = 'ready') {
  ui.status.textContent = text;
  ui.dot.className = `dot ${kind}`;
  presentation.render();
}

function resetMetrics(label) {
  ui.metricsLabel.textContent = replayMode() && !mockSession ? 'Replay / recorded session · no live model' : label;
  for (const id of ['m-speech-start','m-speech-end','m-transcript','m-assistant-text','m-utterance-end','m-audio','m-playback','m-end-audio','m-response-duration']) $(id).textContent = '—';
  $('m-stages').textContent = 'N/A';
  turnStart = 0; speechEnd = 0;
  metrics.reset();
}

function renderArchitecture() {
  $('end-to-end-name').textContent = labels[endToEndModel].name;
  const modular = mode === 'modular';
  ui.architecture.className = `architecture ${modular ? 'modular' : 'end-to-end'}`;
  ui.archLabel.textContent = labels[mode].tag;
  ui.archLabel.classList.toggle('modular', modular);
  ui.backendName.textContent = labels[mode].name;
  ui.interrupt.textContent = modular ? 'Interrupt' : 'Clear local playback';
  $('mic-note').textContent = modular
    ? 'Speak naturally to the modular assistant. Camera preview stays local.'
    : 'Keep the microphone on throughout the conversation. Speak to interrupt. Clear playback mutes until you speak again. Camera stays local.';
  $('metrics-contract').textContent = modular
    ? 'Timings include transport and browser scheduling. Speech boundaries differ between architectures.'
    : mode === 'moshi' ? 'Moshi streams continuously. User transcripts, speech boundaries and per-turn completion are not provided: N/A.' : 'VoiceChat streams audio continuously. First-chunk latency and per-turn response duration are N/A.';
  if (mode === 'moshi') $('mic-note').textContent = 'Keep the microphone on. Assistant text is continuous; user transcription is not provided. Camera stays local.';
  ui.architecture.innerHTML = modular
    ? '<span class="arch-node">Microphone</span><span class="arch-arrow">→</span><div class="arch-stack"><span class="arch-node"><b>VAD + end-of-turn</b><small>Silero + Smart Turn (~8M EOT)</small></span><span class="arch-arrow">→</span><span class="arch-node"><b>STT</b><small>Parakeet TDT (0.6B)</small></span><span class="arch-arrow">→</span><span class="arch-node"><b>LLM</b><small>Qwen3 Instruct (4B)</small></span><span class="arch-arrow">→</span><span class="arch-node"><b>TTS</b><small>Qwen3-TTS (1.7B)</small></span></div><span class="arch-arrow">→</span><span class="arch-node">Speaker</span>'
    : '<span class="arch-node">Microphone</span><span class="arch-arrow">↔</span><span class="arch-node core"><b>' + labels[mode].name + '</b><small>Continuous speech stream</small></span><span class="arch-arrow">↔</span><span class="arch-node">Speaker</span>';
  $('technical-transcript-panel').hidden = mode !== 'nemotron';
}

function clearMessages() {
  ui.messages.innerHTML = '<p class="empty">Start the demo to begin a conversation.</p>';
  $('technical-user-transcript').replaceChildren(); technicalUser = null;
  presentation.follow.reset(true);
  currentAssistant = null;
}

function addMessage(role, text = '') {
  ui.messages.querySelector('.empty')?.remove();
  const row = document.createElement('div');
  row.className = `message ${role}`;
  const name = document.createElement('b');
  name.textContent = role === 'user' ? 'You' : 'Assistant';
  const body = document.createElement('p');
  body.textContent = text;
  row.append(name, body);
  ui.messages.append(row);
  presentation.follow.schedule();
  if (role === 'assistant') currentAssistant = body;
  return body;
}

/** Decode one PCM chunk and transfer ownership to the common output worklet. */
function playAudioDelta(encoded, event) {
  if (!playbackNode || !encoded || suppressOutput) return;
  if (mode === 'moshi') { responseActive = true; ui.interrupt.disabled = false; }
  const bytes = base64ToBytes(encoded);
  const samples = pcm16BytesToFloat32(bytes);
  const key = `${event.item_id || 'assistant'}:${event.content_index || 0}`;
  if (!playbackQueue.enqueue(samples.length)) {
    diagnostics.droppedOutputChunks += 1;
    clearPlayback();
    setStatus('Audio queue limit reached', 'error');
    return;
  }
  playbackNode.port.postMessage({ kind: 'audio', samples, key }, [samples.buffer]);
  if (!$('m-audio').textContent || $('m-audio').textContent === '—') markMetric('m-audio');
}

function clearPlayback() {
  diagnostics.clears += 1;
  if (playbackNode) playbackNode.port.postMessage({ kind: 'clear', clearId: diagnostics.clears });
  playbackQueue.clear();
}

function markMetric(id) {
  const value = Math.max(0, performance.now() - turnStart);
  $(id).textContent = `${value.toFixed(0)} ms`;
}

function renderDerivedMetrics() {
  const values = metrics.snapshot();
  const format = value => value === null ? '—' : `${value.toFixed(0)} ms`;
  // A negative endpoint-to-audio time is valid for overlapping speech.
  $('m-end-audio').textContent = format(values.speechEndToFirstAudioMs);
  $('m-response-duration').textContent = format(values.responseDurationMs);
  if (BACKENDS[mode].continuous && !mockSession) {
    $('m-audio').textContent = 'Continuous stream';
    $('m-end-audio').textContent = 'N/A';
    $('m-response-duration').textContent = 'N/A · session scoped';
    if (mode === 'moshi') for (const id of ['m-speech-start', 'm-speech-end', 'm-transcript', 'm-utterance-end']) $(id).textContent = 'N/A';
  }
}

function onEvent(event) {
  if (!event || typeof event.type !== 'string') throw new TypeError('Missing realtime event type');
  if (event.type === 'input_audio_buffer.speech_started') resetMetrics(mockSession ? 'Mock / synthetic' : 'Real backend · browser receipt times');
  // A cancelled/replaced response may still have buffered output in transit.
  if (event.type.startsWith('response.output_') && activeResponseId && event.response_id && event.response_id !== activeResponseId) {
    diagnostics.staleEvents += 1; return;
  }
  metrics.apply(event);
  switch (event.type) {
    case 'session.created':
      syntheticBackend = event.session?.measurement === 'synthetic';
      replayBackend = ['replay', 'synthetic-replay'].includes(event.session?.measurement);
      if (replayBackend) ui.metricsLabel.textContent = 'Replay / recorded session · no live model';
      if (syntheticBackend) ui.metricsLabel.textContent = 'Mock / synthetic · no live model';
      setStatus(mockSession ? 'Mock ready' : 'Connected', 'ready'); break;
    case 'session.updated': sessionReady = true; setStatus(mockSession ? 'Mock ready' : 'Ready', 'ready'); break;
    case 'input_audio_buffer.speech_started':
      playbackNode?.port.postMessage({ kind: 'mark_turn' });
      turnStart = performance.now();
      $('m-speech-start').textContent = '0 ms';
      if (responseActive || playbackQueue.queuedMs > 0) { clearPlayback(); responseActive = false; suppressOutput = mode === 'modular' || mockSession; }
      if (mode === 'nemotron' && !mockSession) { suppressOutput = false; currentAssistant = null; }
      document.querySelector('.message.user[data-active="true"]')?.removeAttribute('data-active');
      if (mode === 'modular') {
        const body = addMessage('user'); body.parentElement.dataset.active = 'true';
      } else technicalUser = null;
      break;
    case 'conversation.item.input_audio_transcription.delta': {
      if (mode !== 'modular') {
        if (mode === 'nemotron') {
          if (!technicalUser) { technicalUser = document.createElement('p'); $('technical-user-transcript').append(technicalUser); }
          technicalUser.textContent += event.delta || '';
        }
        if ($('m-transcript').textContent === '—') markMetric('m-transcript');
        break;
      }
      if (!document.querySelector('.message.user[data-active="true"]')) {
        const body = addMessage('user'); body.parentElement.dataset.active = 'true';
      }
      const row = document.querySelector('.message.user[data-active="true"] p');
      if (row) row.textContent += event.delta || '';
      if ($('m-transcript').textContent === '—') markMetric('m-transcript');
      break;
    }
    case 'conversation.item.input_audio_transcription.completed': {
      if (mode !== 'modular') {
        if (mode === 'nemotron' && event.transcript) {
          if (!technicalUser) { technicalUser = document.createElement('p'); $('technical-user-transcript').append(technicalUser); }
          technicalUser.textContent = event.transcript; technicalUser = null;
        }
        if ($('m-transcript').textContent === '—') markMetric('m-transcript');
        break;
      }
      let row = document.querySelector('.message.user[data-active="true"] p');
      if (!row) row = addMessage('user');
      if (row) { row.textContent = event.transcript || row.textContent; row.parentElement.removeAttribute('data-active'); }
      if ($('m-transcript').textContent === '—') markMetric('m-transcript');
      break;
    }
    case 'input_audio_buffer.speech_stopped':
      speechEnd = performance.now();
      $('m-speech-end').textContent = turnStart ? `${(speechEnd - turnStart).toFixed(0)} ms after start` : 'received';
      break;
    case 'response.created':
      audioOutputComplete = false;
      activeResponseId = event.response?.id || null;
      responseActive = true; suppressOutput = false; currentAssistant = null;
      ui.interrupt.disabled = false;
      break;
    case 'response.output_audio_transcript.delta':
      if (!event.delta) break;
      if (!currentAssistant) { currentAssistant = addMessage('assistant'); markMetric('m-assistant-text'); }
      responseActive = true; ui.interrupt.disabled = false;
      currentAssistant.textContent += event.delta || '';
      break;
    case 'response.output_audio_transcript.done':
      if (!currentAssistant && event.transcript) currentAssistant = addMessage('assistant', event.transcript);
      else if (currentAssistant && event.transcript) currentAssistant.textContent = event.transcript;
      if (event.transcript) markMetric('m-utterance-end');
      break;
    case 'response.output_audio.delta':
      lastAudioReceivedAt = performance.now();
      if (captureNode && event.delta) receivedOutputSamples += base64ToBytes(event.delta).byteLength / 2;
      playAudioDelta(event.delta, event); break;
    case 'response.output_audio.done': audioOutputComplete = true; break;
    case 'response.done':
      if (activeResponseId && event.response?.id && event.response.id !== activeResponseId) { diagnostics.staleEvents += 1; break; }
      responseActive = false; ui.interrupt.disabled = true;
      if (mode === 'modular' && !mockSession) {
        const stages = modularStageTimings(event);
        if (stages) $('m-stages').textContent = [stages.sttMs, stages.llmMs, stages.ttsFirstAudioMs].map(value => value === null ? 'N/A' : `${Math.round(value)} ms`).join(' / ');
      }
      if (event.response?.status === 'cancelled') setStatus(captureNode ? 'Listening' : mockSession ? 'Mock ready' : 'Ready', 'ready');
      else if (event.response?.status && event.response.status !== 'completed') setStatus(`Response ${event.response.status}`, 'error');
      break;
    case 'session.end': setStatus('Disconnected', 'error'); break;
    case 'error':
      if (['inference_timeout', 'session_timeout'].includes(event.error?.code)) {
        sessionFailureReason = event.error?.message || 'Backend inference failed';
        stopCapture(); clearPlayback();
      }
      setStatus(event.error?.message || 'Backend error', 'error'); break;
    default: break;
  }
  renderDerivedMetrics();
}

function endpointFor(modeName) {
  const input = ui[modeName + 'Url'];
  const value = input.value.trim();
  if (value) localStorage.setItem(`voice-demo.${modeName}.url`, value);
  return value;
}

/** Return whether WebSocket.send accepted the event, not whether the server read it. */
function send(event, target = socket) {
  if (target?.readyState !== WebSocket.OPEN) return false;
  if (event.type === 'input_audio_buffer.append' && target.bufferedAmount > 192000) {
    diagnostics.droppedInputChunks += 1;
    stopCapture(); setStatus('Upload stalled · reconnect to continue', 'error'); return false;
  }
  target.send(JSON.stringify({ ...event, event_id: crypto.randomUUID?.() || `${Date.now()}` }));
  return true;
}

function disconnect() {
  connectionGeneration += 1;
  sessionReady = false;
  syntheticBackend = false;
  clearTimeout(connectionTimer);
  activeResponseId = null;
  // Camera tracks are independent of microphone/session ownership and stay live.
  stopCapture();
  resetDemoTimer();
  clearPlayback();
  responseActive = false;
  sessionFailureReason = null;
  ui.interrupt.disabled = true;
  if (socket) { const old = socket; socket = null; old.close(1000, 'backend switch'); }
}

async function connect(url, isMock = false, attempt = 0) {
  disconnect();
  const generation = connectionGeneration;
  clearMessages();
  mockSession = isMock;
  resetMetrics(isMock ? 'Mock / synthetic' : 'Real backend');
  setStatus('Connecting…');
  try {
    await setupAudio();
    if (generation !== connectionGeneration) return;
    const target = new WebSocket(url);
    socket = target;
    let connectionFailed = false;
    let poolBusy = false;
    turnStart = performance.now();
    connectionTimer = setTimeout(() => {
      if (socket !== target) return;
      connectionFailed = true; target.close(); setStatus('Backend connection timed out', 'error');
    }, 15000);
    // Transport open is insufficient: microphone capture waits for session.updated.
    target.onopen = () => {
      if (socket !== target) return;
      setStatus('Connected · awaiting session', 'ready');
      send(backendSessionUpdate(mode, 'Speak naturally and keep responses concise.'), target);
    };
    target.onmessage = (message) => {
      if (socket !== target) { diagnostics.staleEvents += 1; return; }
      try {
        const event = JSON.parse(message.data);
        if (event.error?.code === 'session_limit_reached' || event.error?.type === 'session_limit_reached') poolBusy = true;
        if (event.type === 'session.updated') clearTimeout(connectionTimer);
        onEvent(event);
      }
      catch { setStatus('Malformed backend event', 'error'); }
    };
    target.onerror = () => { if (socket !== target) return; connectionFailed = true; setStatus('Backend unavailable', 'error'); };
    target.onclose = () => {
      if (socket !== target) return;
      clearTimeout(connectionTimer); stopCapture(); clearPlayback(); responseActive = false;
      ui.interrupt.disabled = true;
      setStatus(sessionFailureReason || (poolBusy ? 'Backend busy · retrying session' : connectionFailed ? 'Backend unavailable' : 'Disconnected'), 'error');
      // HF releases its warm pipeline asynchronously after the old socket closes.
      if (poolBusy && attempt < 4) {
        setTimeout(() => { if (socket === target && generation === connectionGeneration) connect(url, isMock, attempt + 1); }, 1500);
      } else if (poolBusy) setStatus('Backend busy · reconnect when available', 'error');
    };
  } catch (error) { setStatus(`Unavailable: ${error.message}`, 'error'); }
}

async function setupAudio() {
  // Share initialization when reconnect and a microphone gesture overlap.
  if (audioSetupPromise) return audioSetupPromise;
  audioSetupPromise = initializeAudio();
  return audioSetupPromise;
}

async function initializeAudio() {
  audioContext = new AudioContext();
  // Connecting is permitted before user activation; playback resumes on a gesture.
  if (navigator.userActivation?.hasBeenActive) await audioContext.resume();
  await audioContext.audioWorklet.addModule('/vendor/hf-demo/worklets/mic-capture.js');
  await audioContext.audioWorklet.addModule('/vendor/hf-demo/worklets/audio-playback.js');
  playbackNode = new AudioWorkletNode(audioContext, 'audio-playback');
  playbackNode.port.postMessage({ kind: 'config', inputRate: 24000, maxQueuedMs: MAX_PLAYBACK_MS });
  playbackNode.port.onmessage = (event) => {
    if (event.data?.kind === 'stats') playbackQueue.reportQueuedMs(event.data.queuedMs || 0);
    if (event.data?.kind === 'stats') { diagnostics.workletQueuedMs = event.data.queuedMs; diagnostics.peakQueuedMs = event.data.peakQueuedMs; diagnostics.workletPlayed = event.data.played; }
    if (event.data?.kind === 'underrun') {
      diagnostics.playbackUnderruns += 1;
      if (responseActive && !audioOutputComplete) diagnostics.streamingUnderruns += 1;
    }
    if (event.data?.kind === 'overflow') diagnostics.droppedOutputChunks += 1;
    if (event.data?.kind === 'render_started') {
      if ($('m-playback').textContent === '—') markMetric('m-playback');
      metrics.apply({ type: 'demo.playback.started' });
    }
  };
  playbackNode.connect(audioContext.destination);
  // A read-only output analyser drives presentation levels, including silence.
  // The original playback destination, rate, worklet and queue stay unchanged.
  playbackAnalyser = audioContext.createAnalyser(); playbackAnalyser.fftSize = 256;
  playbackNode.connect(playbackAnalyser);
}

async function startCapture() {
  if (captureNode) { stopCapture(); return; }
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    const endpoint = endpointFor(mode);
    if (!endpoint) { setStatus('Backend unavailable · configure an endpoint', 'error'); return; }
    await connect(endpoint, false);
    const activeSocket = socket;
    if (activeSocket && activeSocket.readyState !== WebSocket.OPEN) {
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, 5000);
        activeSocket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
        activeSocket.addEventListener('error', () => { clearTimeout(timer); resolve(); }, { once: true });
      });
    }
  }
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const waitingSocket = socket;
  const deadline = performance.now() + 15000;
  while (!sessionReady && socket === waitingSocket && performance.now() < deadline) await new Promise(resolve => setTimeout(resolve, 40));
  if (!sessionReady || socket !== waitingSocket) { setStatus('Session is not ready · reconnect', 'error'); return; }
  const generation = connectionGeneration;
  try {
    await setupAudio();
    await audioContext.resume();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: microphoneConstraints($('microphone-processing').value), video: false });
    if (generation !== connectionGeneration) { stream.getTracks().forEach((track) => track.stop()); return; }
    micStream = stream;
    microphoneSettings = stream.getAudioTracks()[0]?.getSettings() || null;
    captureSource = audioContext.createMediaStreamSource(micStream);
    captureNode = new AudioWorkletNode(audioContext, 'mic-capture', { processorOptions: { targetRate: 24000, chunkMs: BACKENDS[mode].chunkMs, version: 'hf-audio-24k-v2' } });
    // Keep the capture graph connected, while preventing local mic monitoring.
    // The muted gain is downstream of the worklet's uploaded PCM buffers.
    captureGain = audioContext.createGain(); captureGain.gain.value = 0;
    inputSignal.reset(); inputChunksSent = 0; receivedOutputSamples = 0;
    renderInputDiagnostics();
    captureNode.port.onmessage = (event) => {
      if (generation !== connectionGeneration) return;
      // Inspect the actual resampled upload bytes. Only the opt-in recorder keeps
      // audio; the level monitor retains counters and scalar amplitude values.
      const sampleCount = event.data instanceof ArrayBuffer ? inputSignal.observe(event.data) : 0;
      if (event.data instanceof ArrayBuffer && !muted && socket?.readyState === WebSocket.OPEN) {
        if (send({ type: 'input_audio_buffer.append', audio: base64FromArrayBuffer(event.data) })) {
          inputChunksSent += 1;
          inputSignal.markSent(sampleCount);
          inputRecording.append(event.data);
        }
      }
      if (performance.now() - lastInputRenderAt >= 250) renderInputDiagnostics();
    };
    captureSource.connect(captureNode).connect(captureGain).connect(audioContext.destination);
    captureStartedAt = performance.now(); lastAudioReceivedAt = null;
    demoIntervalStartedAt = performance.now(); demoStarted = true;
    // A successful session.update/health probe does not prove inference is running.
    // Stop uploading before a stalled server can silently discard old PCM.
    const captureSocket = socket;
    inputStreamTimer = setInterval(() => {
      if (generation !== connectionGeneration || !BACKENDS[mode].continuous || mockSession) return;
      if (continuousStreamStalled({ startedAt: captureStartedAt, lastAudioAt: lastAudioReceivedAt, now: performance.now() })) {
        sessionFailureReason = `${labels[mode].name} audio stalled · reconnect`;
        stopCapture(); clearPlayback();
        setStatus(sessionFailureReason, 'error');
        captureSocket?.close(1000, 'continuous audio stalled');
      }
    }, 1000);
    ui.mic.classList.add('active'); ui.mic.querySelector('span').textContent = 'Stop'; ui.mic.setAttribute('aria-label', 'Stop microphone');
    setStatus('Listening', 'ready');
  } catch (error) { setStatus(`Microphone unavailable: ${error.message}`, 'error'); }
}

function stopCapture() {
  const wasCapturing = Boolean(captureNode);
  if (demoIntervalStartedAt !== null) {
    demoElapsedMs += performance.now() - demoIntervalStartedAt;
    demoIntervalStartedAt = null;
  }
  clearInterval(inputStreamTimer); inputStreamTimer = null; captureStartedAt = null;
  if (wasCapturing) inputRecording.stop();
  captureSource?.disconnect(); captureSource = null;
  captureGain?.disconnect(); captureGain = null;
  if (captureNode) { captureNode.port.onmessage = null; captureNode.port.close(); captureNode.disconnect(); }
  captureNode = null;
  if (wasCapturing) renderInputDiagnostics();
  micStream?.getTracks().forEach((track) => track.stop()); micStream = null;
  ui.mic?.classList.remove('active');
  ui.mic?.setAttribute('aria-label', 'Start demo');
  if (ui.mic?.querySelector('span')) ui.mic.querySelector('span').textContent = 'Start Demo';
  if (wasCapturing && socket?.readyState === WebSocket.OPEN) setStatus(mockSession ? 'Mock ready' : 'Ready', 'ready');
}

async function chooseBackend(selected) {
  // Route a new session to a warm backend. This path never calls /api/model.
  if (selected === mode) return;
  mode = selected;
  disconnect();
  ui.modes.forEach(item => {
    const active = (item.dataset.mode === 'modular') === (mode === 'modular');
    item.classList.toggle('selected', active); item.setAttribute('aria-pressed', String(active));
  });
  renderArchitecture(); clearMessages(); resetMetrics('No measurement'); setStatus('Backend unavailable · not configured', 'error');
  const endpoint = endpointFor(mode);
  if (endpoint) await connect(endpoint, false);
}
ui.modes.forEach(button => button.addEventListener('click', () => {
  backendChosenByUser = true;
  chooseBackend(button.dataset.mode === 'modular' ? 'modular' : endToEndModel);
}));
$('end-to-end-model').addEventListener('change', async event => {
  backendChosenByUser = true;
  endToEndModel = event.target.value;
  if (mode !== 'modular') await chooseBackend(endToEndModel);
  else renderArchitecture();
  await updateReadiness();
});

ui.mock.addEventListener('click', async () => {
  await connect(config.mockUrl, true);
  const begin = () => send({
    type: 'demo.mock_turn', transcript: 'How do these two voice architectures differ?',
    delayMs: Number($('mock-delay').value) || 0,
    jitterMs: Number($('mock-jitter').value) || 0,
    stallMs: Number($('mock-stall').value) || 0,
    networkDelayMs: Number($('mock-network-delay').value) || 0,
    networkJitterMs: Number($('mock-network-jitter').value) || 0,
  });
  const target = socket;
  const guardedBegin = () => { if (socket === target) begin(); };
  if (target?.readyState === WebSocket.OPEN) guardedBegin();
  else if (target) target.addEventListener('open', guardedBegin, { once: true });
});
ui.mic.addEventListener('click', startCapture);
function resetDemoTimer() {
  demoElapsedMs = 0;
  demoStarted = Boolean(captureNode);
  demoIntervalStartedAt = demoStarted ? performance.now() : null;
}
$('reset-button').addEventListener('click', () => {
  // Reset the view and local playback, preserving the live session and camera.
  // It intentionally does not cancel inference or reload either model.
  clearPlayback(); clearMessages(); resetMetrics('No measurement');
  resetDemoTimer(); presentation.render();
});
document.getElementById('reconnect-button').addEventListener('click', async () => {
  const endpoint = endpointFor(mode);
  if (!endpoint) { setStatus('No real endpoint configured · run a simulated turn', 'error'); return; }
  await connect(endpoint, false);
});
ui.interrupt.addEventListener('click', () => {
  clearPlayback(); suppressOutput = mode !== 'moshi';
  // `response.cancel` is documented by HF but not in NVIDIA's client-event
  // list. Nemotron interruption is therefore local until real integration
  // establishes its server control behavior.
  if (mode === 'modular' || mockSession) send({ type: 'response.cancel' });
  responseActive = false; ui.interrupt.disabled = true;
});
ui.cameraButton.addEventListener('click', async () => {
  if (ui.camera.srcObject) { ui.camera.srcObject.getTracks().forEach((track) => track.stop()); ui.camera.srcObject = null; ui.cameraButton.textContent = 'Enable'; presentation.render(); return; }
  try { const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); ui.camera.srcObject = stream; ui.cameraButton.textContent = 'Disable'; presentation.render(); }
  catch (error) { ui.cameraButton.textContent = 'Unavailable'; setTimeout(() => { ui.cameraButton.textContent = 'Enable'; }, 1800); }
});
$('mock-disconnect').addEventListener('click', () => {
  if (!mockSession || !socket) { setStatus('Connect the mock before simulating a disconnect', 'error'); return; }
  // Let the mock server close the transport; browsers cannot send code 1011.
  send({ type: 'demo.disconnect' });
});
$('mock-malformed').addEventListener('click', () => {
  if (mockSession) send({ type: 'demo.malformed' });
  else setStatus('Connect the mock before sending a malformed event', 'error');
});
$('record-input').addEventListener('change', () => {
  if ($('record-input').checked) { inputRecording.start(); inputRecordingMode = mode; } else inputRecording.stop();
  renderInputDiagnostics();
});
$('download-input').addEventListener('click', () => {
  inputRecording.stop(); renderInputDiagnostics();
  const url = URL.createObjectURL(new Blob([inputRecording.wav()], { type: 'audio/wav' }));
  const link = document.createElement('a');
  link.href = url; link.download = `${inputRecordingMode}-uploaded-input.wav`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function init() {
  $('frontend-build').textContent = FRONTEND_BUILD;
  renderArchitecture(); resetMetrics('No measurement');
  try { config = { ...config, ...(await (await fetch('/api/config')).json()) }; } catch {}
  $('operator-controls').hidden = !config.modelControl;
  // Default to Moshi, but respect a deliberately replaced resident model and
  // a selection made while the initial configuration fetch was pending.
  if (!backendChosenByUser && config.defaultEndToEndModel in labels && config.defaultEndToEndModel !== 'modular') {
    mode = endToEndModel = config.defaultEndToEndModel;
    $('end-to-end-model').value = endToEndModel;
    renderArchitecture();
  }
  ui.nemotronUrl.value = localStorage.getItem('voice-demo.nemotron.url') || config.nemotronUrl || '';
  ui.modularUrl.value = localStorage.getItem('voice-demo.modular.url') || config.modularUrl || '';
  ui.moshiUrl.value = localStorage.getItem('voice-demo.moshi.url') || config.moshiUrl || '';
  setStatus('Backend unavailable · not configured', 'error');
  const endpoint = endpointFor(mode);
  if (endpoint && !socket) await connect(endpoint, false);
}
window.addEventListener('beforeunload', disconnect);
init();

async function updateReadiness() {
  try {
    const states = await (await fetch('/api/status', { cache: 'no-store' })).json();
    for (const name of ['nemotron', 'modular', 'moshi']) $(name + '-readiness').textContent = states[name]?.state || 'UNKNOWN';
    $('end-to-end-readiness').textContent = states[endToEndModel]?.state || 'UNKNOWN';
    if (states.slot) {
      $('slot-status').textContent = `${states.slot.model || 'No model'} · ${states.slot.state}`;
      $('model-availability').textContent = `Resident model: ${states.slot.model || 'none'}. Use operator controls to replace it.`;
    }
  } catch {
    for (const name of ['nemotron', 'modular', 'moshi']) $(name + '-readiness').textContent = 'UNKNOWN';
  }
}
updateReadiness();
setInterval(updateReadiness, 8000);
$('load-model').addEventListener('click', async () => {
  // Explicit replacement can take minutes; READY is reported by the supervisor
  // only after a prerecorded WAV produces real streamed model output.
  if (mode !== 'modular') disconnect();
  try {
    const response = await fetch('/api/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: endToEndModel }) });
    if (!response.ok) throw new Error(await response.text());
    $('slot-status').textContent = 'Replacement requested · reconnect when READY';
    await updateReadiness();
  } catch (error) { $('slot-status').textContent = 'Replacement failed: ' + error.message; }
});

// Read-only diagnostics support automation without changing the audio path.
export function getDiagnostics() {
  return { frontendBuild: FRONTEND_BUILD, ...diagnostics, queuedMs: playbackQueue.queuedMs, maxQueuedMs: MAX_PLAYBACK_MS, generation: connectionGeneration,
    inputChunksSent, microphoneSettings, localInputRecordingSeconds: inputRecording.seconds,
    inputSignal: inputSignal.snapshot(), receivedOutputSeconds: receivedOutputSamples / 24000,
    captureActive: Boolean(captureNode), responseActive, mode, synthetic: mockSession,
    measurement: replayMode() ? 'replay' : mockSession || syntheticBackend ? 'synthetic' : 'real', metrics: metrics.snapshot() };
}
