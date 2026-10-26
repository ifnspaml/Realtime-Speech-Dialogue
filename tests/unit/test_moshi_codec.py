import unittest
import numpy as np
from services.moshi.codec import Codec, FRAME, RATE


class MoshiCodecTests(unittest.TestCase):
    def test_incremental_frames_and_reconnect_reset(self):
        codec = Codec()
        samples = (4000 * np.sin(2 * np.pi * 440 * np.arange(FRAME * 5) / RATE)).astype('<i2').tobytes()
        packets = []
        for offset in range(0, len(samples), FRAME): packets += codec.encode(samples[offset:offset + FRAME])
        decoded = b''.join(codec.decode(packet) for packet in packets)
        self.assertEqual(len(decoded), len(samples))
        self.assertGreater(np.max(np.abs(np.frombuffer(decoded, dtype='<i2'))), 1000)
        self.assertEqual(codec.pending, b'')
        reset = Codec()
        self.assertTrue(reset.encode(bytes(FRAME * 2)))

    def test_fragmented_headers_and_input_limits(self):
        encoder, decoder = Codec(), Codec()
        packet = encoder.encode(bytes(FRAME * 2))[0]
        decoded = decoder.decode(b'\x01' + packet[1:20]) + decoder.decode(b'\x01' + packet[20:])
        self.assertEqual(len(decoded), FRAME * 2)
        for raw in (b'x', bytes(RATE * 2 + 2)):
            with self.assertRaises(ValueError): encoder.encode(raw)
        with self.assertRaises(ValueError): decoder.decode(b'\x02text')


if __name__ == '__main__': unittest.main()
