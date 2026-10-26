#!/usr/bin/env python3
"""Validate landscape UI, real browser audio worklets and transcript following.

Uses deterministic modular events and the native Moshi Opus mock/adapter.
No model quality or live model performance is inferred from this test.
"""
import asyncio
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aiohttp import web
from playwright.async_api import async_playwright
from scripts.run_demo import Handler
from services.moshi.adapter import create_app
from services.moshi.mock import create_app as native_mock
from tests.browser.validate import INSTRUMENT, diagnostic
from tests.browser.controls import ui_action

OUTPUT = ROOT / 'artifacts/presentation'


async def start(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    return runner, site._server.sockets[0].getsockname()[1]


async def dimensions(page):
    return await page.evaluate('''() => {
      const bounds = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}; };
      return { pageHeight:document.documentElement.scrollHeight, viewportHeight:innerHeight,
        pageWidth:document.documentElement.scrollWidth, viewportWidth:innerWidth,
        conversation:bounds('.conversation-card'), sidebar:bounds('.side-column'),
        controls:bounds('.controls'), breadcrumb:bounds('#architecture'),
        transcript:bounds('#messages'),
        textSize:parseFloat(getComputedStyle(document.querySelector('.message') || document.querySelector('.empty')).fontSize),
        logos:[...document.querySelectorAll('.brand img')].map(img=>({loaded:img.complete && img.naturalWidth>0,
          naturalRatio:img.naturalWidth/img.naturalHeight, displayRatio:img.getBoundingClientRect().width/img.getBoundingClientRect().height})),
        detailsHidden:!document.querySelector('#technical-details').open,
        futureText:document.body.innerText.includes('Future: Audio-Visual'),
        activeBottom:(document.querySelector('.message:last-child')?.getBoundingClientRect().bottom || 0)-document.querySelector('#messages').getBoundingClientRect().top };
    }''')


async def send_turn(page, index):
    before = await page.locator('.message.assistant').count()
    await page.evaluate('''index => window.__sockets.at(-1).send(JSON.stringify({type:'demo.mock_turn',
      transcript:`Question ${index}: how do these voice architectures differ?`, delayMs:0, jitterMs:0}))''', index)
    await page.wait_for_function('count => document.querySelectorAll(".message.assistant").length > count', arg=before)
    await page.wait_for_function("document.querySelector('.message.assistant:last-child p')?.textContent.endsWith('stages.')")
    await page.wait_for_timeout(480)


async def history_checks(page, report, mode):
    for index in range(12):
        await send_turn(page, index)
    if mode == 'modular':
        assert await page.locator('.message.user').count() == 12
        assert await page.locator('.message.assistant').count() == 12
    else:
        assert await page.locator('.message.user').count() == 0
    await page.wait_for_timeout(350)
    live = await dimensions(page)
    assert .69 <= live['activeBottom'] / live['transcript']['height'] <= .81, live
    # Manual wheel review must remain stable as real socket events arrive.
    await page.locator('#messages').hover()
    await page.mouse.wheel(0, -900)
    await page.wait_for_timeout(250)
    assert await page.locator('#latest-button').is_visible()
    top = await page.locator('#messages').evaluate('element => element.scrollTop')
    await send_turn(page, 99)
    await page.wait_for_timeout(250)
    after = await page.locator('#messages').evaluate('element => element.scrollTop')
    assert abs(after - top) <= 2, (top, after)
    await page.locator('#latest-button').click()
    await page.wait_for_timeout(600)
    assert not await page.locator('#latest-button').is_visible()
    latest = await dimensions(page)
    assert .69 <= latest['activeBottom'] / latest['transcript']['height'] <= .81, latest
    # Grow one existing response beyond a viewport, the continuous Moshi case.
    # Inject through the live socket callback to exercise the actual event renderer.
    await page.evaluate('''() => { window.__scrollTrace=[];
      document.querySelector('#messages').addEventListener('scroll',()=>window.__scrollTrace.push(document.querySelector('#messages').scrollTop)); }''')
    for _ in range(45):
        await page.evaluate('''() => window.__sockets.at(-1).onmessage({data:JSON.stringify({
          type:'response.output_audio_transcript.delta',delta:' Streamed caption keeps following the current response.'})})''')
        await page.wait_for_timeout(35)
    await page.wait_for_timeout(600)
    grown = await dimensions(page)
    assert .69 <= grown['activeBottom'] / grown['transcript']['height'] <= .81, grown
    assert grown['pageHeight'] <= grown['viewportHeight']
    trace = await page.evaluate('window.__scrollTrace')
    assert len(trace) > 10, trace
    steps = [abs(b-a) for a,b in zip(trace,trace[1:])]
    assert max(steps, default=0) < grown['transcript']['height']*.25, steps
    report.append({'mode':mode, 'live_position_fraction':live['activeBottom']/live['transcript']['height'],
      'manual_review':'PASS', 'resume':'PASS', 'long_stream':'PASS', 'scroll_events':len(trace), 'max_scroll_step_px':max(steps,default=0)})
    await page.locator('#messages').hover()
    await page.mouse.wheel(0, -500)
    await page.wait_for_timeout(200)
    await page.locator('#reset-button').click()
    assert await page.locator('.message').count() == 0
    assert not await page.locator('#latest-button').is_visible()
    await send_turn(page, 100)
    await page.wait_for_timeout(300)
    assert not await page.locator('#latest-button').is_visible()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {'measurement':'synthetic', 'status':'FAIL', 'layouts':[], 'history':[], 'checks':[]}
    runners = []
    runner, port = await start(native_mock()); runners.append(runner)
    runner, bridge = await start(create_app(f'ws://127.0.0.1:{port}/api/chat', measurement='synthetic')); runners.append(runner)
    os.environ['VOICE_DEMO_MOSHI_URL'] = f'ws://127.0.0.1:{bridge}/v1/realtime'
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    ui_port = server.server_address[1]
    os.environ['VOICE_DEMO_MODULAR_URL'] = f'ws://127.0.0.1:{ui_port}/mock'
    os.environ['VOICE_DEMO_NEMOTRON_URL'] = f'ws://127.0.0.1:{ui_port}/mock'
    os.environ.pop('VOICE_DEMO_SLOT_CONTROL', None)
    os.environ.pop('VOICE_DEMO_REPLAY', None)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    page = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox', '--use-fake-device-for-media-stream',
              '--use-fake-ui-for-media-stream', f'--use-file-for-fake-audio-capture={ROOT}/artifacts/input/browser.wav',
              '--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(viewport={'width':1920,'height':1080}, permissions=['microphone','camera'])
            await context.add_init_script(INSTRUMENT)
            page = await context.new_page()
            errors, replacements = [], []
            page.on('pageerror', lambda error: (errors.append(str(error)), print('Browser error:', error, flush=True)))
            page.on('request', lambda request: replacements.append(request.url) if request.method=='POST' and request.url.endswith('/api/model') else None)
            await page.goto(f'http://127.0.0.1:{ui_port}')
            await page.wait_for_function("document.querySelector('#status-text').textContent==='Ready'")
            assert not await page.locator('#end-to-end-model').is_visible()
            assert not await page.locator('.metrics-card').is_visible()
            await page.locator('#mic-button').click()
            await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>3")
            await page.wait_for_function('window.__audioObservation.peak > .002')
            await page.wait_for_function("document.querySelector('#live-state').textContent==='Listening + Speaking'")
            observed = await diagnostic(page)
            assert observed['inputChunksSent'] > 0 and observed['receivedOutputSeconds'] > 0
            assert await page.locator('.message.user').count() == 0
            await page.locator('#camera-button').click()
            await page.wait_for_function("document.querySelector('#camera').srcObject?.getVideoTracks().length===1")
            camera = await page.locator('#camera').evaluate('video => video.srcObject.getVideoTracks()[0].id')
            # A presentation Reset preserves both streams and never reloads a model.
            await page.locator('#reset-button').click()
            assert (await diagnostic(page))['captureActive']
            assert not await page.locator('#latest-button').is_visible()
            await page.locator('#mic-button').click()
            report['checks'].append('Moshi native mock: PCM upload, Opus bridge, assistant text, audible playback, no user transcript, concurrent activity')
            await page.locator('#details-button').click()
            assert await page.locator('.metrics-card').is_visible()
            await page.keyboard.press('Escape')
            assert not await page.locator('#technical-details').evaluate('dialog=>dialog.open')
            report['checks'].append('Details is collapsed by default, exposes timing/debug controls, closes with Escape')
            await ui_action(page, '.mode[data-mode=modular]')
            await page.wait_for_function("document.querySelector('#status-text').textContent==='Ready'")
            await page.locator('#mic-button').click()
            await page.wait_for_function("document.querySelector('.message.user p')?.textContent.length>3")
            await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>3")
            await page.locator('#mic-button').click()
            assert (await diagnostic(page))['inputChunksSent'] > 0
            report['checks'].append('Modular mock: fake WAV microphone, user and assistant transcript, browser playback')
            for mode in ['modular', 'moshi']:
                await ui_action(page, f'.mode[data-mode={"modular" if mode=="modular" else "nemotron"}]')
                await page.wait_for_function("document.querySelector('#status-text').textContent==='Ready'")
                assert await page.locator('#camera').evaluate('v=>v.srcObject.getVideoTracks()[0].id') == camera
                if not await page.locator('.settings-card').evaluate('d=>d.open'):
                    await ui_action(page, '.settings-card > summary')
                await ui_action(page, '#mock-button')
                await page.wait_for_function("document.querySelector('.message.assistant p')?.textContent.length>100")
                await page.wait_for_timeout(500)
                await ui_action(page, '#reset-button')
                await history_checks(page, report['history'], mode)
                for width,height in [(1920,1080),(2560,1440),(3840,2160)]:
                    await page.set_viewport_size({'width':width,'height':height})
                    await page.wait_for_timeout(600)
                    layout = await dimensions(page)
                    assert layout['pageHeight'] <= height and layout['pageWidth'] <= width, layout
                    assert layout['controls']['bottom'] <= height, layout
                    fraction = layout['conversation']['width']/(layout['conversation']['width']+layout['sidebar']['width'])
                    assert .78 <= fraction <= .82, fraction
                    assert layout['breadcrumb']['height'] <= height*.065
                    assert all(logo['loaded'] and abs(logo['naturalRatio']-logo['displayRatio'])<.03 for logo in layout['logos']), layout
                    assert not layout['futureText'] and layout['detailsHidden']
                    assert await page.locator('.message.user').count() == (1 if mode=='modular' else 0)
                    name=f'{mode}-{width}x{height}.png'
                    await page.screenshot(path=str(OUTPUT/name))
                    report['layouts'].append({'mode':mode, 'resolution':f'{width}x{height}', 'conversation_fraction':fraction, 'screenshot':name, **layout})
            # Switching a fresh session restores live following even from manual review.
            await page.locator('#messages').hover(); await page.mouse.wheel(0,-500)
            await ui_action(page, '.mode[data-mode=modular]')
            assert not await page.locator('#latest-button').is_visible()
            assert await page.locator('.message').count() == 0
            await page.locator('#camera-button').click()
            await page.wait_for_function("!document.querySelector('#camera').srcObject")
            assert await page.locator('#camera-off').is_visible()
            report['checks'].append('Switch/reset restores follow; camera persists across sessions and disables cleanly; no model-load POST')
            await page.goto(f'http://127.0.0.1:{ui_port}/?display=tv')
            await page.wait_for_function("document.querySelector('#status-text').textContent==='Ready'")
            assert await page.locator('body').evaluate('body=>body.classList.contains("tv")')
            for width,height in [(1920,1080),(2560,1440),(3840,2160)]:
                await page.set_viewport_size({'width':width,'height':height})
                await page.wait_for_timeout(200)
                layout=await dimensions(page)
                assert layout['pageHeight']<=height and layout['controls']['bottom']<=height, layout
            report['checks'].append('TV query modifier fits all three resolutions without separate UI')
            assert not errors, errors
            assert not replacements, replacements
            report['checks'].append('No JavaScript errors or model replacement requests')
            report['status']='PASS'
            await browser.close()
    except Exception as error:
        report['error']=repr(error)
        if page:
            try: await page.screenshot(path=str(OUTPUT/'failure.png'))
            except Exception: pass
        raise
    finally:
        (OUTPUT/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        server.shutdown(); server.server_close()
        for runner in reversed(runners): await runner.cleanup()
    print(json.dumps(report, indent=2))


if __name__=='__main__': asyncio.run(main())
