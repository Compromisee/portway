"""Desktop window, Flask server, TUI, and CLI entry point."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

from portway import __version__
from portway.cli import print_ip_list, print_scan
from portway.discovery import collect_targets
from portway.scanner import scan_targets
from portway.services import ports_for_profile
from portway.session import flatten_hosts
from portway.tokens import TokenStore


def _web_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "portway" / "web"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent / "web"


WEB_DIR = _web_dir()


def _store() -> TokenStore:
    return TokenStore()


def run_list(args: argparse.Namespace) -> int:
    kinds = args.networks or ["local", "wifi", "tailscale"]
    snapshot = collect_targets(kinds)
    store = _store()
    if args.token:
        for spec in args.token:
            if "=" not in spec:
                print("Token specs look like host=secret or host:port=secret", file=sys.stderr)
                return 2
            target, secret = spec.split("=", 1)
            store.upsert(target, secret)
    if args.scan:
        hosts = flatten_hosts(snapshot, args.host)
        ports = list(ports_for_profile(args.profile))
        result = scan_targets(
            hosts=hosts,
            ports=ports,
            timeout=args.timeout,
            fingerprint=not args.no_fingerprint,
        )
        items = [store.annotate(dict(item)) for item in result.get("open") or []]
        if args.json:
            print(
                json.dumps(
                    {"snapshot": snapshot, "hosts": flatten_hosts(snapshot), "open": items},
                    indent=2,
                )
            )
            return 0
        print_scan(snapshot, items, store)
        return 0
    if args.json:
        print(json.dumps({"snapshot": snapshot, "hosts": flatten_hosts(snapshot)}, indent=2))
        return 0
    print_ip_list(snapshot, store)
    return 0


def run_scan(args: argparse.Namespace) -> int:
    args.scan = True
    return run_list(args)


def run_tui() -> int:
    from portway.tui import run_tui as _run

    return _run()


def run_server(args: argparse.Namespace) -> int:
    from portway.server import run_server as _run

    _run(host=args.bind, port=args.port)
    return 0


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_gui(args: argparse.Namespace) -> int:
    try:
        import webview
    except ImportError:
        print("pywebview is not installed. Falling back to the Flask server.", file=sys.stderr)
        return run_server(args)

    from portway.server import create_app

    port = args.port or _free_port()
    app = create_app()
    thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1",
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False,
        ),
        daemon=True,
        name="portway-flask",
    )
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    url = f"http://127.0.0.1:{port}/"
    webview.create_window(
        "Portway",
        url=url,
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#080b10",
        text_select=True,
    )
    webview.start(debug=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portway",
        description="Discover and open services on Wi-Fi and Tailscale.",
    )
    parser.add_argument("--version", action="version", version=f"Portway {__version__}")
    sub = parser.add_subparsers(dest="command")

    def add_scan_flags(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--profile",
            choices=("quick", "developer", "deep"),
            default="developer",
            help="Port set to scan (deep requires --host).",
        )
        target.add_argument(
            "--networks",
            nargs="+",
            choices=("local", "wifi", "ethernet", "tailscale"),
            help="Networks to include. Default: local wifi tailscale.",
        )
        target.add_argument("--host", help="Limit to a single host.")
        target.add_argument("--timeout", type=float, default=0.28, help="TCP connect timeout.")
        target.add_argument("--no-fingerprint", action="store_true", help="Skip HTTP probes.")
        target.add_argument("--json", action="store_true", help="Print machine-readable output.")
        target.add_argument(
            "--token",
            action="append",
            default=[],
            help="Save a token as host=secret or host:port=secret. Repeatable.",
        )

    gui = sub.add_parser("gui", help="Open the HeroUI desktop window.")
    gui.add_argument("--bind", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=0, help="Flask port. 0 picks a free port.")

    serve = sub.add_parser("serve", help="Run the Flask API and GUI server.")
    serve.add_argument("--bind", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=5050)

    sub.add_parser("tui", help="Interactive terminal listing.")

    listing = sub.add_parser("list", help="Color listing of every discovered IP.")
    add_scan_flags(listing)
    listing.add_argument("--scan", action="store_true", help="Also scan ports after listing IPs.")

    scan = sub.add_parser("scan", help="Scan and print a colored report.")
    add_scan_flags(scan)

    parser.add_argument("--cli", action="store_true", help="Alias for the scan command.")
    parser.add_argument("--profile", choices=("quick", "developer", "deep"), default="developer")
    parser.add_argument(
        "--networks",
        nargs="+",
        choices=("local", "wifi", "ethernet", "tailscale"),
    )
    parser.add_argument("--host", help="Scan a single host.")
    parser.add_argument("--timeout", type=float, default=0.28)
    parser.add_argument("--no-fingerprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--token", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command == "gui":
        return run_gui(args)
    if command == "serve":
        return run_server(args)
    if command == "tui":
        return run_tui()
    if command == "list":
        return run_list(args)
    if command == "scan" or args.cli or args.json or args.host:
        if command != "scan":
            args.scan = True
            args.token = getattr(args, "token", [])
        else:
            args.scan = True
        return run_list(args)
    args.bind = "127.0.0.1"
    args.port = 0
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
