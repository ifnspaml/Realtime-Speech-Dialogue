/** Presentation-only transcript following and read-only activity indicators. */
export class TranscriptFollow {
  constructor(viewport, latest) {
    this.viewport = viewport;
    this.latest = latest;
    this.following = true;
    this.frame = null;
    this.timer = null;
    this.lastTop = viewport.scrollTop;
    this.programmatic = false;
    this.target = 0;
    this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    viewport.addEventListener('wheel', event => {
      if (event.deltaY < 0) this.pause();
    }, { passive: true });
    viewport.addEventListener('keydown', event => {
      if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) this.pause();
    });
    viewport.addEventListener('pointerdown', event => {
      const bounds = viewport.getBoundingClientRect();
      if (event.clientX >= bounds.right - 20) this.pause();
    });
    let touchY = null;
    viewport.addEventListener('touchstart', event => { touchY = event.touches[0]?.clientY; }, { passive: true });
    viewport.addEventListener('touchmove', event => {
      if (touchY !== null && event.touches[0]?.clientY > touchY) this.pause();
    }, { passive: true });
    viewport.addEventListener('scroll', () => {
      // Wheel, keyboard, touch and scrollbar input above pause explicitly.
      // A delayed animation/layout scroll event is not evidence of user input.
      this.lastTop = viewport.scrollTop;
    }, { passive: true });
    latest.addEventListener('click', () => this.reset());
    this.observer = new MutationObserver(() => this.schedule());
    this.observer.observe(viewport, { childList: true, subtree: true, characterData: true });
    this.resize = new ResizeObserver(() => {
      viewport.style.setProperty('--breathing-space', `${viewport.clientHeight * .24}px`);
      this.schedule();
    });
    this.resize.observe(viewport);
  }

  pause() {
    this.following = false;
    this.latest.hidden = false;
    cancelAnimationFrame(this.frame);
    this.frame = null;
    this.programmatic = false;
  }

  reset(fresh = false) {
    cancelAnimationFrame(this.frame);
    this.following = true;
    this.latest.hidden = true;
    this.programmatic = true;
    if (fresh) this.viewport.scrollTop = 0;
    this.lastTop = this.viewport.scrollTop;
    // Clearing history itself produces a scroll event. Let it settle before
    // interpreting scrolling as manual review of the new conversation.
    this.frame = requestAnimationFrame(() => {
      this.frame = requestAnimationFrame(() => {
        this.frame = null; this.programmatic = false; this.schedule();
      });
    });
  }

  schedule() {
    const rows = [...this.viewport.querySelectorAll('.message')];
    rows.forEach((row, index) => {
      row.classList.toggle('current', index === rows.length - 1);
      row.classList.toggle('recent', index === rows.length - 2);
    });
    if (!this.following || this.timer) return;
    // Coalesce streamed tokens rather than restarting native smooth scrolling.
    this.timer = setTimeout(() => { this.timer = null; this.follow(); }, 120);
  }

  follow() {
    if (!this.following) return;
    const active = this.viewport.querySelector('.message:last-child');
    if (!active) return;
    const bottom = active.getBoundingClientRect().bottom - this.viewport.getBoundingClientRect().top + this.viewport.scrollTop;
    this.target = Math.max(0, Math.min(this.viewport.scrollHeight - this.viewport.clientHeight, bottom - this.viewport.clientHeight * .76));
    if (this.frame) return;
    let lastTime = null;
    const tick = time => {
      if (!this.following) return;
      const elapsed = lastTime === null ? 16 : Math.min(50, time - lastTime);
      lastTime = time;
      const delta = this.target - this.viewport.scrollTop;
      this.programmatic = true;
      this.viewport.scrollTop += this.reducedMotion || Math.abs(delta) < 1 ? delta : delta * (1 - Math.exp(-elapsed / 65));
      this.lastTop = this.viewport.scrollTop;
      if (this.reducedMotion || Math.abs(delta) < 1) {
        // Scroll notifications arrive after the animation callback.
        this.frame = requestAnimationFrame(() => { this.programmatic = false; this.frame = null; });
      } else this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }
}

export function bindPresentation(getState) {
  const $ = id => document.getElementById(id);
  const follow = new TranscriptFollow($('messages'), $('latest-button'));
  document.body.classList.toggle('tv', new URLSearchParams(location.search).get('display') === 'tv');
  const details = $('technical-details');
  $('details-button').addEventListener('click', () => details.showModal());
  $('close-details').addEventListener('click', () => details.close());
  details.addEventListener('click', event => { if (event.target === details && event.clientX < details.getBoundingClientRect().left) details.close(); });
  // Escape and focus restoration are supplied by the native modal dialog.
  function render() {
    const state = getState();
    const speaking = state.sessionReady && state.outputRms > .001;
    let label = state.status;
    if (!state.error && state.sessionReady) {
      label = state.captureActive ? (speaking ? 'Listening + Speaking' : 'Listening') : (speaking ? 'Speaking' : 'Connected');
      if (state.mode === 'modular' && state.responseActive && !speaking && !state.captureActive) label = 'Responding';
    }
    $('live-state').textContent = label;
    $('live-state-dot').className = `dot ${state.error ? 'error' : state.sessionReady ? 'ready' : ''}`;
    $('input-state').textContent = state.captureActive ? 'Live input' : 'Microphone off';
    $('output-state').textContent = speaking ? 'Playing audio' : 'Quiet';
    // These bars are level indicators, not inferred speech or a fabricated waveform.
    document.querySelector('#input-signal .signal-bars').style.setProperty('--level', state.captureActive ? Math.max(.05, Math.min(1, (state.inputDbfs + 60) / 50)) : .05);
    document.querySelector('#output-signal .signal-bars').style.setProperty('--level', Math.max(.05, Math.min(1, state.outputRms * 10)));
    $('primary-metric-label').textContent = state.mode === 'modular' ? 'RESPONSE' : 'DEMO TIME';
    $('primary-metric').textContent = state.mode === 'modular'
      ? state.responseMs === null ? '—' : `${Math.round(state.responseMs)} ms`
      : `${(state.demoElapsedMs / 1000).toFixed(1)} s`;
    $('primary-metric-note').textContent = state.mode === 'modular' ? 'Speech end → first audio received' : state.captureActive ? 'Continuous stream' : state.demoStarted ? 'Paused · microphone off' : state.sessionReady ? 'Ready to start' : 'Awaiting connection';
    $('measurement-badge').hidden = !state.measurement;
    $('measurement-badge').textContent = state.measurement;
    document.querySelectorAll('.mode').forEach(button => {
      button.querySelector('.selection-label').textContent = button.classList.contains('selected') ? '● SELECTED' : 'SELECT';
    });
    $('camera').hidden = !$('camera').srcObject;
    $('camera-off').hidden = Boolean($('camera').srcObject);
  }
  render();
  setInterval(render, 120);
  return { follow, render };
}
