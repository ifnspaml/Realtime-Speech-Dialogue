"""Check real modular text-to-audio generation without microphone or GPU reload."""
import argparse
import asyncio
import base64
import json
import struct
import time
from pathlib import Path
import websockets

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='ws://127.0.0.1:7860/backend/modular')
parser.add_argument('--output', type=Path, default=Path('artifacts/modular-audio-check'))
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)

async def main():
    report = []
    async with websockets.connect(args.url, proxy=None, max_size=4_000_000) as ws:
        async def until(kind):
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), 45))
                if event['type'] == 'error':
                    raise RuntimeError(event)
                if event['type'] == kind:
                    return event
        await until('session.created')
        await ws.send(json.dumps({'type':'session.update','session':{'type':'realtime','instructions':'Repeat the requested sentence exactly. Preserve its punctuation. Do not add explanations.','tools':[],'audio':{'input':{'format':{'type':'audio/pcm','rate':24000}},'output':{'format':{'type':'audio/pcm','rate':24000}}}}}))
        await until('session.updated')
        for index, text in enumerate(['Hello. I am listening.', 'I’m listening—please go ahead.', 'It’s ready. What’s your question?', 'The answer is Berlin—Germany’s capital.']):
            await ws.send(json.dumps({'type':'response.create','response':{'input':[{'type':'message','role':'user','content':[{'type':'input_text','text':'Repeat exactly: '+text}]}]}}))
            audio = bytearray()
            assistant = ''
            events = []
            started = time.monotonic()
            while True:
                event=json.loads(await asyncio.wait_for(ws.recv(),45))
                events.append(event['type'])
                if event['type']=='error':
                    raise RuntimeError(event)
                if event['type']=='response.output_audio_transcript.delta':
                    assistant+=event.get('delta','')
                if event['type']=='response.output_audio.delta':
                    audio.extend(base64.b64decode(event['delta']))
                if event['type']=='response.done':
                    status=event['response']['status']
                    break
            samples=[x[0] for x in struct.iter_unpack('<h',audio)]
            row={'case':index,'requested_text':text,'assistant_text':assistant,'non_ascii_output':any(ord(c)>127 for c in assistant),'output_samples':len(samples),'nonzero_samples':sum(v!=0 for v in samples),'response_status':status,'elapsed_ms':(time.monotonic()-started)*1000,'event_types':events}
            report.append(row)
            (OUT/'text-probe.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
            print(json.dumps({k:v for k,v in row.items() if k!='event_types'},ensure_ascii=False),flush=True)
            assert samples and any(samples) and status=='completed',row
    assert any(row['non_ascii_output'] for row in report), 'No Unicode output exercised'
    print('PASS: Four real responses, including Unicode text, produced nonzero streaming PCM.')

asyncio.run(main())
