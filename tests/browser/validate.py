#!/usr/bin/env python3
"""Exercise the real browser audio worklets with deterministic mock transport."""
import asyncio
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.browser.controls import ui_action
from scripts.run_demo import Handler
from playwright.async_api import async_playwright

INSTRUMENT = """
(() => {
  const Original = window.AudioWorkletNode;
  const OriginalSocket = window.WebSocket;
  window.__sockets = [];
  window.WebSocket = class extends OriginalSocket {
    constructor(...args) { super(...args); window.__sockets.push(this); if (window.__sockets.length > 32) window.__sockets.shift(); }
  };
  window.__audioObservation = { peak: 0, received: 0 };
  window.AudioWorkletNode = class extends Original {
    constructor(context, name, options) {
      super(context, name, options);
      if (name === 'audio-playback') {
        const analyser = context.createAnalyser(); analyser.fftSize = 256;
        this.connect(analyser);
        const data = new Float32Array(256);
        setInterval(() => {
          analyser.getFloatTimeDomainData(data);
          for (const sample of data) window.__audioObservation.peak = Math.max(window.__audioObservation.peak, Math.abs(sample));
        }, 10);
      }
      if (name === 'mic-capture') this.port.addEventListener('message', e => {
        if (e.data instanceof ArrayBuffer) window.__audioObservation.received += e.data.byteLength;
      });
    }
  };
})();
"""


async def diagnostic(page):
    return await page.evaluate("""async () => {
      // Import the page's exact entry URL so diagnostics never instantiate a
      // second client when release versions are included in module URLs.
      const entry = document.querySelector('script[type="module"][src]').src;
      return (await import(entry)).getDiagnostics();
    }""")


async def conversation(page, delay=0, jitter=0, stall=0, chunk_jitter=0, response_delay=0):
    await ui_action(page, "#mock-delay", "fill", str(response_delay))
    await ui_action(page, "#mock-jitter", "fill", str(chunk_jitter))
    await ui_action(page, "#mock-network-delay", "fill", str(delay))
    await ui_action(page, "#mock-network-jitter", "fill", str(jitter))
    await ui_action(page, "#mock-stall", "fill", str(stall))
    await ui_action(page, "#mock-button", "click")
    await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length > 100")
    await page.wait_for_function("document.querySelector('#m-audio').textContent !== '—'")
    await page.wait_for_function("document.querySelector('#m-response-duration').textContent !== '—'")
    await page.wait_for_timeout(350)
    result = await diagnostic(page)
    assert result["synthetic"] and result["queuedMs"] <= result['maxQueuedMs']
    return result


