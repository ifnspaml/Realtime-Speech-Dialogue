import asyncio
import base64
import json
import unittest
import numpy as np
from aiohttp import ClientSession, web
from services.moshi.adapter import create_app
from services.moshi.mock import create_app as create_mock
from services.moshi.codec import FRAME, RATE


class MoshiAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock = create_mock()
        self.runners = []
        self.native = await self.start(self.mock)
        self.adapter = await self.start(create_app('ws://127.0.0.1:%d/api/chat' % self.native, measurement='synthetic'))

    async def start(self, app):
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        self.runners.append(runner)
        return site._server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        for runner in reversed(self.runners): await runner.cleanup()

    async def test_native_preroll_pcm_text_and_session_close(self):
        async with ClientSession() as client:
            async with client.ws_connect('http://127.0.0.1:%d/v1/realtime' % self.adapter) as ws:
                self.assertEqual((await ws.receive_json())['type'], 'session.created')
                await ws.send_json({'type':'session.update','session':{}})
                samples = (4000 * np.sin(2 * np.pi * 440 * np.arange(FRAME) / RATE)).astype('<i2').tobytes()
                for _ in range(4): await ws.send_json({'type':'input_audio_buffer.append','audio':base64.b64encode(samples).decode()})
                events = []
                while not any(event['type']=='response.output_audio_transcript.delta' for event in events):
                    events.append(await asyncio.wait_for(ws.receive_json(),3))
                self.assertIn('Café', events[-1]['delta'])
                self.assertFalse(any(event['type'].startswith('conversation.item.input') for event in events))
                self.assertLess(float(np.max(np.abs(self.mock['input_chunks'][0]))),0.005)
                self.assertGreater(float(np.max(np.abs(self.mock['input_chunks'][1]))),0.05)
                await ws.send_json({'type':'session.close'})
                while True:
                    event = await asyncio.wait_for(ws.receive_json(),3)
                    if event['type']=='session.end': break
                self.assertEqual(event['origin'],'moshi_adapter')

    async def test_instructions_are_not_silently_applied(self):
        async with ClientSession() as client:
            async with client.ws_connect('http://127.0.0.1:%d/v1/realtime' % self.adapter) as ws:
                await ws.receive_json()
                await ws.send_json({'type':'session.update','session':{'instructions':'Unsupported'}})
                while True:
                    event=await asyncio.wait_for(ws.receive_json(),3)
                    if event['type']=='error': break
                self.assertEqual(event['error']['code'],'unsupported_configuration')

    async def test_busy_session_rejected_and_reconnect(self):
        async with ClientSession() as client:
            url = 'http://127.0.0.1:%d/v1/realtime' % self.adapter
            async with client.ws_connect(url) as first:
                await first.receive_json()
                async with client.ws_connect(url) as second:
                    failure = await second.receive_json()
                    self.assertEqual(failure['error']['code'], 'session_limit_reached')
                await first.send_json({'type': 'session.close'})
                while (await first.receive_json())['type'] != 'session.end': pass
            async with client.ws_connect(url) as third:
                self.assertEqual((await third.receive_json())['type'], 'session.created')

    async def test_delay_jitter_malformed_disconnect_and_handshake_stall(self):
        cases = [('delay=%s&jitter=%s' % (delay, jitter), False)
                 for delay in (0, .05, .1, .2) for jitter in (0, .02, .05)]
        cases += [('malformed=1', True), ('disconnect=1', False), ('handshake=stall', True)]
        async with ClientSession() as client:
            for query, expect_error in cases:
                with self.subTest(query=query):
                    app = create_app('ws://127.0.0.1:%d/api/chat?%s' % (self.native, query), measurement='synthetic')
                    adapter = await self.start(app)
                    async with client.ws_connect('http://127.0.0.1:%d/v1/realtime' % adapter) as ws:
                        first = await asyncio.wait_for(ws.receive_json(), 7)
                        events = [first]
                        if first['type'] == 'session.created':
                            tone = np.full(FRAME, 3000, dtype='<i2').tobytes()
                            for _ in range(5):
                                await ws.send_json({'type':'input_audio_buffer.append','audio':base64.b64encode(tone).decode()})
                            while True:
                                value = await asyncio.wait_for(ws.receive_json(), 5)
                                events.append(value)
                                if value['type'] in ('error', 'session.end'): break
                                if value['type'] == 'response.output_audio_transcript.delta' and 'disconnect' not in query:
                                    await ws.send_json({'type':'session.close'})
                        self.assertEqual(any(e['type']=='error' for e in events), expect_error)


if __name__ == '__main__': unittest.main()
