"""Shared scan session used by Flask, the TUI, and the desktop bridge."""

from __future__ import annotations

import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from portway.discovery import (
    collect_targets,
    host_is_live,
    list_nics,
    subnet_ips,
)
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
    return [item for item in hosts if item.get("source") != "subnet"]


class ScanSession:
    def __init__(self, store: TokenStore | None = None) -> None:
        self.store = store or TokenStore()
        self._controller = ScanController()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.snapshot: dict = {}
        self.items: list[dict] = []
        self.hosts: dict[str, dict] = {}
        self.activity: list[dict] = []
        self.progress: dict[str, Any] = {}
        self.phase: str = "idle"
        self.last_error: str | None = None
        self.started_at: float | None = None

    def refresh(self, kinds: list[str] | None = None) -> dict:
        self.snapshot = collect_targets(kinds or ["local", "wifi", "tailscale"])
        return self.snapshot

    def scanning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _log(self, text: str) -> None:
        self.activity.append({"text": text, "t": time.time()})
        self.activity = self.activity[-48:]

    def _note_host(self, host: dict, state: str) -> None:
        ip = host.get("ip")
        if not ip:
            return
        current = self.hosts.get(ip, {})
        current.update(host)
        current["state"] = state
        current.setdefault("open_count", current.get("open_count") or 0)
        self.hosts[ip] = current

    def _on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "open":
            item = self.store.annotate(dict(event["item"]))
            self.items.append(item)
            ip = item.get("host")
            if ip and ip in self.hosts:
                self.hosts[ip]["open_count"] = int(self.hosts[ip].get("open_count") or 0) + 1
                self.hosts[ip]["state"] = "open"
            self._log(f"Open {item['host']}:{item['port']} {item.get('label') or ''}".strip())
        elif kind in {"progress", "start", "done"}:
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
            if len(ports) > 4096 and not single_host:
                return {
                    "ok": False,
                    "error": "All-port scans run against one host at a time. Select a host first.",
                }

            self.items = []
            self.hosts = {}
            self.activity = []
            self.progress = {}
            self.last_error = None
            self.phase = "discover"
            self.started_at = time.time()
            self._controller = ScanController()
            thread = threading.Thread(
                target=self._run,
                kwargs={
                    "snapshot": snapshot,
                    "kinds": kinds,
                    "ports": ports,
                    "single_host": single_host,
                    "timeout": timeout,
                    "fingerprint": fingerprint,
                    "profile": profile,
                },
                daemon=True,
                name="portway-scan",
            )
            self._thread = thread
            thread.start()
            return {"ok": True, "profile": profile, "phase": "discover"}

    def _run(
        self,
        snapshot: dict,
        kinds: list[str],
        ports: list[int],
        single_host: str | None,
        timeout: float,
        fingerprint: bool,
        profile: str,
    ) -> None:
        known = flatten_hosts(snapshot, single_host)
        for host in known:
            self._note_host(host, "known")
            self._log(f"Known {host['ip']} ({host.get('source') or host.get('kind')})")

        if not single_host:
            wanted = set(kinds)
            nics = [
                nic
                for nic in list_nics()
                if nic.kind in wanted or (nic.kind == "ethernet" and "wifi" in wanted)
            ]
            probes: list[tuple[str, Any]] = []
            seen = set(self.hosts)
            for nic in nics:
                if nic.kind not in {"wifi", "ethernet"}:
                    continue
                for ip in subnet_ips(nic):
                    if ip in seen:
                        continue
                    seen.add(ip)
                    probes.append((ip, nic))
            self._log(f"Probing {len(probes)} LAN addresses")
            self.progress = {
                "type": "discover",
                "done": 0,
                "total": len(probes),
                "open": 0,
            }
            if probes and not self._controller.cancelled():
                done = 0
                workers = max(16, min(120, len(probes)))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(host_is_live, ip): (ip, nic) for ip, nic in probes}
                    for future in as_completed(futures):
                        if self._controller.cancelled():
                            break
                        ip, nic = futures[future]
                        done += 1
                        live = False
                        try:
                            live = bool(future.result())
                        except Exception:
                            live = False
                        if live:
                            self._note_host(
                                {
                                    "ip": ip,
                                    "hostname": "",
                                    "source": "probe",
                                    "kind": "wifi" if nic.kind == "ethernet" else nic.kind,
                                    "nic": nic.name,
                                    "online": True,
                                    "os": "",
                                    "tags": ["live"],
                                },
                                "live",
                            )
                            self._log(f"Live {ip} on {nic.name}")
                        if done % 8 == 0 or live:
                            self.progress = {
                                "type": "discover",
                                "done": done,
                                "total": len(probes),
                                "open": len(self.items),
                                "current_host": ip,
                                "current_port": 0,
                            }

        if self._controller.cancelled():
            self.phase = "cancelled"
            self._log("Scan cancelled")
            return

        targets = list(self.hosts.values())
        if not targets:
            self.phase = "done"
            self._log("No live hosts found")
            self.progress = {"type": "done", "done": 0, "total": 0, "open": 0, "cancelled": False}
            return

        for host in targets:
            host["state"] = "scanning"
        self.phase = "scan"
        self._log(f"Scanning {len(targets)} live hosts · {len(ports)} ports ({profile})")
        scan_targets(
            hosts=targets,
            ports=ports,
            timeout=timeout,
            fingerprint=fingerprint,
            on_event=self._on_event,
            controller=self._controller,
        )
        for host in self.hosts.values():
            if host.get("open_count"):
                host["state"] = "open"
            elif host.get("state") == "scanning":
                host["state"] = "quiet"
        self.phase = "cancelled" if self._controller.cancelled() else "done"
        self._log(f"Done · {len(self.items)} open ports on {len(self.hosts)} hosts")

    def cancel(self) -> dict:
        self._controller.cancel()
        return {"ok": True}

    def status(self) -> dict:
        return {
            "running": self.scanning(),
            "phase": self.phase,
            "items": list(self.items),
            "hosts": list(self.hosts.values()),
            "activity": list(self.activity),
            "progress": self.progress,
            "count": len(self.items),
            "started_at": self.started_at,
            "snapshot": self.snapshot,
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
