#!/usr/bin/env python3
"""Verify input upload stops when a synthetic continuous-audio server stalls."""
import asyncio
import base64
import json
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.browser.controls import ui_action
from scripts.run_demo import Handler
from tests.browser.validate import diagnostic
from playwright.async_api import async_playwright
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


async def main():
    reports = []
    scenario = 'initial'
    received_chunks = 0

    async def stalled_backend(ws):
        nonlocal received_chunks
        first_input_at = None
        await ws.send(json.dumps({'type': 'session.created', 'session': {'id': 'synthetic-stall'}}))
        try:
            async for message in ws:
                event = json.loads(message)
                if event['type'] == 'session.update':
                    await ws.send(json.dumps({'type': 'session.updated', 'session': event['session']}))
                if event['type'] != 'input_audio_buffer.append':
                    continue
                received_chunks += 1
                if first_input_at is None:
                    first_input_at = time.monotonic()
                if scenario == 'midstream' and time.monotonic() - first_input_at < 2:
                    await ws.send(json.dumps({'type': 'response.output_audio.delta',
                        'delta': base64.b64encode(b'\0\0' * 1920).decode()}))
                if scenario == 'error' and received_chunks == 3:
                    await ws.send(json.dumps({'type': 'error', 'error': {
                        'code': 'inference_timeout', 'message': 'Inference timeout'}}))
                    await asyncio.sleep(1)
                    await ws.close(1011, 'synthetic inference failure')
        except ConnectionClosed:
            pass

    async with serve(stalled_backend, '127.0.0.1', 0) as backend:
        port = backend.sockets[0].getsockname()[1]
        os.environ['VOICE_DEMO_NEMOTRON_URL'] = f'ws://127.0.0.1:{port}'
        ui = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=ui.serve_forever, daemon=True).start()
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True, args=[
                    '--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
                    f'--use-file-for-fake-audio-capture={ROOT}/artifacts/input/browser.wav',
                    '--autoplay-policy=no-user-gesture-required'])
                for scenario in ('initial', 'midstream', 'error'):
                    received_chunks = 0
                    context = await browser.new_context(permissions=['microphone'])
                    page = await context.new_page()
                    await page.goto(f'http://127.0.0.1:{ui.server_address[1]}')
                    await ui_action(page, '.settings-card > summary', "click")
                    await ui_action(page, '#end-to-end-model', "select_option", 'nemotron')
                    await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
                    await ui_action(page, '#mic-button', "click")
                    message = 'Inference timeout' if scenario == 'error' else 'audio stalled'
                    await page.wait_for_function("text => document.querySelector('#status-text').textContent.includes(text)", arg=message, timeout=18000)
                    observed = await diagnostic(page)
                    assert not observed['captureActive']
                    assert observed['queuedMs'] == 0
                    assert observed['droppedInputChunks'] == 0
                    stopped_at_chunks = received_chunks
                    await page.wait_for_timeout(1200)
                    assert received_chunks == stopped_at_chunks, 'Upload continued after the watchdog stopped capture'
                    assert received_chunks < 190, 'Watchdog must stop before a 100 x 160 ms inference queue fills'
                    reports.append({'scenario': scenario, 'status': 'PASS', 'input_chunks': received_chunks,
                                    'capture_stopped': True, 'upload_stopped': True,
                                    'message': await page.locator('#status-text').inner_text()})
                    await context.close()
                await browser.close()
        finally:
            ui.shutdown()
            ui.server_close()
    output = ROOT / 'artifacts/browser-input-watchdog/report.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'measurement': 'synthetic failure detection; no model latency claim', 'checks': reports}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
