The worklets/ and ws/codec.js files derive from huggingface/speech-to-speech,
commit 81b688b452ee6b64ff5745b91985e9eb653fcc9f, directory demo/.
Upstream is licensed under Apache-2.0; the full license is retained in LICENSE.
Upstream source: https://github.com/huggingface/speech-to-speech/tree/81b688b452ee6b64ff5745b91985e9eb653fcc9f/demo

Local playback modifications bound the queue (eight-second default, configured
by this UI to a hard-capped thirty seconds), report overflow and peak queue
samples, retire consumed diagnostic counters, and report first rendered nonzero
samples with turn markers. Resampling and playback interpolation remain upstream
code. The capture worklet and PCM codec retain upstream behavior. These changes
support transport diagnostics and do not alter model inference.
