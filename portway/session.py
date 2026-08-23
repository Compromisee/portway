"""Shared scan session used by Flask, the TUI, and the desktop bridge."""

from __future__ import annotations

import threading
import webbrowser
from typing import Any

from portway.discovery import collect_targets
from portway.scanner import ScanController, scan_targets
from portway.services import parse_port_list, ports_for_profile, url_for
from portway.tokens import TokenStore, apply_token_to_url, looks_protected


def flatten_hosts(snapshot: dict, host: str | None = None) -> list[dict]:
    hosts: list[dict] = []
    for group in (snapshot.get("groups") or {}).values():
        hosts.extend(group.get("hosts") or [])
    if host:
        matches = [item for item in hosts if item.get("ip") == host]
        return matches or [
            {
                "ip": host,
                "hostname": host,
                "source": "manual",
                "kind": "wifi",
                "nic": "",
                "online": True,
                "os": "",
                "tags": [],
            }
        ]
    return hosts


class ScanSession:
    def __init__(self, store: TokenStore | None = None) -> None:
        self.store = store or TokenStore()
        self._controller = ScanController()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.snapshot: dict = {}
        self.items: list[dict] = []
        self.progress: dict[str, Any] = {}
        self.last_error: str | None = None

    def refresh(self, kinds: list[str] | None = None) -> dict:
        self.snapshot = collect_targets(kinds or ["local", "wifi", "tailscale"])
        return self.snapshot

    def scanning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "open":
            item = self.store.annotate(dict(event["item"]))
            self.items.append(item)
        elif kind == "progress" or kind == "start" or kind == "done":
            self.progress = event

    def start(self, options: dict | None = None) -> dict:
        options = options or {}
        with self._lock:
            if self.scanning():
                return {"ok": False, "error": "A scan is already running"}

            kinds = options.get("networks") or ["local", "wifi", "tailscale"]
            profile = options.get("profile") or "developer"
            custom = options.get("ports") or ""
            single_host = options.get("host")
            timeout = float(options.get("timeout") or 0.28)
            fingerprint = bool(options.get("fingerprint", True))
            ports = parse_port_list(custom) if custom else list(ports_for_profile(profile))

            snapshot = self.refresh(kinds)
            hosts = flatten_hosts(snapshot, single_host)
            if not hosts:
                return {"ok": False, "error": "No hosts to scan on the selected networks"}
            if len(ports) > 4096 and len(hosts) > 1:
                return {
                    "ok": False,
                    "error": "All-port scans run against one host at a time. Select a host first.",
                }

            self.items = []
            self.progress = {}
            self.last_error = None
            self._controller = ScanController()
            thread = threading.Thread(
                target=scan_targets,
                kwargs={
                    "hosts": hosts,
                    "ports": ports,
                    "timeout": timeout,
                    "fingerprint": fingerprint,
                    "on_event": self._on_event,
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

    def cancel(self) -> dict:
        self._controller.cancel()
        return {"ok": True}

    def status(self) -> dict:
        return {
            "running": self.scanning(),
            "items": list(self.items),
            "progress": self.progress,
            "count": len(self.items),
        }

    def open_service(
        self,
        host: str,
        port: int,
        scheme: str | None = None,
        token: str | None = None,
        style: str = "query",
        query_key: str = "token",
        save: bool = True,
    ) -> dict:
        url = url_for(host, int(port), scheme)
        if not url:
            return {
                "ok": False,
                "error": "This port is not a web service. Copy the address instead.",
                "target": f"{host}:{port}",
            }
        record = self.store.get(host, int(port))
        if token:
            if save:
                record = self.store.upsert(
                    f"{host}:{int(port)}",
                    token,
                    style=style,
                    query_key=query_key,
                )
            else:
                from portway.tokens import AccessToken

                record = AccessToken(
                    target=f"{host}:{int(port)}",
                    token=token,
                    style=style,
                    query_key=query_key,
                )
        if looks_protected(int(port)) and record is None:
            return {
                "ok": False,
                "needs_token": True,
                "error": "This address looks protected. Enter a token to open it.",
                "target": f"{host}:{port}",
                "url": url,
            }
        final = apply_token_to_url(url, record)
        opened = webbrowser.open(final)
        return {"ok": True, "url": final, "opened": opened, "used_token": bool(record)}
