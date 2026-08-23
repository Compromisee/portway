"""Colored CLI listing of discovered IPs and optional open ports."""

from __future__ import annotations

from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.text import Text

from portway import __version__
from portway.session import flatten_hosts
from portway.tokens import TokenStore, looks_protected

KIND_STYLE = {
    "local": "bold gold1",
    "wifi": "bold cyan",
    "ethernet": "bold green",
    "tailscale": "bold magenta",
}

KIND_LABEL = {
    "local": "this-machine",
    "wifi": "wifi",
    "ethernet": "ethernet",
    "tailscale": "tailscale",
}

console = Console(highlight=False)


def style_for(kind: str) -> str:
    return KIND_STYLE.get(kind, "bold white")


def colored_ip(ip: str, kind: str) -> Text:
    return Text(ip, style=style_for(kind))


def list_hosts(snapshot: dict, store: TokenStore | None = None) -> list[dict]:
    hosts = flatten_hosts(snapshot)
    store = store or TokenStore()
    rows = []
    seen: set[str] = set()
    for host in hosts:
        ip = host.get("ip") or ""
        if not ip or ip in seen:
            continue
        seen.add(ip)
        record = store.get(ip)
        row = dict(host)
        row["has_token"] = bool(record)
        row["protected"] = bool(record)
        rows.append(row)
    return rows


def print_ip_list(snapshot: dict, store: TokenStore | None = None) -> None:
    store = store or TokenStore()
    rows = list_hosts(snapshot, store)
    table = Table(
        title=f"Portway {__version__}  {snapshot.get('hostname', '')}",
        expand=True,
        show_lines=False,
    )
    table.add_column("Pier", style="dim")
    table.add_column("Address")
    table.add_column("Name")
    table.add_column("Source", style="dim")
    table.add_column("Token")
    if not rows:
        console.print("[yellow]No local addresses found.[/yellow]")
        return
    for host in rows:
        kind = host.get("kind") or "wifi"
        token_cell = (
            Text("saved", style="green") if host.get("has_token") else Text("-", style="dim")
        )
        table.add_row(
            KIND_LABEL.get(kind, kind),
            colored_ip(host["ip"], kind),
            host.get("hostname") or "",
            host.get("source") or "",
            token_cell,
        )
    console.print(table)
    console.print(
        Text.assemble(
            ("legend  ", "dim"),
            ("this-machine ", "gold1"),
            ("wifi ", "cyan"),
            ("ethernet ", "green"),
            ("tailscale", "magenta"),
        )
    )


def print_scan(snapshot: dict, items: list[dict], store: TokenStore | None = None) -> None:
    store = store or TokenStore()
    print_ip_list(snapshot, store)
    if not items:
        console.print("\n[dim]No open ports in this profile.[/dim]")
        return
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["host"]].append(store.annotate(dict(item)))
    table = Table(title="Open ports", expand=True)
    table.add_column("Address")
    table.add_column("Port", justify="right")
    table.add_column("Service")
    table.add_column("URL")
    table.add_column("Lock")
    for host, ports in grouped.items():
        kind = (ports[0].get("host_meta") or {}).get("kind") or "wifi"
        for item in sorted(ports, key=lambda row: row["port"]):
            protected = item.get("protected") or looks_protected(
                item["port"], item.get("key") or "", item.get("banner")
            )
            if item.get("has_token"):
                lock = Text("token", style="green")
            elif protected:
                lock = Text("needs token", style="red")
            else:
                lock = Text("open", style="dim")
            table.add_row(
                colored_ip(host, kind),
                str(item["port"]),
                item.get("label") or "",
                item.get("url") or f"{host}:{item['port']}",
                lock,
            )
    console.print()
    console.print(table)
