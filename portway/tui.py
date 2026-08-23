"""Interactive TUI for listing discovered IPs and open ports."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from portway import __version__
from portway.cli import KIND_LABEL, list_hosts
from portway.session import ScanSession
from portway.tokens import looks_protected


class TokenScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def compose(self) -> ComposeResult:
        with Vertical(id="token-dialog"):
            yield Label(f"Token for {self.target}")
            yield Input(placeholder="paste token", password=True, id="token-value")
            with Horizontal(id="token-actions"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            value = self.query_one("#token-value", Input).value.strip()
            self.dismiss(value or None)
        else:
            self.dismiss(None)


class PortwayTUI(App):
    """List local, Wi-Fi, and Tailscale addresses."""

    CSS = """
    Screen { background: #080b10; color: #eef2f7; }
    Header { background: #141018; color: #d4a054; }
    Footer { background: #0c1016; }
    #sidebar { width: 28; border-right: solid #273244; padding: 1; }
    #main { padding: 1; }
    DataTable { height: 1fr; }
    #status { color: #8b97a8; height: 3; padding: 0 1; }
    #token-dialog {
        width: 56; height: auto; padding: 2;
        background: #141b24; border: solid #d4a054;
    }
    #token-actions { height: auto; padding-top: 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "scan", "Scan"),
        Binding("t", "token", "Token"),
        Binding("o", "open", "Open"),
        Binding("l", "toggle_ports", "Ports"),
    ]

    TITLE = f"Portway {__version__}"
    SUB_TITLE = "this machine · wifi · tailscale"

    def __init__(self) -> None:
        super().__init__()
        self.session = ScanSession()
        self.hosts: list[dict] = []
        self.show_ports = False
        self._poller = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static(
                    "Piers\n\nthis-machine  gold\nwifi          cyan\n"
                    "tailscale     magenta\n\nKeys\n r refresh\n s scan\n"
                    " t token\n o open\n l ports\n q quit",
                    id="legend",
                )
            with Vertical(id="main"):
                yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
                yield Static("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("Pier", "Address", "Name", "Source", "Token")
        self.action_refresh()

    def _status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _selected_host(self) -> dict | None:
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return None
        row = table.cursor_row
        if row < 0 or row >= len(self.hosts):
            return None
        return self.hosts[row]

    def _paint_hosts(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear()
        snapshot = self.session.snapshot or self.session.refresh()
        self.hosts = list_hosts(snapshot, self.session.store)
        if self.show_ports and self.session.items:
            table.clear(columns=True)
            table.add_columns("Pier", "Address", "Port", "Service", "Lock")
            rows = []
            for item in self.session.items:
                meta = item.get("host_meta") or {}
                kind = meta.get("kind") or "wifi"
                protected = item.get("protected") or looks_protected(
                    item["port"], item.get("key") or "", item.get("banner")
                )
                if item.get("has_token"):
                    lock = "token"
                elif protected:
                    lock = "needs token"
                else:
                    lock = "open"
                table.add_row(
                    KIND_LABEL.get(kind, kind),
                    item["host"],
                    str(item["port"]),
                    item.get("label") or "",
                    lock,
                )
                rows.append({**meta, "ip": item["host"], "port": item["port"], **item})
            self.hosts = rows
            return
        for host in self.hosts:
            kind = host.get("kind") or "wifi"
            table.add_row(
                KIND_LABEL.get(kind, kind),
                host["ip"],
                host.get("hostname") or "",
                host.get("source") or "",
                "saved" if host.get("has_token") else "-",
            )

    def action_refresh(self) -> None:
        self.session.refresh()
        self.show_ports = False
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_columns("Pier", "Address", "Name", "Source", "Token")
        self._paint_hosts()
        self._status(f"{len(self.hosts)} addresses on this machine, Wi-Fi, and Tailscale.")

    def action_scan(self) -> None:
        result = self.session.start({"profile": "quick"})
        if not result.get("ok"):
            self._status(result.get("error") or "Scan failed")
            return
        self._status("Scanning...")
        if self._poller is not None:
            self._poller.stop()
        self._poller = self.set_interval(0.4, self._poll_scan)

    def _poll_scan(self) -> None:
        status = self.session.status()
        progress = status.get("progress") or {}
        if status["running"]:
            done = progress.get("done", 0)
            total = progress.get("total", 0)
            self._status(f"Sweep {done}/{total}  open={status['count']}")
            return
        if self._poller is not None:
            self._poller.stop()
            self._poller = None
        self.show_ports = True
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_columns("Pier", "Address", "Port", "Service", "Lock")
        self._paint_hosts()
        self._status(f"Done. {status['count']} open ports. Press l to toggle the address list.")

    def action_toggle_ports(self) -> None:
        self.show_ports = not self.show_ports
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        if self.show_ports:
            table.add_columns("Pier", "Address", "Port", "Service", "Lock")
        else:
            table.add_columns("Pier", "Address", "Name", "Source", "Token")
        self._paint_hosts()

    def action_token(self) -> None:
        host = self._selected_host()
        if not host:
            self._status("Select a row first.")
            return
        target = host.get("token_target") or (
            f"{host['ip']}:{host['port']}" if host.get("port") else host["ip"]
        )

        def saved(value: str | None) -> None:
            if not value:
                return
            self.session.store.upsert(str(target), value)
            self._paint_hosts()
            self._status(f"Saved token for {target}.")

        self.push_screen(TokenScreen(str(target)), saved)

    def action_open(self) -> None:
        host = self._selected_host()
        if not host:
            self._status("Select a row first.")
            return
        port = host.get("port")
        if port is None:
            self._status("Scan first, then open a port row.")
            return
        result = self.session.open_service(host["ip"], int(port), host.get("scheme"))
        if result.get("needs_token"):
            self.action_token()
            return
        if result.get("ok"):
            self._status(f"Opened {result.get('url')}")
        else:
            self._status(result.get("error") or "Could not open")


def run_tui() -> int:
    PortwayTUI().run()
    return 0
