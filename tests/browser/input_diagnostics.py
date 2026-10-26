#!/usr/bin/env python3
"""Validate input metadata and exact local WAV with fake media and mock only."""
import asyncio
import base64
import json
import math
import os
import struct
import sys
import threading
import time
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.browser.controls import ui_action
from scripts.run_demo import Handler
from tests.browser.validate import diagnostic
from playwright.async_api import async_playwright


async def wait_input(page, predicate):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        stats = await diagnostic(page)
        level = await page.locator('#input-level').evaluate('(element) => element.value')
        if predicate(stats, level):
            return stats
        await page.wait_for_timeout(100)
    raise TimeoutError('Input diagnostic condition did not become true')


async def main():
    output = ROOT / 'artifacts/browser/input-diagnostics'
    output.mkdir(parents=True, exist_ok=True)
    source = output / 'fake-microphone.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
        wav.writeframes(b''.join(struct.pack('<h', int(6000 * math.sin(2 * math.pi * 440 * i / 48000)) if i < 48000 * 2 else 0)
                                 for i in range(48000 * 20)))
    os.environ.pop('VOICE_DEMO_SLOT_CONTROL', None)
    for name in ['MOSHI', 'MODULAR', 'NEMOTRON']:
        os.environ.pop(f'VOICE_DEMO_{name}_URL', None)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    uploaded = bytearray()
    errors = []
    report = {'measurement': 'synthetic', 'checks': []}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=[
                '--no-sandbox', '--use-fake-device-for-media-stream',
                '--use-fake-ui-for-media-stream', f'--use-file-for-fake-audio-capture={source}',
                '--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(permissions=['microphone'], accept_downloads=True)
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def sent(payload):
                event = json.loads(payload)
                if event.get('type') == 'input_audio_buffer.append':
                    uploaded.extend(base64.b64decode(event['audio']))

            page.on('websocket', lambda ws: ws.on('framesent', sent))
            await page.goto(f'http://127.0.0.1:{server.server_address[1]}')
            await ui_action(page, '.settings-card > summary', "click")
            await ui_action(page, '#mock-button', "click")
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Mock ready'")
            await ui_action(page, '#microphone-processing', "select_option", 'raw')
            await ui_action(page, '#record-input', "check")
            await ui_action(page, '#mic-button', "click")
            stats = await wait_input(page, lambda value, level:
                value['inputSignal']['signalSeconds'] > 1
                and value['inputSignal']['rmsDbfs'] is not None
                and value['inputSignal']['rmsDbfs'] > -50 and level > -50)
            assert stats['synthetic'] and stats['inputSignal']['rmsDbfs'] > -50
            assert stats['inputSignal']['sentSeconds'] == stats['inputSignal']['capturedSeconds']
            assert await page.locator('#input-level').evaluate('(element) => element.value') > -50
            assert 'Microphone on' in await page.locator('#input-monitor-status').inner_text()
            silence = await wait_input(page, lambda value, level:
                value['inputSignal']['rmsDbfs'] is None and value['receivedOutputSeconds'] > 0)
            assert silence['inputSignal']['capturedSeconds'] > silence['inputSignal']['signalSeconds']
            await ui_action(page, '#mic-button', "click")
            stopped = await diagnostic(page)
            assert not stopped['captureActive'] and not await page.locator('#record-input').is_checked()
            assert 'Microphone stopped' in await page.locator('#input-monitor-status').inner_text()
            async with page.expect_download() as event:
                await ui_action(page, '#download-input', "click")
            await (await event.value).save_as(output / 'uploaded-input.wav')
            with wave.open(str(output / 'uploaded-input.wav'), 'rb') as wav:
                assert wav.getframerate() == 24000 and wav.getnchannels() == 1
                assert wav.readframes(wav.getnframes()) == uploaded
            report['checks'].extend(['48 kHz fake microphone becomes measured 24 kHz PCM',
                                     'nonzero signal is displayed without claiming recognition',
                                     'silent input increases upload duration, and received mock audio is counted separately',
                                     'local WAV exactly matches WebSocket input',
                                     'stopping microphone stops recording and marks monitor stopped'])
            await ui_action(page, '#mic-button', "click")
            restarted = await wait_input(page, lambda value, level:
                value['captureActive'] and 0 < value['inputSignal']['capturedSeconds'] < stopped['inputSignal']['capturedSeconds'])
            assert restarted['inputSignal']['capturedSeconds'] < stopped['inputSignal']['capturedSeconds']
            await ui_action(page, '#mic-button', "click")
            report['checks'].append('restarting microphone resets signal and upload counters')
            assert not errors, errors
            report['status'] = 'PASS'; report['diagnostics'] = stats
            await browser.close()
    finally:
        server.shutdown(); server.server_close()
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
