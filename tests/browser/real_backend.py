#!/usr/bin/env python3
"""Validate real browser capture/playback against an already warm backend."""
import argparse
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
from tests.browser.validate import INSTRUMENT, diagnostic
from playwright.async_api import async_playwright


async def main(args):
    os.environ[f"VOICE_DEMO_{args.backend.upper()}_URL"] = args.url
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"backend": args.backend, "measurement": getattr(args, 'measurement', 'real'), "status": "FAIL"}
    if hasattr(args, 'source_validation_status'): report['source_validation_status'] = args.source_validation_status
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox", "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream", f"--use-file-for-fake-audio-capture={args.wav.resolve()}",
                "--autoplay-policy=no-user-gesture-required"])
            context = await browser.new_context(permissions=["microphone"])
            await context.add_init_script(INSTRUMENT)
            page = await context.new_page()
            await page.goto(getattr(args, 'ui_url', None) or f"http://127.0.0.1:{server.server_address[1]}")
            if args.backend == "modular": await ui_action(page, ".mode[data-mode=modular]", "click")
            else:
                await ui_action(page, '.settings-card > summary', "click")
                await ui_action(page, '#end-to-end-model', "select_option", 'nemotron')
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'", timeout=30000)
            await ui_action(page, "#mic-button", "click")
            await page.wait_for_function("[...document.querySelectorAll('.message.user p, #technical-user-transcript p')].some(p => p.textContent.length > 3)", timeout=120000)
            await page.wait_for_function("[...document.querySelectorAll('.message.assistant p')].some(p => p.textContent.length > 3)", timeout=120000)
            await page.wait_for_function("window.__audioObservation.peak > 0.002", timeout=120000)
            await page.wait_for_function("document.querySelector('#m-utterance-end').textContent !== '—'", timeout=120000)
            await ui_action(page, "#mic-button", "click")
            observed = await diagnostic(page)
            assert observed['droppedOutputChunks'] == 0, 'Playback overflow dropped real audio'
            assert observed['droppedInputChunks'] == 0, 'Upload backpressure dropped real input'
            report.update(status="PASS", diagnostics=await diagnostic(page),
                transcripts=await page.locator("#messages").inner_text(),
                audio_observation=await page.evaluate("window.__audioObservation"))
            report['metrics_label'] = await page.locator('#metrics-label').inner_text()
            await page.screenshot(path=str(args.output / "browser.png"), full_page=True)
            await browser.close()
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        server.shutdown(); server.server_close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["modular", "nemotron"], required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--wav", type=Path, default=ROOT / "artifacts/input/browser.wav")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--ui-url', help='Use an already deployed UI, for example through one localhost SSH forward')
    asyncio.run(main(parser.parse_args()))
