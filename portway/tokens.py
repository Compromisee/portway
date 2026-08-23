"""Local access tokens for protected IPs and host:port pairs.

Tokens stay on disk under the user config directory. They are never printed
in full by the CLI, TUI, or API list endpoints.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

TARGET_RE = re.compile(r"^(?P<host>[^:\s]+)(?::(?P<port>\d{1,5}))?$")
STYLES = ("query", "bearer", "header")
PROTECTED_PORTS = {8888, 8889}
PROTECTED_KEYS = {"jupyter", "jupyter-alt"}


def default_store_path() -> Path:
    override = os.environ.get("PORTWAY_TOKEN_STORE")
    if override:
        return Path(override)
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "portway" / "tokens.json"


def normalize_target(target: str) -> str:
    text = (target or "").strip()
    match = TARGET_RE.match(text)
    if not match:
        raise ValueError("Target must be an IP/hostname or host:port")
    host = match.group("host")
    port = match.group("port")
    if port:
        value = int(port)
        if value < 1 or value > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return f"{host}:{value}"
    return host


def looks_protected(port: int, key: str = "", banner: dict | None = None) -> bool:
    if port in PROTECTED_PORTS:
        return True
    if key in PROTECTED_KEYS:
        return True
    status = (banner or {}).get("status")
    return status in {401, 403}


def mask_secret(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 6:
        return "*" * len(token)
    return f"{token[:2]}{'*' * min(8, len(token) - 4)}{token[-2:]}"


@dataclass
class AccessToken:
    target: str
    token: str
    style: str = "query"
    query_key: str = "token"
    note: str = ""

    def to_public_dict(self) -> dict:
        data = asdict(self)
        data["token"] = mask_secret(self.token)
        data["has_token"] = bool(self.token)
        return data

    def to_private_dict(self) -> dict:
        return asdict(self)


def apply_token_to_url(url: str, record: AccessToken | None) -> str:
    if not url or record is None or not record.token:
        return url
    if record.style != "query":
        return url
    parsed = urlparse(url)
    key = record.query_key or "token"
    extra = f"{quote(key)}={quote(record.token)}"
    query = f"{parsed.query}&{extra}" if parsed.query else extra
    return urlunparse(parsed._replace(query=query))


def auth_headers(record: AccessToken | None) -> dict[str, str]:
    if record is None or not record.token:
        return {}
    if record.style == "bearer":
        return {"Authorization": f"Bearer {record.token}"}
    if record.style == "header":
        return {"Authorization": record.token}
    return {}


class TokenStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self._items: dict[str, AccessToken] = {}
        self.load()

    def load(self) -> None:
        self._items = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rows = raw if isinstance(raw, list) else raw.get("tokens") or []
        for row in rows:
            if not isinstance(row, dict) or not row.get("target") or not row.get("token"):
                continue
            try:
                target = normalize_target(row["target"])
            except ValueError:
                continue
            style = row.get("style") if row.get("style") in STYLES else "query"
            self._items[target] = AccessToken(
                target=target,
                token=str(row["token"]),
                style=style,
                query_key=str(row.get("query_key") or "token"),
                note=str(row.get("note") or ""),
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.to_private_dict() for item in self._items.values()]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list(self) -> list[AccessToken]:
        return [self._items[key] for key in sorted(self._items)]

    def get(self, host: str, port: int | None = None) -> AccessToken | None:
        if port is not None:
            exact = self._items.get(f"{host}:{int(port)}")
            if exact:
                return exact
        return self._items.get(host)

    def upsert(
        self,
        target: str,
        token: str,
        style: str = "query",
        query_key: str = "token",
        note: str = "",
    ) -> AccessToken:
        key = normalize_target(target)
        if style not in STYLES:
            raise ValueError(f"Unknown token style: {style}")
        if not token.strip():
            raise ValueError("Token cannot be empty")
        record = AccessToken(
            target=key,
            token=token.strip(),
            style=style,
            query_key=query_key or "token",
            note=note,
        )
        self._items[key] = record
        self.save()
        return record

    def delete(self, target: str) -> bool:
        key = normalize_target(target)
        if key not in self._items:
            return False
        del self._items[key]
        self.save()
        return True

    def annotate(self, item: dict) -> dict:
        """Attach protection / token flags to a scan result or host dict."""
        host = item.get("host") or item.get("ip") or ""
        port = item.get("port")
        record = self.get(host, int(port) if port is not None else None)
        protected = bool(record) or looks_protected(
            int(port or 0),
            item.get("key") or "",
            item.get("banner"),
        )
        item["protected"] = protected
        item["has_token"] = bool(record)
        item["token_target"] = record.target if record else (f"{host}:{port}" if port else host)
        if item.get("url") and record:
            item["url"] = apply_token_to_url(item["url"], record)
        return item
