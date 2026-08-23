# Portway

[![CI](https://github.com/portway-app/portway/actions/workflows/ci.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/ci.yml)
[![Pages](https://github.com/portway-app/portway/actions/workflows/pages.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/pages.yml)
[![Release](https://github.com/portway-app/portway/actions/workflows/release.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/release.yml)

Find open ports on this machine, the Wi-Fi subnet, and Tailscale, then open the ones that speak HTTP.

Portway now ships four faces of the same scanner:

- **GUI** — [HeroUI](https://heroui.com/) React deck inside pywebview
- **Flask** — local API plus the same GUI at `http://0.0.0.0:5050`
- **TUI** — Textual listing of every discovered IP
- **CLI** — Rich color listing of every IP, optional scan

Icons are from [Lucide](https://lucide.dev/icons/).

## Why it exists

You start a Flask app, a Vite preview, Jupyter, or a NAS UI, then forget the port. Portway sweeps what you are already attached to and turns listening sockets into doors.

It will not scan the public internet. Host discovery is capped at a /24. An all-port sweep (1-65535) only runs against a single host you choose.

## Features

- **This machine, Wi-Fi, Tailscale.** Interfaces are classified automatically. Tailscale peers come from `tailscale status --json` when the CLI is installed.
- **HeroUI React GUI.** Buttons, cards, chips, switches, and a token modal from [HeroUI v3](https://heroui.com/).
- **Protected IPs.** Jupyter and 401/403 services prompt for a token. Tokens stay in `~/.config/portway/tokens.json` and are never listed in full.
- **Profiles.** Quick, Developer, and All ports on one host.
- **Open or copy.** HTTP(S) services open in the browser, with `?token=` attached when you saved one.
- **CLI colors.** `portway list` prints every IP in pier colors: gold, cyan, green, magenta.
- **TUI.** `portway tui` is a keyboard listing. `t` saves a token, `s` scans, `o` opens.

## Install

Python 3.10 or newer.

```bash
git clone https://github.com/portway-app/portway
cd portway
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
portway
```

Optional GUI rebuild (from the **repository root**, not a random folder):

```bash
npm run build
```

That installs `gui/` dependencies if needed and writes the HeroUI bundle to `portway/web/`. Same thing, spelled out:

```bash
cd gui
npm install
npm run build
```

Tailscale is optional. Without the CLI, the Tailscale pier still appears if an interface has a `100.64.0.0/10` address.

## Usage

```bash
portway                          # HeroUI desktop window (Flask + pywebview)
portway gui
portway serve --bind 0.0.0.0 --port 5050
portway tui                      # terminal listing
portway list                     # colored IPs
portway list --scan --profile quick
portway scan --host 127.0.0.1 --profile deep
portway list --token 127.0.0.1:8888=YOUR_TOKEN
portway --cli                    # still works; alias for scan
```

Token styles:

- `query` — `?token=` (Jupyter default)
- `bearer` — `Authorization: Bearer ...`
- `header` — raw Authorization header

## How scanning works

1. Enumerate IPv4 interfaces (`ip`, `ifconfig`, or `ipconfig`).
2. Skip virtual bridges (Docker, `veth`, Hyper-V).
3. Build a host list: self, default gateway, ARP neighbors, Tailscale peers, and the rest of a /24.
4. TCP `connect` with a short timeout, in a thread pool.
5. Optional HTTP probe. No payloads, no authentication attacks, no exploit code.

The landing page lives in [`website/`](website/index.html).

## Project layout

```
portway/            Python package (scanner, Flask, TUI, CLI)
portway/web/        Built HeroUI GUI
gui/                HeroUI + Vite + React source
website/            Marketing page for GitHub Pages
tests/              Unit tests, no live network required
.github/workflows/  CI, Release, Pages
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check portway tests
cd gui && npm install && npm run dev
```

`npm run dev` expects `portway serve` on port 5050 so `/api` can proxy.

## License

MIT. See [LICENSE](LICENSE).

Lucide icons are ISC-licensed by the Lucide contributors. HeroUI is Apache-2.0.
