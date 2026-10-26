"""Validate opt-in operator API input and same-origin checks without models."""
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from scripts.run_demo import Handler
from services.end_to_end import atomic_json, read_json


class OperatorTests(unittest.TestCase):
    def test_operator_control_is_explicit_and_rejects_cross_origin(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'VOICE_DEMO_SLOT_CONTROL':'1', 'VOICE_DEMO_SLOT_DIRECTORY':directory}):
            atomic_json(Path(directory)/'state.json', {'state':'READY','model':'moshi','updated_at':time.time()})
            server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f'http://127.0.0.1:{server.server_address[1]}'
            def post(model, origin):
                request = urllib.request.Request(url+'/api/model', data=json.dumps({'model':model}).encode(),
                    headers={'Content-Type':'application/json','Origin':origin}, method='POST')
                return urllib.request.urlopen(request)
            try:
                with urllib.request.urlopen(url+'/api/config') as response:
                    self.assertEqual(json.load(response)['defaultEndToEndModel'],'moshi')
                atomic_json(Path(directory)/'state.json', {'state':'READY','model':'nemotron','updated_at':time.time()})
                with urllib.request.urlopen(url+'/api/config') as response:
                    self.assertEqual(json.load(response)['defaultEndToEndModel'],'nemotron')
                self.assertFalse((Path(directory)/'request.json').exists(), 'Reading configuration must not replace a resident model')
                with post('nemotron',url) as response:
                    self.assertEqual(response.status,202)
                    accepted=json.load(response)
                self.assertEqual(read_json(Path(directory)/'request.json'),accepted)
                for model, origin, expected in [('moshi','http://untrusted.example',403), ('other',url,400)]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        post(model,origin)
                    self.assertEqual(error.exception.code,expected)
                os.environ['VOICE_DEMO_SLOT_CONTROL']='0'
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post('moshi',url)
                self.assertEqual(error.exception.code,404)
            finally:
                server.shutdown();server.server_close()
