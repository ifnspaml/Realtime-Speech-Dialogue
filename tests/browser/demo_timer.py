#!/usr/bin/env python3
"""Verify active demo time is independent of the warm WebSocket session."""
import asyncio
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.async_api import async_playwright
from scripts.run_demo import Handler
from tests.browser.validate import diagnostic


class ObsoleteClientHandler(Handler):
    """Simulate old cached assets at the previously unversioned entry URLs."""
    def do_GET(self):
        if self.path in ('/app.js', '/presentation.js'):
            payload = b"throw new Error('Obsolete unversioned frontend was loaded');"
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


async def seconds(page):
    return float((await page.locator('#primary-metric').inner_text()).removesuffix(' s'))


async def main():
    output = ROOT / 'artifacts/presentation/demo-timer'
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), ObsoleteClientHandler)
    for mode in ['MOSHI', 'NEMOTRON', 'MODULAR']:
        os.environ[f'VOICE_DEMO_{mode}_URL'] = f'ws://127.0.0.1:{server.server_address[1]}/mock'
    os.environ.pop('VOICE_DEMO_SLOT_CONTROL', None)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {'status':'FAIL', 'measurement':'synthetic', 'checks':[]}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox',
              '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
              '--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(permissions=['microphone'], viewport={'width':1920,'height':1080})
            page = await context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{server.server_address[1]}')
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            await page.wait_for_timeout(1300)
            assert await seconds(page) == 0
            assert await page.locator('#primary-metric-label').inner_text() == 'DEMO TIME'
            assert (await diagnostic(page))['frontendBuild'] == 'publication-v2'
            assert await page.locator('#primary-metric-note').inner_text() == 'Ready to start'
            report['checks'].append('Connected idle session remains at 0.0 s')
            await page.locator('#mic-button').click()
            await page.wait_for_function("document.querySelector('#mic-button').classList.contains('active')")
            await page.wait_for_timeout(1000)
            first = await seconds(page)
            assert .8 <= first <= 2, first
            assert await page.locator('#primary-metric-note').inner_text() == 'Continuous stream'
            await page.locator('#mic-button').click()
            paused = await seconds(page)
            await page.wait_for_timeout(1000)
            assert await seconds(page) == paused
            assert await page.locator('#primary-metric-note').inner_text() == 'Paused · microphone off'
            report['checks'].append('Start counts capture time; Stop freezes the value')
            await page.locator('#mic-button').click()
            await page.wait_for_timeout(650)
            assert await seconds(page) >= paused + .4
            await page.locator('#reset-button').click()
            assert await seconds(page) <= .2
            assert (await diagnostic(page))['captureActive']
            await page.wait_for_timeout(650)
            assert await seconds(page) >= .4
            await page.locator('#mic-button').click()
            await page.locator('#reset-button').click()
            await page.wait_for_timeout(350)
            assert await seconds(page) == 0
            assert await page.locator('#primary-metric-note').inner_text() == 'Ready to start'
            report['checks'].append('Resume accumulates active intervals; Reset zeroes the clock without changing capture')
            await page.locator('#mic-button').click()
            await page.wait_for_timeout(400)
            await page.locator('.mode[data-mode=modular]').click()
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            assert await page.locator('#primary-metric-label').inner_text() == 'RESPONSE'
            await page.locator('.mode[data-mode=nemotron]').click()
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            await page.wait_for_timeout(300)
            assert await seconds(page) == 0
            report['checks'].append('Architecture switching resets active time; Modular response metric is preserved')
            await page.evaluate("() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Test denial', 'NotAllowedError'); }; }")
            await page.locator('#mic-button').click()
            await page.wait_for_function("document.querySelector('#status-text').textContent.startsWith('Microphone unavailable')")
            await page.wait_for_timeout(300)
            assert await seconds(page) == 0
            assert not (await diagnostic(page))['captureActive']
            report['checks'].append('Permission failure does not start the timer')
            # Ordinary reload must select the release entry module, not a cached
            # unversioned app.js, and start with no active microphone interval.
            await page.reload()
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            await page.wait_for_timeout(500)
            assert await seconds(page) == 0
            assert await page.locator('#primary-metric-label').inner_text() == 'DEMO TIME'
            assert (await diagnostic(page))['frontendBuild'] == 'publication-v2'
            report['checks'].append('Versioned client ignores obsolete unversioned assets; ordinary reload remains idle at zero')
            assert not errors, errors
            report['status'] = 'PASS'
            await browser.close()
    finally:
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        server.shutdown(); server.server_close()
    print(json.dumps(report,indent=2))


if __name__ == '__main__': asyncio.run(main())
