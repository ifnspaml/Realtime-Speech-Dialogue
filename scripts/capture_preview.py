#!/usr/bin/env python3
"""Capture a silent, explicitly simulated UI preview using CPU-only test services.

Requires the project tools, Playwright Chromium, FFmpeg and generated test audio.
No real inference endpoint, model artifact, microphone or camera is used.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aiohttp import web
from playwright.async_api import async_playwright
from scripts.run_demo import Handler
from services.health import HealthMonitor
from services.moshi.adapter import create_app as adapter_app
from services.moshi.mock import create_app as native_mock
from tests.browser.controls import ui_action


async def start(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    return runner, site._server.sockets[0].getsockname()[1]


async def capture():
    wav = ROOT / 'artifacts/input/browser.wav'
    if not wav.is_file():
        raise SystemExit('Generate synthetic test audio first: bash scripts/prepare_test_audio.sh')
    output = ROOT / 'assets/readme'
    frames = ROOT / 'artifacts/readme-preview/frames'
    output.mkdir(parents=True, exist_ok=True)
    frames.mkdir(parents=True, exist_ok=True)
    runners = []
    server = None
    browser = None
    report = {'status': 'FAIL', 'measurement': 'synthetic', 'camera': 'off', 'model_inference': False}
    try:
        runner, native_port = await start(native_mock())
        runners.append(runner)
        runner, bridge_port = await start(adapter_app(f'ws://127.0.0.1:{native_port}/api/chat', measurement='synthetic'))
        runners.append(runner)
        os.environ['VOICE_DEMO_MOSHI_URL'] = f'ws://127.0.0.1:{bridge_port}/v1/realtime'
        os.environ['VOICE_DEMO_SLOT_CONTROL'] = '0'
        os.environ.pop('VOICE_DEMO_NEMOTRON_URL', None)
        os.environ.pop('VOICE_DEMO_REPLAY', None)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        os.environ['VOICE_DEMO_MODULAR_URL'] = f'ws://127.0.0.1:{port}/mock'
        server.health_monitor = HealthMonitor()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=[
                '--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
                f'--use-file-for-fake-audio-capture={wav}', '--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(viewport={'width': 1600, 'height': 900}, permissions=['microphone'])
            page = await context.new_page()
            errors, replacements = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: replacements.append(request.url) if request.method == 'POST' and request.url.endswith('/api/model') else None)
            await page.goto(f'http://127.0.0.1:{port}')
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
            await page.evaluate("""() => {
              const label=document.createElement('div'); label.id='preview-label';
              label.textContent='SIMULATED UI · NO MODEL INFERENCE';
              label.style.cssText='position:fixed;right:22px;bottom:8px;padding:8px 12px;border:1px solid #4f9b8e;border-radius:6px;background:#132b2d;color:#83dfcd;font:700 12px Arial,sans-serif;letter-spacing:1px;z-index:20';
              document.body.append(label);
            }""")
            await page.wait_for_function("[...document.querySelectorAll('.brand img')].every(i => i.complete && i.naturalWidth > 0)")
            assert await page.locator('.university-seal').count() == 1
            assert await page.locator('.ifn-logo').count() == 1
            frame = 0
            for mode in ['moshi', 'modular']:
                if mode == 'modular':
                    await ui_action(page, '.mode[data-mode=modular]', 'click')
                    await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
                    # Enter the explicit mock session so the UI labels every simulated metric.
                    await ui_action(page, '#mock-button', 'click')
                    await page.wait_for_function("document.querySelector('.message.assistant:last-child p')?.textContent.endsWith('stages.')")
                    await page.wait_for_function("document.querySelector('#interrupt-button').disabled")
                    await ui_action(page, '#reset-button', 'click')
                await ui_action(page, '#mic-button', 'click')
                await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length > 3", timeout=30000)
                if mode == 'modular':
                    await page.wait_for_function("document.querySelector('.message.user p')?.textContent.length > 3", timeout=30000)
                    await page.wait_for_timeout(500)
                assert not await page.locator('#camera').evaluate('video => Boolean(video.srcObject)')
                assert not await page.locator('#technical-details').evaluate('dialog => dialog.open')
                await page.wait_for_function("document.querySelector('#measurement-badge').textContent.includes('SIMULATION')")
                assert 'SIMULATION' in await page.locator('#measurement-badge').inner_text()
                for _ in range(12):
                    await page.screenshot(path=str(frames / f'frame-{frame:03d}.png'))
                    frame += 1
                    await page.wait_for_timeout(250)
                if mode == 'modular':
                    await page.screenshot(path=str(output / 'demo-preview.png'))
                await ui_action(page, '#mic-button', 'click')
            assert not errors, errors
            assert not replacements, replacements
            social = await browser.new_page(viewport={'width': 1280, 'height': 640})
            await social.goto((output / 'social-preview.svg').as_uri())
            await social.screenshot(path=str(ROOT / '.github/social-preview.png'))
            await browser.close()
            browser = None
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '1',
            '-filter_complex_threads', '1', '-framerate', '4', '-i', str(frames / 'frame-%03d.png'),
            '-filter_complex', '[0:v]scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4',
            '-loop', '0', '-map_metadata', '-1', str(output / 'demo-preview.gif')], check=True)
        for path in [output / 'demo-preview.gif', output / 'demo-preview.png', ROOT / '.github/social-preview.png']:
            if path.stat().st_size > 2 * 1024 * 1024:
                raise RuntimeError('Preview asset exceeds the 2 MiB size budget: ' + path.name)
        report.update(status='PASS', frames=frame, model_replacement_requests=0)
    finally:
        if browser:
            await browser.close()
        if server:
            if hasattr(server, 'health_monitor'):
                server.health_monitor.close()
            server.shutdown()
            server.server_close()
        for runner in reversed(runners):
            await runner.cleanup()
        (ROOT / 'artifacts/readme-preview/report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(capture())
