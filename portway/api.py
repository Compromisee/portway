"""pywebview JavaScript bridge, kept as a thin wrapper over ScanSession."""

from __future__ import annotations

from portway import __version__
from portway.discovery import list_nics, load_tailscale
from portway.services import PROFILES
from portway.session import ScanSession
from portway.tokens import normalize_target


class Bridge:
    def __init__(self) -> None:
        self.window = None
        self.session = ScanSession()

    def attach(self, window) -> None:  # noqa: ANN001
        self.window = window

    def version(self) -> str:
        return __version__

    def snapshot(self, kinds: list[str] | None = None) -> dict:
        return self.session.refresh(kinds)

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
        return self.session.start(options)

    def cancel_scan(self) -> dict:
        return self.session.cancel()

    def scanning(self) -> bool:
        return self.session.scanning()

    def scan_status(self) -> dict:
        return self.session.status()

    def open_service(
        self,
        host: str,
        port: int,
        scheme: str | None = None,
        token: str | None = None,
    ) -> dict:
        return self.session.open_service(host, int(port), scheme, token)

    def list_tokens(self) -> list[dict]:
        return [item.to_public_dict() for item in self.session.store.list()]

    def save_token(self, target: str, token: str, style: str = "query") -> dict:
        record = self.session.store.upsert(target, token, style=style)
        return {"ok": True, "token": record.to_public_dict()}

    def delete_token(self, target: str) -> dict:
        return {"ok": self.session.store.delete(normalize_target(target))}
