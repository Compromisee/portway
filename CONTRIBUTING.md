# Contributing to Portway

Thank you for helping keep the harbor chart accurate.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check portway tests
```

The desktop UI lives in `portway/web/`. Lucide SVG paths are inlined in `portway/web/icons.js` so the window works offline. Prefer those icons over new image assets. Do not add emoji.

## What belongs here

Portway is a **local discovery** tool. Changes should stay inside:

- loopback
- the attached Wi-Fi / Ethernet /24
- Tailscale peers reported by the local CLI

Do not add support for scanning arbitrary public ranges, writing exploit payloads, or brute-forcing services.

## Pull requests

1. Add or update tests for pure helpers (parsers, catalogs, URL builders).
2. Avoid live scans in CI. Mock command output and sockets.
3. Update `CHANGELOG.md` under **Unreleased**.
4. Keep the tone of the UI: serif wordmark, Lucide icons, no emoji.

## Release

Tags matching `v*` start the Release workflow, which builds PyInstaller artifacts per OS and publishes a GitHub Release.
