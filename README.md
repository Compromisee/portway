# Portway

[![CI](https://github.com/portway-app/portway/actions/workflows/ci.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/ci.yml)
[![Pages](https://github.com/portway-app/portway/actions/workflows/pages.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/pages.yml)
[![Release](https://github.com/portway-app/portway/actions/workflows/release.yml/badge.svg)](https://github.com/portway-app/portway/actions/workflows/release.yml)

Find open ports on this machine, the Wi-Fi subnet, and Tailscale, then open the ones that speak HTTP.

Portway is a local [pywebview](https://pywebview.flowrl.com/) desktop app. It charts three piers — loopback, LAN, and the Tailscale mesh — runs a TCP connect scan, fingerprints Flask and other web services, and gives you an Open button.

Icons throughout the app and landing page are from [Lucide](https://lucide.dev/icons/).

## Why it exists

You start a Flask app, a Vite preview, Jupyter, or a NAS UI, then forget the port. Portway sweeps what you are already attached to and turns listening sockets into doors.

It will not scan the public internet. Host discovery is capped at a /24. An all-port sweep (1-65535) only runs against a single host you choose.

## Features

- **This machine, Wi-Fi, Tailscale.** Interfaces are classified automatically. Tailscale peers come from `tailscale status --json` when the CLI is installed.
- **Profiles.** Quick (SSH + common web), Developer (the catalog: Flask, Vite, Django, databases, remote access), and All ports on one host.
- **Open or copy.** HTTP(S) services open in the default browser. Everything else copies as `host:port`.
- **Fingerprints.** A tiny HTTP GET reads `Server` and `<title>` so Werkzeug looks like Flask, not "unknown".
- **CLI.** `portway --cli` prints the same sweep without a window.

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

Desktop window requirements:

| Platform | WebView |
| --- | --- |
| Windows | Edge WebView2 (usually already present) |
| macOS | Cocoa / WKWebView |
| Linux | GTK + WebKit2, or Qt |

On Debian/Ubuntu:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1
```

Tailscale is optional. Without the CLI, the Tailscale pier still appears if an interface has a `100.64.0.0/10` address, but peer names will be missing.

## Usage

```bash
portway                          # desktop window
portway --cli                    # terminal sweep, developer ports
portway --cli --profile quick
portway --cli --host 127.0.0.1 --profile deep
portway --cli --networks local wifi
portway --cli --json
```

In the window:

- **Scan** runs the selected profile against this machine, Wi-Fi, and Tailscale.
- **All ports** on a host row walks 1-65535 on that host only.
- **Open** launches HTTP(S) in the browser.
- **Copy** puts the URL or `host:port` on the clipboard.
- `/` focuses the filter. `R` starts or stops a scan.

## How scanning works

1. Enumerate IPv4 interfaces (`ip`, `ifconfig`, or `ipconfig`).
2. Skip virtual bridges (Docker, `veth`, Hyper-V).
3. Build a host list: self, default gateway, ARP neighbors, Tailscale peers, and the rest of a /24.
4. TCP `connect` with a short timeout, in a thread pool.
5. Optional HTTP probe. No payloads, no authentication attacks, no exploit code.

The landing page lives in [`website/`](website/index.html) and is published by the Pages workflow.

## Project layout

```
portway/            Python package and desktop UI
portway/web/        pywebview frontend (Lucide icons inlined)
website/            Marketing page for GitHub Pages
tests/              Unit tests, no live network required
.github/workflows/  CI, Release, Pages
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check portway tests
```

## License

MIT. See [LICENSE](LICENSE).

Lucide icons are ISC-licensed by the Lucide contributors.
