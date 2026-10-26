# Presentation assets

The hero, capability badges and project mark are original project artwork under
Apache-2.0. The cover and UI previews also include the original supplied TU
Braunschweig seal and IfN logo, restored at the maintainer’s request for this
private repository. Those institutional marks retain separate rights; see
[branding provenance](../branding/README.md) before public redistribution.

The UI preview and static screenshot are generated from this publication copy's
actual frontend using controlled synthetic text/tones and fake microphone input.
They are labeled SIMULATION, contain no personal speech or camera data, and
carry no real model inference or performance claim. The animation is silent.

Regenerate after installing the tools/browser prerequisites and test audio:

```bash
bash scripts/prepare_test_audio.sh
.venv-tools/bin/python scripts/generate_artwork.py
.venv-tools/bin/python scripts/capture_preview.py
```

Set PLAYWRIGHT_BROWSERS_PATH to the installed browser directory and, when needed,
LD_LIBRARY_PATH to a compatible local host-library tree. Generated intermediate
frames/logs stay in ignored artifacts/. Reviewed presentation PNG/GIF/SVG files
are versioned here; each must remain under the publication asset size limit.
