# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-23

### Added

- Initial public release of Portway.
- pywebview desktop shell with a three-pier layout: this machine, Wi-Fi / LAN, and Tailscale.
- TCP connect scanner with Quick, Developer, and All-ports profiles.
- HTTP fingerprinting for titles and `Server` headers so Flask, Vite, and similar apps are labeled.
- One-click Open for HTTP(S) services and Copy for everything else.
- Tailscale peer discovery through `tailscale status --json`.
- CLI mode: `portway --cli`, including `--json` and single-host deep scans.
- Local-only guardrails: public ranges refused, host discovery capped at /24, all-port sweeps limited to one host.
- Marketing site in `website/` using Lucide icons.
- GitHub Actions workflows for CI, tagged releases, and GitHub Pages.

[Unreleased]: https://github.com/portway-app/portway/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/portway-app/portway/releases/tag/v0.1.0
