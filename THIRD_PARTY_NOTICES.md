# Attribution and third-party terms

Project-owned integration code derives from the reviewed Speech Dialogue Demo
release. Original authorship is retained in NOTICE; source identifiers are in
PROVENANCE.md. A fresh publication history does not imply new ownership.

- Adapted Hugging Face browser worklets and PCM helpers: speech-to-speech commit
  `81b688b452ee6b64ff5745b91985e9eb653fcc9f`, Apache-2.0. The full license and
  local modification notice are in `frontend/vendor/hf-demo/`.
- Separately cloned Hugging Face speech-to-speech backend: Apache-2.0; retain
  its LICENSE and dependency notices in the frozen upstream checkout.
- Kyutai Moshi Python/web client code: MIT; Rust backend: Apache-2.0. Moshiko/Mimi model artifacts
  in the pinned repository: CC-BY-4.0. Code and model terms are distinct.
- NVIDIA Parakeet v3 weights: CC-BY-4.0. Qwen3/Qwen3-TTS weights: Apache-2.0.
  Serveurperso GGUF conversion: Apache-2.0 attribution remains relevant in
  addition to original Qwen model provenance.
- Silero VAD source/model: MIT. Smart Turn endpointing: BSD-2-Clause.
- NLTK punkt_tab data: retain package/upstream data terms when downloaded;
  the archive is outside Git and pinned in `config/models.json`.
- Optional NVIDIA Nemotron VoiceChat model and official container: NVIDIA's
  applicable model/container licenses, access and runtime requirements apply.
  Nothing here grants rights to redistribute them; no artifacts are vendored.

The exact model revisions, hashes and upstream links are in `docs/models.md`
and `config/models.json`. Python packages retain their distributions' licenses;
installation does not relicense them. Locally synthesized test tones/events
contain no speaker recordings; generated espeak inputs stay outside Git.

Project-owned publication code and new project artwork use Apache-2.0 as authorized by the project maintainer. The original TU Braunschweig seal and IfN logo retain separate institutional rights; Apache-2.0 does not relicense them. They are included in this private repository at the maintainer’s request. See assets/branding/README.md for provenance and public-distribution clearance.
