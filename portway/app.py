"""Desktop window and CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from portway import __version__
from portway.api import Bridge
from portway.discovery import collect_targets
from portway.scanner import scan_targets
from portway.services import ports_for_profile


def _web_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "portway" / "web"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent / "web"


WEB_DIR = _web_dir()


def _print_cli(result: dict, snapshot: dict) -> None:
    print(f"Portway {__version__}")
    print(f"Host: {snapshot.get('hostname')}  ({snapshot.get('platform')})")
    print()
    groups = snapshot.get("groups") or {}
    if not groups:
        print("No local networks found.")
        return
    for key, group in groups.items():
        nics = ", ".join(
            f"{n['name']} {n['ip']}/{n['prefix']}" for n in group.get("nics") or []
        )
        print(f"== {key}{('  ' + nics) if nics else ''} ==")
        hosts = {h["ip"]: h for h in group.get("hosts") or []}
        items = [i for i in result.get("open") or [] if i["host"] in hosts]
        if not items:
            print("  (no open ports in this profile)")
            print()
            continue
        by_host: dict[str, list] = {}
        for item in items:
            by_host.setdefault(item["host"], []).append(item)
        for ip, ports in by_host.items():
            meta = hosts.get(ip, {})
            name = meta.get("hostname") or ""
            label = f"{ip}  {name}".rstrip()
            print(f"  {label}")
            for item in sorted(ports, key=lambda p: p["port"]):
                extra = item.get("url") or ""
                print(f"    {item['port']:<6} {item['label']:<22} {extra}")
        print()
    print(f"Open ports: {result.get('count', 0)}  checked: {result.get('checked', 0)}")


def run_cli(args: argparse.Namespace) -> int:
    kinds = args.networks or ["local", "wifi", "tailscale"]
    snapshot = collect_targets(kinds)
    hosts: list[dict] = []
    for group in (snapshot.get("groups") or {}).values():
        hosts.extend(group["hosts"])
    if args.host:
        hosts = [h for h in hosts if h["ip"] == args.host] or [
            {
                "ip": args.host,
                "hostname": args.host,
                "source": "manual",
                "kind": "wifi",
                "nic": "",
                "online": True,
                "os": "",
                "tags": [],
            }
        ]
    ports = list(ports_for_profile(args.profile))
    if args.profile == "deep" and len(hosts) > 1:
        print("All-port scans require --host <ip>", file=sys.stderr)
        return 2

    def on_event(event: dict) -> None:
        if args.verbose and event.get("type") == "progress":
            done = event["done"]
            total = event["total"]
            print(f"\r{done}/{total}  open={event['open']}", end="", file=sys.stderr)
        if args.verbose and event.get("type") == "open":
            item = event["item"]
            print(f"\nopen {item['host']}:{item['port']} {item['label']}", file=sys.stderr)

    result = scan_targets(
        hosts=hosts,
        ports=ports,
        timeout=args.timeout,
        fingerprint=not args.no_fingerprint,
        on_event=on_event,
    )
    if args.verbose:
        print(file=sys.stderr)
    if args.json:
        print(json.dumps({"snapshot": snapshot, "result": result}, indent=2, default=str))
    else:
        _print_cli(result, snapshot)
    return 0


def run_gui() -> int:
    try:
        import webview
    except ImportError:
        print(
            "pywebview is not installed. Run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    index = WEB_DIR / "index.html"
    if not index.exists():
        print(f"UI missing: {index}", file=sys.stderr)
        return 1

    bridge = Bridge()
    window = webview.create_window(
        "Portway",
        url=index.as_uri(),
        js_api=bridge,
        width=1220,
        height=780,
        min_size=(920, 600),
        background_color="#080b10",
        text_select=True,
    )
    bridge.attach(window)
    webview.start(debug=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portway",
        description="Discover and open services on Wi-Fi and Tailscale.",
    )
    parser.add_argument("--version", action="version", version=f"Portway {__version__}")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run a scan in the terminal instead of opening the desktop window.",
    )
    parser.add_argument(
        "--profile",
        choices=("quick", "developer", "deep"),
        default="developer",
        help="Port set to scan (deep requires --host).",
    )
    parser.add_argument(
        "--networks",
        nargs="+",
        choices=("local", "wifi", "ethernet", "tailscale"),
        help="Networks to include. Default: local wifi tailscale.",
    )
    parser.add_argument("--host", help="Scan a single host.")
    parser.add_argument("--timeout", type=float, default=0.28, help="TCP connect timeout.")
    parser.add_argument("--no-fingerprint", action="store_true", help="Skip HTTP probes.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--verbose", action="store_true", help="Progress on stderr.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cli or args.json or args.host:
        return run_cli(args)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
