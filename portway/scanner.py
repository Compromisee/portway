"""Concurrent TCP connect scanner with optional HTTP fingerprinting."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any

from portway.services import hint_for, url_for
from portway.tokens import looks_protected

EventCallback = Callable[[dict[str, Any]], None]


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def parse_html_title(html: str) -> str:
    parser = _TitleParser()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return " ".join(parser.title.split())[:120]


def parse_http_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    lines = raw.split("\r\n")
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def probe_http(host: str, port: int, timeout: float = 0.8) -> dict[str, Any] | None:
    """Issue a tiny HTTP GET. Returns fingerprint or None if not HTTP."""
    request = (
        f"GET / HTTP/1.0\r\n"
        f"Host: {host}:{port}\r\n"
        f"User-Agent: Portway/0.1\r\n"
        f"Accept: text/html,*/*\r\n"
        f"Connection: close\r\n\r\n"
    )
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request.encode("ascii"))
            chunks: list[bytes] = []
            received = 0
            while received < 4096:
                piece = sock.recv(1024)
                if not piece:
                    break
                chunks.append(piece)
                received += len(piece)
    except OSError:
        return None
    raw = b"".join(chunks)
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    if not text.startswith("HTTP/"):
        return None
    head, _, body = text.partition("\r\n\r\n")
    status_line = head.split("\r\n", 1)[0]
    parts = status_line.split(" ", 2)
    status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    headers = parse_http_headers(head)
    title = parse_html_title(body)
    server = headers.get("server", "")
    location = headers.get("location", "")
    scheme = "https" if port in {443, 8443, 9443} else "http"
    return {
        "http": True,
        "scheme": scheme,
        "status": status,
        "server": server,
        "title": title,
        "location": location,
        "tls": False,
    }


def check_port(host: str, port: int, timeout: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            sock.close()


@dataclass
class OpenPort:
    host: str
    port: int
    label: str
    key: str
    group: str
    scheme: str | None
    url: str | None
    openable: bool
    protected: bool = False
    banner: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ScanController:
    def __init__(self) -> None:
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self.running = False

    def cancel(self) -> None:
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def reset(self) -> None:
        self._cancel = threading.Event()


def fingerprint_port(host: str, port: int, timeout: float) -> OpenPort:
    banner: dict[str, Any] = {}
    http = probe_http(host, port, timeout=max(timeout, 0.6))
    http_detected = bool(http)
    if http:
        banner = http
    hint = hint_for(port, http_detected=http_detected)
    scheme = (http.get("scheme") or hint.scheme) if http else hint.scheme
    if http and http.get("title"):
        label = http["title"]
    elif http and http.get("server"):
        label = http["server"]
    else:
        label = hint.label
    url = url_for(host, port, scheme)
    return OpenPort(
        host=host,
        port=port,
        label=label,
        key=hint.key,
        group=hint.group,
        scheme=scheme,
        url=url,
        openable=bool(url),
        banner=banner,
    )


def scan_targets(
    hosts: list[dict],
    ports: list[int],
    timeout: float = 0.28,
    workers: int = 180,
    fingerprint: bool = True,
    on_event: EventCallback | None = None,
    controller: ScanController | None = None,
) -> dict[str, Any]:
    """Scan many host:port pairs. Streams events through on_event."""
    ctrl = controller or ScanController()
    ctrl.reset()
    ctrl.running = True
    started = time.time()
    emit = on_event or (lambda _event: None)

    work: list[tuple[str, int, dict]] = []
    host_meta = {h["ip"]: h for h in hosts}
    for host in hosts:
        ip = host["ip"]
        for port in ports:
            work.append((ip, port, host))

    total = len(work)
    emit(
        {
            "type": "start",
            "total": total,
            "hosts": len(hosts),
            "ports": len(ports),
        }
    )

    found: list[dict] = []
    done = 0
    last_progress = 0.0

    def handle_open(ip: str, port: int) -> None:
        if fingerprint:
            item = fingerprint_port(ip, port, timeout)
            payload = item.to_dict()
        else:
            hint = hint_for(port)
            payload = OpenPort(
                host=ip,
                port=port,
                label=hint.label,
                key=hint.key,
                group=hint.group,
                scheme=hint.scheme,
                url=url_for(ip, port, hint.scheme),
                openable=bool(hint.scheme),
                protected=looks_protected(port, hint.key),
            ).to_dict()
        payload["host_meta"] = host_meta.get(ip, {})
        found.append(payload)
        emit({"type": "open", "item": payload})

    max_workers = max(8, min(workers, total or 1, 400))
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(check_port, ip, port, timeout): (ip, port)
                for ip, port, _host in work
            }
            for future in as_completed(futures):
                if ctrl.cancelled():
                    break
                ip, port = futures[future]
                done += 1
                try:
                    is_open = future.result()
                except Exception:
                    is_open = False
                if is_open:
                    handle_open(ip, port)
                now = time.time()
                if now - last_progress > 0.12 or done == total:
                    last_progress = now
                    emit(
                        {
                            "type": "progress",
                            "done": done,
                            "total": total,
                            "open": len(found),
                            "current_host": ip,
                            "current_port": port,
                            "elapsed": now - started,
                        }
                    )
    finally:
        ctrl.running = False

    elapsed = time.time() - started
    result = {
        "type": "done",
        "cancelled": ctrl.cancelled(),
        "open": found,
        "count": len(found),
        "checked": done,
        "total": total,
        "elapsed": elapsed,
    }
    emit(result)
    return result
