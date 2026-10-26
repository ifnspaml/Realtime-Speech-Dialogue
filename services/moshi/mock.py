"""Native Moshi binary-protocol simulation; tone/text are explicitly synthetic."""
import argparse
import asyncio
import numpy as np
import sphn
from aiohttp import WSMsgType, web
from services.moshi.codec import FRAME, RATE


async def chat(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    delay = float(request.query.get('delay', '0'))
    jitter = float(request.query.get('jitter', '0'))
    if request.query.get('handshake') == 'stall': await asyncio.sleep(6)
    await ws.send_bytes(b'\x00')
    reader, writer = sphn.OpusStreamReader(RATE), sphn.OpusStreamWriter(RATE)
    chunks = 0
    async for message in ws:
        if message.type != WSMsgType.BINARY: break
        if not message.data or message.data[0] != 1: break
        pcm = reader.append_bytes(message.data[1:])
        if not pcm.size: continue
        request.app['input_chunks'].append(pcm.copy())
        chunks += 1
        await asyncio.sleep(delay + (jitter if chunks % 2 else 0))
        if request.query.get('malformed') == '1':
            await ws.send_bytes(b'\x09invalid'); break
        if chunks == 2: await ws.send_bytes(b'\x02Synthetic Moshi reply. Caf\xc3\xa9.')
        tone = (0.1 * np.sin(2 * np.pi * 440 * (np.arange(FRAME) + chunks * FRAME) / RATE)).astype(np.float32)
        packet = writer.append_pcm(tone)
        if packet: await ws.send_bytes(b'\x01' + packet)
        if request.query.get('disconnect') == '1' and chunks >= 3: break
    await ws.close()
    return ws


def create_app():
    app = web.Application()
    app['input_chunks'] = []
    app.router.add_get('/api/chat', chat)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8999)
    args = parser.parse_args()
    web.run_app(create_app(), host='127.0.0.1', port=args.port)
