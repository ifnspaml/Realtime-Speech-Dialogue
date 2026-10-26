# Contributing

The CPU-check workflow is manual; use it for relevant runtime changes.
Start with the README's CPU-only setup. Keep new UI work usable without loading
models. Use Node.js 22+ for the JavaScript checks and Python 3.11 for tools.

```bash
node --test tests/unit/*.test.mjs tests/protocol/*.test.mjs
.venv-tools/bin/python -m unittest discover -s tests/unit
.venv-tools/bin/python -m unittest discover -s tests/integration
.venv-tools/bin/python scripts/check_release.py
bash scripts/setup_browser.sh
bash scripts/prepare_test_audio.sh
bash scripts/run_browser_tests.sh
```

With PLAYWRIGHT_BROWSERS_PATH set to your installed Chromium directory, also run
tests/browser/presentation.py, tests/browser/demo_timer.py, and
`tests/browser/moshi.py --mock --switch --output artifacts/browser-moshi-mock`
using `.venv-tools/bin/python`. See docs/deployment.md for browser host libraries.

Do not commit .env files, credentials, personal paths, cluster hosts, operational
logs, user recordings, model weights or containers. Keep deployment examples
configurable and screenshots free of private data. Preview generation is
CPU-only and visibly synthetic; see assets/readme/README.md.

Preserve upstream notices and exact model revisions. Model/backend changes need
separate authorized inference validation. A mock/replay pass does not establish
real model correctness or performance. Do not trigger GPU jobs from CPU CI.

Describe behavior, validation and limitations in pull requests. Project-owned
contributions are provided under the repository's Apache-2.0 license; retain
separate third-party terms where applicable.

Import reviewed source changes selectively into a topic branch. Preserve notices
and model pins, and rerun privacy checks before committing. Keep private
development history and operational archives outside the publication repository.