async def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    os.environ["VOICE_DEMO_MOSHI_URL"] = f"ws://127.0.0.1:{port}/mock"
    os.environ["VOICE_DEMO_MODULAR_URL"] = f"ws://127.0.0.1:{port}/mock"
    os.environ["VOICE_DEMO_NEMOTRON_URL"] = f"ws://127.0.0.1:{port}/mock"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    output = ROOT / "artifacts/browser"
    output.mkdir(parents=True, exist_ok=True)
    report = {"measurement": "synthetic", "browser": "Chromium", "checks": [], "network_matrix": []}
    browser = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox", "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={ROOT}/artifacts/input/browser.wav",
                "--autoplay-policy=no-user-gesture-required"])
            context = await browser.new_context(permissions=["microphone", "camera"])
            await context.add_init_script(INSTRUMENT)
            page = await context.new_page()
            errors, uploads = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            def observe_socket(ws):
                ws.on("framesent", lambda payload: uploads.append(payload))
            page.on("websocket", observe_socket)
            await page.goto(f"http://127.0.0.1:{port}")
            await ui_action(page, ".settings-card > summary", "click")
            await ui_action(page, '#end-to-end-model', "select_option", 'nemotron')
            await conversation(page)
            await page.wait_for_function("window.__audioObservation.peak > 0.005")
            report["checks"].append("real playback worklet renders nonzero samples")
            await ui_action(page, "#camera-button", "click")
            await page.wait_for_function("document.querySelector('#camera').srcObject?.getVideoTracks().length === 1")
            await page.evaluate("window.__cameraTrack = document.querySelector('#camera').srcObject.getVideoTracks()[0]")
            for index in range(20):
                await ui_action(page, f".mode[data-mode={'modular' if index % 2 == 0 else 'nemotron'}]", "click")
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
                assert await page.evaluate("window.__cameraTrack === document.querySelector('#camera').srcObject.getVideoTracks()[0]")
                assert await page.locator(".message").count() == 0
            report["checks"].append("20 session switches preserve camera and clear conversation")
            before = (await diagnostic(page))["staleEvents"]
            await page.evaluate("""() => {
              const old = window.__sockets[0];
              old.onmessage({data: JSON.stringify({type:'response.output_audio_transcript.delta', delta:'STALE EVENT'})});
            }""")
            assert "STALE EVENT" not in await page.locator("#messages").inner_text()
            assert (await diagnostic(page))["staleEvents"] > before
            report["checks"].append("late old-socket callback cannot alter the new session")
            await conversation(page)
            await ui_action(page, "#mic-button", "click")
            await page.wait_for_function("document.querySelector('#mic-button').classList.contains('active')")
            await page.wait_for_function("window.__audioObservation.received > 0", timeout=15000)
            await page.wait_for_function("[...document.querySelectorAll('.message.user p, #technical-user-transcript p')].some(p => p.textContent.includes('microphone turn'))", timeout=20000)
            await ui_action(page, "#mic-button", "click")
            report["checks"].append("fake WAV microphone traverses capture worklet and WebSocket")
            camera_payloads = [p for p in uploads if isinstance(p, str) and any(s in p.lower() for s in ['input_image', 'image/jpeg', 'image/png', 'video_frame'])]
            assert not camera_payloads
            report["checks"].append("camera produces no image/video WebSocket messages")
            for delay in [0, 50, 100, 200]:
                for jitter in [0, 20, 50]:
                    before = await diagnostic(page)
                    result = await conversation(page, delay, jitter)
                    deltas = {key: result[key] - before[key] for key in ('playbackUnderruns', 'streamingUnderruns', 'droppedInputChunks', 'droppedOutputChunks', 'staleEvents')}
                    report["network_matrix"].append({"delay_ms": delay, "jitter_ms": jitter, "diagnostics": result, 'counter_deltas': deltas})
            await conversation(page, stall=500)
            report["checks"].append("12 added-event-delay/jitter combinations and 500ms stall")
            report['chunk_jitter_scenarios'] = []
            for jitter in [0, 50, 100, 200]:
                result = await conversation(page, chunk_jitter=jitter)
                report['chunk_jitter_scenarios'].append({'chunk_jitter_ms': jitter, 'diagnostics': result})
            delayed = await conversation(page, response_delay=1000)
            assert delayed['metrics']['speechEndToFirstAudioMs'] >= 1000
            report['checks'].append('0/50/100/200ms response chunk jitter and 1000ms artificial response delay')
            await ui_action(page, "#mock-button", "click")
            await page.wait_for_function("!document.querySelector('#interrupt-button').disabled")
            before = (await diagnostic(page))["clears"]
            await ui_action(page, "#interrupt-button", "click")
            await page.wait_for_timeout(100)
            assert (await diagnostic(page))["clears"] > before
            report["checks"].append("interrupt clears local playback and cancels mock response")
            await ui_action(page, "#mock-malformed", "click")
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Malformed backend event'")
            await conversation(page)
            await ui_action(page, "#mock-disconnect", "click")
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Disconnected'")
            await conversation(page)
            report["checks"].append("malformed event and disconnect recover without reload")
            await ui_action(page, "#nemotron-url", "fill", f"ws://127.0.0.1:{port}/not-a-backend")
            await ui_action(page, "#reconnect-button", "click")
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Backend unavailable'")
            await ui_action(page, ".mode[data-mode=modular]", "click")
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            report["checks"].append("unavailable selected backend does not block other architecture")
            denied = await context.new_page()
            await denied.add_init_script("""localStorage.clear(); navigator.mediaDevices.getUserMedia = async (constraints) => {
              throw new DOMException('Permission denied in automated scenario', 'NotAllowedError');
            };""")
            await denied.goto(f"http://127.0.0.1:{port}")
            await denied.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            await ui_action(denied, '#camera-button', "click")
            await denied.wait_for_function("document.querySelector('#camera-button').textContent === 'Unavailable'")
            assert await denied.locator('#status-text').inner_text() == 'Ready'
            await ui_action(denied, '#mic-button', "click")
            await denied.wait_for_function("document.querySelector('#status-text').textContent.startsWith('Microphone unavailable')")
            assert not (await diagnostic(denied))["captureActive"]
            await denied.evaluate("() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('No device', 'NotFoundError'); }; }")
            await ui_action(denied, '#mic-button', "click")
            await denied.wait_for_function("document.querySelector('#status-text').textContent.includes('No device')")
            await ui_action(denied, '.mode[data-mode=modular]', "click")
            await denied.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            report["checks"].append("camera/microphone denial and missing microphone remain recoverable")
            await denied.close()
            await page.screenshot(path=str(output / "mock.png"), full_page=True)
            assert not errors, errors
            report["checks"].append("no browser JavaScript errors")
            report["audio_observation"] = await page.evaluate("window.__audioObservation")
            report["status"] = "PASS"
            await browser.close()
    except Exception as error:
        report["status"] = "FAIL"; report["error"] = repr(error)
        if browser:
            try: await page.screenshot(path=str(output / "failure.png"), full_page=True)
            except Exception: pass
        raise
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        server.shutdown(); server.server_close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__": asyncio.run(main())
