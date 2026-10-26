"""Minimal PCM/JSON bridge to the unmodified Moshi binary Opus server."""
import argparse
import asyncio
import base64
import json
import socket
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web
from services.moshi.codec import Codec, FRAME, RATE


def event(kind, **fields):
    return {'type': kind, 'event_id': str(uuid.uuid4()), 'origin': 'moshi_adapter', **fields}


async def chat(request):
    """Bridge one browser session using one persistent native Opus codec pair."""
    app = request.app
    ws = web.WebSocketResponse(max_msg_size=192000, heartbeat=20)
    await ws.prepare(request)
    if app['busy']:
        await ws.send_json(event('error', error={'code': 'session_limit_reached', 'message': 'Moshi is busy'}))
        await ws.close()
        return ws
    # The official native model has one session slot; reject overlap explicitly.
    app['busy'] = True
    stats = {'input_samples': 0, 'output_samples': 0, 'codec_ms': 0.0, 'preroll_samples': FRAME}
    session_id, response_id = str(uuid.uuid4()), str(uuid.uuid4())
    # Bound undelivered events; a stalled browser eventually closes the bridge.
    queue = asyncio.Queue(maxsize=100)
    tasks = []
    try:
        async with ClientSession(timeout=ClientTimeout(total=None, sock_connect=5)) as client:
            async with client.ws_connect(app['native_url'], max_msg_size=1024 * 1024, heartbeat=20) as native:
                handshake = await asyncio.wait_for(native.receive(), timeout=5)
                if handshake.type != WSMsgType.BINARY or handshake.data != b'\x00':
                    raise ValueError('Invalid native handshake or busy model')
                codec = Codec()
                # The official server resets its first encoded frame. Sacrifice
                # silent preroll instead of the beginning of the user's question.
                for packet in codec.encode(bytes(FRAME * 2)):
                    await native.send_bytes(packet)
                await ws.send_json(event('session.created', session={'id': session_id, 'model': 'moshi', 'measurement': app['measurement'], 'capabilities': {'user_transcript': False, 'speech_boundaries': False, 'response_scope': 'session'}}))
                # Moshi is continuous: this response spans the transport session.
                # No user transcript, VAD boundary or per-turn done is fabricated.
                await ws.send_json(event('response.created', response={'id': response_id, 'status': 'in_progress', 'scope': 'session'}))

                async def upload():
                    async for message in ws:
                        if message.type != WSMsgType.TEXT:
                            if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR): break
                            raise ValueError('Only JSON text input is supported')
                        data = json.loads(message.data)
                        kind = data.get('type')
                        if kind == 'session.update':
                            configuration = data.get('session', {})
                            if configuration.get('instructions') or configuration.get('tools'):
                                await queue.put(event('error', error={'code': 'unsupported_configuration', 'message': 'Moshi does not support instructions or tools'}))
                                continue
                            for direction in ('input', 'output'):
                                audio_format = configuration.get('audio', {}).get(direction, {}).get('format', {})
                                if audio_format and audio_format != {'type': 'audio/pcm', 'rate': RATE}:
                                    raise ValueError('Moshi bridge requires PCM16 at 24 kHz')
                            await queue.put(event('session.updated', session={'id': session_id, 'scope': 'transport', 'model': 'moshi'}))
                        elif kind == 'input_audio_buffer.append':
                            raw = base64.b64decode(data['audio'], validate=True)
                            started = time.perf_counter()
                            packets = codec.encode(raw)
                            stats['codec_ms'] += (time.perf_counter() - started) * 1000
                            stats['input_samples'] += len(raw) // 2
                            for packet in packets: await native.send_bytes(packet)
                        elif kind == 'session.close':
                            break
                        else:
                            await queue.put(event('error', error={'code': 'unsupported_event', 'message': 'Unsupported Moshi control: ' + str(kind)}))

                async def download():
                    async for message in native:
                        if message.type != WSMsgType.BINARY:
                            if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR): break
                            raise ValueError('Unexpected native message')
                        packet = message.data
                        if not packet: raise ValueError('Empty native frame')
                        if packet[0] == 1:
                            # Native kind 1 is Opus; kind 2 below is UTF-8 text.
                            started = time.perf_counter()
                            raw = codec.decode(packet)
                            stats['codec_ms'] += (time.perf_counter() - started) * 1000
                            stats['output_samples'] += len(raw) // 2
                            if raw: await asyncio.wait_for(queue.put(event('response.output_audio.delta', response_id=response_id, delta=base64.b64encode(raw).decode())), timeout=5)
                        elif packet[0] == 2:
                            text = packet[1:].decode('utf-8')
                            if text: await asyncio.wait_for(queue.put(event('response.output_audio_transcript.delta', response_id=response_id, delta=text)), timeout=5)
                        else: raise ValueError('Unknown native frame kind')

                async def deliver():
                    while True:
                        await asyncio.wait_for(ws.send_json(await queue.get()), timeout=5)

                tasks = [asyncio.create_task(function()) for function in (upload, download, deliver)]
                # Ending either transport tears down all three tasks together.
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
    except Exception as error:
        # Native context cleanup precedes this notification. A handshake timeout
        # does not include the time required to negotiate/finish socket closure.
        if not ws.closed:
            await ws.send_json(event('error', error={'code': 'moshi_bridge_error', 'message': str(error)}))
    finally:
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        # Completed-session counters include silence and exclude input preroll.
        # They are overwritten even by an empty session, and are not live input
        # acknowledgements or a recording of the user's spoken content.
        app['last_stats'] = stats
        app['busy'] = False
        if not ws.closed:
            # This is transport completion, not an invented model turn boundary.
            await ws.send_json(event('session.end', session_id=session_id, stats=stats, reason='transport_closed'))
            await ws.close()
    return ws


async def health(request):
    """Combine port availability with prerecorded inference-validation evidence."""
    app = request.app
    parsed = urlsplit(app['native_url'])
    native_up = False
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=0.3): native_up = True
    except OSError: pass
    # A listening port alone cannot certify that model inference is usable.
    validated = app['measurement'] == 'synthetic'
    if app['ready_file']:
        try: validated = json.loads(Path(app['ready_file']).read_text()).get('status') == 'PASS'
        except (OSError, ValueError): validated = False
    ready = native_up and validated
    return web.json_response({'status': 'ok' if ready else 'starting', 'model': 'moshi', 'native_available': native_up,
                              'inference_validated': validated, 'measurement': app['measurement'], 'busy': app['busy'], 'last_stats': app['last_stats']})


def create_app(native_url, ready_file=None, measurement='real'):
    app = web.Application()
    app.update(native_url=native_url, ready_file=ready_file, measurement=measurement, busy=False, last_stats={})
    app.router.add_get('/v1/realtime', chat)
    app.router.add_get('/health', health)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-url', default='ws://127.0.0.1:8998/api/chat')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9005)
    parser.add_argument('--ready-file')
    parser.add_argument('--synthetic', action='store_true')
    args = parser.parse_args()
    web.run_app(create_app(args.native_url, args.ready_file, 'synthetic' if args.synthetic else 'real'), host=args.host, port=args.port)


if __name__ == '__main__': main()
