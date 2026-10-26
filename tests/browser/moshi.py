#!/usr/bin/env python3
"""Validate capability-aware Moshi using real, mock, or replay audio."""
import argparse
import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from aiohttp import web
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.browser.controls import ui_action
from scripts.run_demo import Handler
from tests.browser.validate import INSTRUMENT, diagnostic
from services.moshi.adapter import create_app
from services.moshi.mock import create_app as mock_app


async def start(app):
    runner=web.AppRunner(app)
    await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0)
    await site.start()
    return runner, site._server.sockets[0].getsockname()[1]


async def main(args):
    runners=[]
    args.output.mkdir(parents=True,exist_ok=True)
    report={'status':'FAIL','backend':'moshi','measurement':args.measurement or ('synthetic' if args.mock else 'real')}
    if args.mock:
        runner, port=await start(mock_app()); runners.append(runner)
        runner, port=await start(create_app(f'ws://127.0.0.1:{port}/api/chat',measurement='synthetic')); runners.append(runner)
        args.url=f'ws://127.0.0.1:{port}/v1/realtime'
    os.environ['VOICE_DEMO_MOSHI_URL']=args.url
    ui=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    if args.mock:
        os.environ['VOICE_DEMO_MODULAR_URL'] = f'ws://127.0.0.1:{ui.server_address[1]}/mock'
    threading.Thread(target=ui.serve_forever,daemon=True).start()
    try:
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',
                f'--use-file-for-fake-audio-capture={args.wav.resolve()}{"%noloop" if getattr(args, "no_loop", False) else ""}','--autoplay-policy=no-user-gesture-required'])
            context=await browser.new_context(permissions=['microphone','camera'])
            await context.add_init_script(INSTRUMENT)
            page=await context.new_page()
            model_requests=[]
            page.on('request', lambda request: model_requests.append(request.url)
                    if request.method == 'POST' and request.url.endswith('/api/model') else None)
            await page.goto(args.ui_url or f'http://127.0.0.1:{ui.server_address[1]}')
            assert not await page.locator('#end-to-end-model').is_visible()
            assert not await page.locator('#input-level').is_visible()
            if args.mock:
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'",timeout=30000)
                assert (await diagnostic(page))['mode']=='moshi'
                report['default_model']='PASS: Moshi connects without a load request'
            await ui_action(page, '.settings-card > summary', "click")
            assert await page.locator('#end-to-end-model').is_visible()
            assert await page.locator('#input-level').is_visible()
            await ui_action(page, '#end-to-end-model', "select_option", 'moshi')
            await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'",timeout=30000)
            await ui_action(page, '#camera-button', "click")
            await page.wait_for_function("document.querySelector('#camera').srcObject?.getVideoTracks().length > 0")
            camera=await page.locator('#camera').evaluate('v => v.srcObject.getVideoTracks()[0].id')
            await ui_action(page, '#mic-button', "click")
            await page.wait_for_function("[...document.querySelectorAll('.message.assistant p')].some(p => p.textContent.length>3)",timeout=60000)
            await page.wait_for_function('window.__audioObservation.peak>0.002',timeout=60000)
            await page.wait_for_timeout(getattr(args, 'listen_seconds', 1.2) * 1000)
            assert await page.locator('.message.user').count()==0,'Fabricated Moshi user transcript'
            for identifier in ['m-transcript','m-speech-start','m-speech-end','m-utterance-end','m-end-audio']:
                assert await page.locator('#'+identifier).inner_text()=='N/A',identifier
            await ui_action(page, '#interrupt-button', "click")
            await page.wait_for_timeout(500)
            observed=await diagnostic(page)
            assert observed['droppedInputChunks']==0 and observed['droppedOutputChunks']==0
            assert await page.locator('#camera').evaluate('v=>v.srcObject.getVideoTracks()[0].id')==camera
            report.update(status='PASS',diagnostics=observed,assistant_text=await page.locator('.message.assistant p').inner_text(),
                          audio_observation=await page.evaluate('window.__audioObservation'),metrics_label=await page.locator('#metrics-label').inner_text())
            if getattr(args, 'exercise_reset', False):
                generation = (await diagnostic(page))['generation']
                await ui_action(page, '#reset-button', 'click')
                after_reset = await diagnostic(page)
                assert after_reset['captureActive'] and after_reset['generation'] == generation
                assert await page.locator('#camera').evaluate('v=>v.srcObject.getVideoTracks()[0].id') == camera
                report['reset'] = 'PASS: capture/session/camera preserved'
            await ui_action(page, '#mic-button', "click")
            if getattr(args, 'exercise_reset', False):
                generation = (await diagnostic(page))['generation']
                await ui_action(page, '#reconnect-button', 'click')
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'", timeout=30000)
                assert (await diagnostic(page))['generation'] > generation
                await ui_action(page, '#mic-button', 'click')
                await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>3", timeout=60000)
                await page.wait_for_function("window.__audioObservation.peak>0.002", timeout=60000)
                await ui_action(page, '#mic-button', 'click')
                report['reconnect'] = 'PASS: new session produces assistant text/audio'
            if args.switch:
                await ui_action(page, '.mode[data-mode=modular]', "click")
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'",timeout=30000)
                await ui_action(page, '#mic-button', "click")
                await page.wait_for_function("document.querySelector('.message.user p')?.textContent.length>3",timeout=60000)
                await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>3",timeout=60000)
                await ui_action(page, '#mic-button', "click")
                await ui_action(page, '.mode[data-mode=nemotron]', "click")
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'",timeout=30000)
                await ui_action(page, '#mic-button', "click")
                await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>3",timeout=30000)
                await ui_action(page, '#mic-button', "click")
                assert await page.locator('#camera').evaluate('v=>v.srcObject.getVideoTracks()[0].id')==camera
                report['architecture_switch'] = 'PASS: Moshi -> Modular -> Moshi; camera preserved'
                await ui_action(page, '#moshi-url', "fill", 'ws://127.0.0.1:1/unavailable')
                await ui_action(page, '#reconnect-button', "click")
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Backend unavailable'",timeout=15000)
                await ui_action(page, '.mode[data-mode=modular]', "click")
                await page.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'",timeout=30000)
                report['unavailable_fallback'] = 'PASS: modular usable without reload'
            assert not model_requests, 'Loading a page or switching architecture must not replace models'
            report['developer_controls']='PASS: model selector and input diagnostics start collapsed'
            report['model_load_requests']=len(model_requests)
            await page.screenshot(path=str(args.output/'browser.png'),full_page=True)
            await browser.close()
    except Exception as error:
        report['error']=repr(error)
        raise
    finally:
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        ui.shutdown();ui.server_close()
        for runner in reversed(runners): await runner.cleanup()
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mock',action='store_true')
    parser.add_argument('--url',default='ws://127.0.0.1:9005/v1/realtime')
    parser.add_argument('--ui-url')
    parser.add_argument('--switch', action='store_true')
    parser.add_argument('--exercise-reset', action='store_true')
    parser.add_argument('--no-loop', action='store_true')
    parser.add_argument('--listen-seconds', type=float, default=1.2)
    parser.add_argument('--measurement', choices=['real','replay','synthetic'])
    parser.add_argument('--wav',type=Path,default=ROOT/'artifacts/input/browser.wav')
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
