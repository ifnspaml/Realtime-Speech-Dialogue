"""Exercise real process teardown with synthetic model commands, without GPU."""
import tempfile
import time
import unittest
from pathlib import Path
from services.end_to_end import Supervisor, read_json, request_model


class SlotTests(unittest.TestCase):
    def test_replacement_idempotency_and_process_teardown(self):
        commands = {name: ['sleep', '120'] for name in ('moshi', 'nemotron')}
        with tempfile.TemporaryDirectory() as directory:
            slot = Supervisor(directory, commands, lambda: 10)
            first = request_model(directory, 'moshi')
            self.assertTrue(slot.replace(first))
            old = slot.process
            generation = slot.state['generation']
            self.assertFalse(slot.replace(request_model(directory, 'moshi')))
            self.assertIs(slot.process, old)
            self.assertEqual(slot.state['generation'], generation)
            self.assertTrue(slot.replace(request_model(directory, 'nemotron')))
            self.assertIsNotNone(old.poll())
            self.assertNotEqual(slot.process.pid, old.pid)
            slot.close()
            self.assertEqual(read_json(Path(directory) / 'state.json')['state'], 'UNLOADED')

    def test_invalid_model_cannot_start_process(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                request_model(directory, 'untrusted command')
            self.assertFalse((Path(directory) / 'request.json').exists())
