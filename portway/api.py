"""pywebview JavaScript bridge."""

from __future__ import annotations

import contextlib
import json
import threading
import webbrowser
from typing import Any

from portway import __version__
from portway.discovery import collect_targets, list_nics, load_tailscale
from portway.scanner import ScanController, scan_targets
from portway.services import PROFILES, parse_port_list, ports_for_profile, url_for


class Bridge:
    def __init__(self) -> None:
        self.window = None
        self._controller = ScanController()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def attach(self, window) -> None:  # noqa: ANN001
        self.window = window

    def _push(self, payload: dict[str, Any]) -> None:
        if self.window is None:
            return
        encoded = json.dumps(payload, default=str)
        with contextlib.suppress(Exception):
            self.window.evaluate_js(f"window.portway && window.portway.ingest({encoded})")

    def version(self) -> str:
        return __version__

    def snapshot(self, kinds: list[str] | None = None) -> dict:
        return collect_targets(kinds)

    def profiles(self) -> dict:
        return {
            name: {
                "label": data["label"],
                "hint": data["hint"],
                "count": len(data["ports"]) if name != "deep" else 65535,
            }
            for name, data in PROFILES.items()
        }

    def interfaces(self) -> list[dict]:
        return [n.to_dict() for n in list_nics()]

    def tailscale(self) -> dict:
        hosts, meta = load_tailscale()
        return {"hosts": [h.to_dict() for h in hosts], **meta}

    def start_scan(self, options: dict | None = None) -> dict:
        options = options or {}
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"ok": False, "error": "A scan is already running"}

            kinds = options.get("networks") or ["local", "wifi", "tailscale"]
            profile = options.get("profile") or "developer"
            custom = options.get("ports") or ""
            single_host = options.get("host")
            timeout = float(options.get("timeout") or 0.28)
            fingerprint = bool(options.get("fingerprint", True))

            ports = parse_port_list(custom) if custom else list(ports_for_profile(profile))

            snapshot = collect_targets(kinds)
            hosts: list[dict] = []
            for group in snapshot["groups"].values():
                hosts.extend(group["hosts"])

            if single_host:
                hosts = [h for h in hosts if h["ip"] == single_host]
                if not hosts:
                    hosts = [
                        {
                            "ip": single_host,
                            "hostname": single_host,
                            "source": "manual",
                            "kind": "wifi",
                            "nic": "",
                            "online": True,
                            "os": "",
                            "tags": [],
                        }
                    ]
                # Deep scans are only allowed against one already-known local host
                if profile == "deep" and len(ports) > 4096:
                    pass

            if not hosts:
                return {"ok": False, "error": "No hosts to scan on the selected networks"}

            # Guard: all-port sweep only on a single host
            if len(ports) > 4096 and len(hosts) > 1:
                return {
                    "ok": False,
                    "error": "All-port scans run against one host at a time. Select a host first.",
                }

            self._controller = ScanController()
            thread = threading.Thread(
                target=scan_targets,
                kwargs={
                    "hosts": hosts,
                    "ports": ports,
                    "timeout": timeout,
                    "fingerprint": fingerprint,
                    "on_event": self._push,
                    "controller": self._controller,
                },
                daemon=True,
                name="portway-scan",
            )
            self._thread = thread
            thread.start()
            return {
                "ok": True,
                "hosts": len(hosts),
                "ports": len(ports),
                "profile": profile,
            }

    def cancel_scan(self) -> dict:
        self._controller.cancel()
        return {"ok": True}

    def scanning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def open_service(self, host: str, port: int, scheme: str | None = None) -> dict:
        url = url_for(host, int(port), scheme)
        if not url:
            return {
                "ok": False,
                "error": "This port is not a web service. Copy the address instead.",
                "target": f"{host}:{port}",
            }
        opened = webbrowser.open(url)
        return {"ok": True, "url": url, "opened": opened}

    def open_url(self, url: str) -> dict:
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "Only http and https URLs can be opened"}
        opened = webbrowser.open(url)
        return {"ok": True, "url": url, "opened": opened}
