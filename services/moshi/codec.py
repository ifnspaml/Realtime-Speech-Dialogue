"""Stateful 24 kHz PCM16 / streaming Opus conversion, without model imports."""
import numpy as np
import sphn

RATE = 24000
# Mimi consumes 80 ms frames; browser JSON chunk boundaries need not align.
FRAME = 1920


class Codec:
    """Retain Opus history and partial PCM across messages within one session."""
    def __init__(self):
        self.writer = sphn.OpusStreamWriter(RATE)
        self.reader = sphn.OpusStreamReader(RATE)
        self.pending = b''

    def encode(self, pcm):
        """Consume little-endian PCM16 and return native kind-1 audio packets."""
        if len(pcm) % 2:
            raise ValueError('PCM16 requires complete samples')
        if len(pcm) > RATE * 2:
            raise ValueError('Input chunk exceeds one second')
        self.pending += pcm
        result = []
        while len(self.pending) >= FRAME * 2:
            raw, self.pending = self.pending[:FRAME * 2], self.pending[FRAME * 2:]
            samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
            packet = self.writer.append_pcm(samples)
            if packet:
                result.append(b'\x01' + packet)
        return result

    def decode(self, packet):
        """Return newly decoded PCM only; incomplete Opus input can yield no PCM."""
        if not packet or packet[0] != 1:
            raise ValueError('Expected a native audio frame')
        if len(packet) > 1024 * 1024:
            raise ValueError('Native audio packet is oversized')
        if len(packet) == 1:
            return b''
        samples = self.reader.append_bytes(packet[1:])
        if samples.size > RATE * 30:
            raise ValueError('Decoded audio exceeds queue bound')
        # Saturate both extrema before casting to avoid int16 wraparound.
        return np.clip(np.rint(samples * 32768), -32768, 32767).astype('<i2').tobytes()
