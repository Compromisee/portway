"""Local interface, LAN, and Tailscale host discovery.

Scanning is constrained to networks this machine is already on:
loopback, the connected Wi-Fi / Ethernet subnet, and Tailscale peers.
Arbitrary internet ranges are rejected.
"""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")
LOOPBACK = ipaddress.ip_network("127.0.0.0/8")

VIRTUAL_PREFIXES = (
    "docker",
    "br-",
    "veth",
    "virbr",
    "vmnet",
    "vbox",
    "vethernet",
    "cni",
    "flannel",
    "kube",
    "zt",
    "tun",
    "tap",
    "wg",
    "utun",
)

WIFI_HINTS = ("wlan", "wlp", "wlx", "wifi", "wi-fi", "en0", "en1", "wlo")
ETHER_HINTS = ("eth", "enp", "ens", "eno", "ethernet", "lan")
TAILSCALE_HINTS = ("tailscale", "ts-")


@dataclass
class Nic:
    name: str
    ip: str
    prefix: int
    kind: str
    cidr: str
    gateway: str | None = None

    def network(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_network(self.cidr, strict=False)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Host:
    ip: str
    hostname: str = ""
    source: str = "lan"
    nic: str = ""
    kind: str = "wifi"
    online: bool = True
    os: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_cmd(args: list[str], timeout: float = 5.0) -> str | None:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def is_tailscale_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in TAILSCALE_CGNAT
    except ValueError:
        return False


def is_loopback_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in LOOPBACK
    except ValueError:
        return False


def classify_iface(name: str, ip: str) -> str:
    lower = name.lower()
    if lower in {"lo", "lo0", "loopback"} or is_loopback_ip(ip):
        return "local"
    if any(lower.startswith(p) for p in TAILSCALE_HINTS) or is_tailscale_ip(ip):
        return "tailscale"
    if any(h in lower for h in WIFI_HINTS):
        return "wifi"
    if any(lower.startswith(p) for p in VIRTUAL_PREFIXES):
        return "virtual"
    if any(h in lower for h in ETHER_HINTS):
        return "ethernet"
    return "wifi"


def constrain_network(cidr: str, host_ip: str | None = None) -> ipaddress.IPv4Network:
    """Refuse huge or public ranges. Cap discovery at /24 around the host."""
    net = ipaddress.ip_network(cidr, strict=False)
    if not net.version == 4:
        raise ValueError("Only IPv4 is supported")
    if net.is_global and net not in (
        ipaddress.ip_network("100.64.0.0/10"),
    ) and not any(
        ipaddress.ip_address(str(net.network_address)) in block
        for block in (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            TAILSCALE_CGNAT,
            LOOPBACK,
        )
    ):
        # ip_network.is_global is True for many private-adjacent ranges; extra check:
        addr = ipaddress.ip_address(host_ip) if host_ip else net.network_address
        if not (
            addr.is_private
            or addr.is_loopback
            or addr in TAILSCALE_CGNAT
            or addr.is_link_local
        ):
            raise ValueError(f"Refusing to scan non-local network {cidr}")
    addr = ipaddress.ip_address(host_ip) if host_ip else next(net.hosts(), net.network_address)
    if not (
        addr.is_private
        or addr.is_loopback
        or addr in TAILSCALE_CGNAT
        or addr.is_link_local
    ):
        raise ValueError(f"Refusing to scan non-local address {addr}")
    if net.prefixlen < 24:
        # Never walk a /16. Stay on the host's /24.
        return ipaddress.ip_network(f"{addr}/{max(net.prefixlen, 24)}", strict=False)
    if net.num_addresses > 256:
        return ipaddress.ip_network(f"{addr}/24", strict=False)
    return net


def parse_ip_o_addr(text: str) -> list[Nic]:
    """Parse `ip -4 -o addr show` output."""
    nics: list[Nic] = []
    pattern = re.compile(
        r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)",
        re.MULTILINE,
    )
    for name, ip, prefix in pattern.findall(text):
        name = name.split("@", 1)[0]
        kind = classify_iface(name, ip)
        if kind == "virtual":
            continue
        cidr = f"{ip}/{prefix}"
        nics.append(Nic(name=name, ip=ip, prefix=int(prefix), kind=kind, cidr=cidr))
    return nics


def parse_ifconfig(text: str) -> list[Nic]:
    nics: list[Nic] = []
    blocks = re.split(r"\n(?=\S)", text)
    for block in blocks:
        header = re.match(r"^(\S+):", block)
        if not header:
            continue
        name = header.group(1)
        match = re.search(r"inet(?: addr:)?\s*(\d+\.\d+\.\d+\.\d+)", block)
        if not match:
            continue
        ip = match.group(1)
        mask_match = re.search(r"(?:netmask|Mask:)\s*(0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)", block)
        prefix = 24
        if mask_match:
            prefix = _mask_to_prefix(mask_match.group(1))
        kind = classify_iface(name, ip)
        if kind == "virtual":
            continue
        nics.append(Nic(name=name, ip=ip, prefix=prefix, kind=kind, cidr=f"{ip}/{prefix}"))
    return nics


def parse_ipconfig(text: str) -> list[Nic]:
    nics: list[Nic] = []
    blocks = re.split(r"\r?\n\r?\n", text)
    current_name = "Ethernet"
    for block in blocks:
        name_match = re.search(r"adapter (.+):", block, re.IGNORECASE)
        if name_match:
            current_name = name_match.group(1).strip()
        ip_match = re.search(r"IPv4 Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if not ip_match:
            continue
        ip = ip_match.group(1)
        mask_match = re.search(r"Subnet Mask[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", block)
        prefix = _mask_to_prefix(mask_match.group(1)) if mask_match else 24
        kind = classify_iface(current_name, ip)
        if kind == "virtual":
            continue
        nics.append(
            Nic(name=current_name, ip=ip, prefix=prefix, kind=kind, cidr=f"{ip}/{prefix}")
        )
    return nics


def _mask_to_prefix(mask: str) -> int:
    if mask.lower().startswith("0x"):
        value = int(mask, 16)
        return bin(value).count("1")
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen


def parse_default_gateway_linux(text: str) -> dict[str, str]:
    """Map iface -> gateway from `ip route`."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = re.search(r"default via (\d+\.\d+\.\d+\.\d+) dev (\S+)", line)
        if match:
            found[match.group(2)] = match.group(1)
    return found


def parse_arp_table(text: str) -> list[tuple[str, str]]:
    """Return (ip, hostname) pairs from `arp -a` or `ip neigh`."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    # `ip neigh`: 192.168.1.1 dev wlan0 lladdr aa:bb REACHABLE
    for match in re.finditer(r"(\d+\.\d+\.\d+\.\d+)", text):
        ip = match.group(1)
        if ip in seen:
            continue
        if ip.endswith(".255") or ip.endswith(".0"):
            continue
        seen.add(ip)
        host_match = re.search(rf"\(?{re.escape(ip)}\)?", text)
        hostname = ""
        # `arp -a`: router (192.168.1.1) at ...
        named = re.search(rf"([^\s()]+)\s+\({re.escape(ip)}\)", text)
        if named and named.group(1) != "?":
            hostname = named.group(1)
        elif host_match:
            hostname = ""
        pairs.append((ip, hostname))
    return pairs


def parse_tailscale_status(payload: dict) -> list[Host]:
    hosts: list[Host] = []

    def from_node(node: dict, source: str) -> Host | None:
        ips = node.get("TailscaleIPs") or []
        ipv4 = next((item for item in ips if ":" not in item), None)
        if not ipv4:
            return None
        dns = (node.get("DNSName") or "").rstrip(".")
        name = node.get("HostName") or dns.split(".")[0] or ipv4
        tags = []
        if node.get("Online"):
            tags.append("online")
        else:
            tags.append("offline")
        if node.get("ExitNode"):
            tags.append("exit-node")
        return Host(
            ip=ipv4,
            hostname=name,
            source=source,
            nic="tailscale",
            kind="tailscale",
            online=bool(node.get("Online", True)),
            os=node.get("OS") or "",
            tags=tags,
        )

    self_node = payload.get("Self")
    if isinstance(self_node, dict):
        host = from_node(self_node, "tailscale-self")
        if host:
            host.tags = list(dict.fromkeys([*host.tags, "this-node"]))
            hosts.append(host)

    peers = payload.get("Peer") or {}
    if isinstance(peers, dict):
        for node in peers.values():
            if not isinstance(node, dict):
                continue
            host = from_node(node, "tailscale")
            if host:
                hosts.append(host)
    return hosts


def _linux_nics() -> list[Nic]:
    text = run_cmd(["ip", "-4", "-o", "addr", "show"])
    if text:
        nics = parse_ip_o_addr(text)
    else:
        text = run_cmd(["ifconfig"])
        nics = parse_ifconfig(text or "")
    routes = run_cmd(["ip", "route"])
    if routes:
        gateways = parse_default_gateway_linux(routes)
        for nic in nics:
            nic.gateway = gateways.get(nic.name)
    return nics


def _darwin_nics() -> list[Nic]:
    text = run_cmd(["ifconfig"]) or ""
    return parse_ifconfig(text)


def _windows_nics() -> list[Nic]:
    text = run_cmd(["ipconfig"]) or ""
    return parse_ipconfig(text)


def list_nics() -> list[Nic]:
    system = platform.system()
    if system == "Linux":
        nics = _linux_nics()
    elif system == "Darwin":
        nics = _darwin_nics()
    elif system == "Windows":
        nics = _windows_nics()
    else:
        nics = _linux_nics() or _darwin_nics()

    if not any(n.kind == "local" for n in nics):
        nics.insert(
            0,
            Nic(name="lo", ip="127.0.0.1", prefix=8, kind="local", cidr="127.0.0.1/8"),
        )
    # Deduplicate by ip
    unique: list[Nic] = []
    seen: set[str] = set()
    for nic in nics:
        if nic.ip in seen:
            continue
        seen.add(nic.ip)
        unique.append(nic)
    return unique


def tailscale_binary() -> str | None:
    return shutil.which("tailscale") or shutil.which("tailscale.exe")


def load_tailscale() -> tuple[list[Host], dict]:
    meta = {"available": False, "error": None, "backend": None}
    binary = tailscale_binary()
    if not binary:
        meta["error"] = "Tailscale CLI not found on PATH"
        return [], meta
    text = run_cmd([binary, "status", "--json"], timeout=8)
    if not text:
        meta["error"] = "tailscale status failed (is the daemon running?)"
        return [], meta
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        meta["error"] = "tailscale status returned invalid JSON"
        return [], meta
    meta["available"] = True
    meta["backend"] = payload.get("BackendState")
    return parse_tailscale_status(payload), meta


def neighbors_from_arp() -> list[tuple[str, str]]:
    text = run_cmd(["ip", "neigh"]) or run_cmd(["arp", "-a"]) or ""
    return parse_arp_table(text)


def ping_host(ip: str, timeout: float = 0.4) -> bool:
    system = platform.system()
    if system == "Windows":
        args = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
    else:
        # -c 1 one packet, -W timeout seconds (linux), -W ms on some BSD
        args = ["ping", "-c", "1", "-W", "1", ip]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout + 1.0,
            check=False,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def candidate_hosts_for_nic(nic: Nic, ping: bool = False) -> list[Host]:
    hosts: list[Host] = []
    seen: set[str] = set()

    def add(ip: str, hostname: str = "", source: str = "lan") -> None:
        if ip in seen:
            return
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return
        if addr.is_multicast or addr.is_unspecified:
            return
        seen.add(ip)
        hosts.append(
            Host(
                ip=ip,
                hostname=hostname,
                source=source,
                nic=nic.name,
                kind=nic.kind,
                online=True,
            )
        )

    add(nic.ip, hostname=socket.gethostname(), source="self")
    if nic.kind == "local":
        add("127.0.0.1", hostname="localhost", source="self")
        return hosts

    if nic.gateway:
        add(nic.gateway, hostname="gateway", source="gateway")

    if nic.kind == "tailscale":
        peers, _meta = load_tailscale()
        for peer in peers:
            add(peer.ip, hostname=peer.hostname, source=peer.source)
            # keep richer metadata
            for existing in hosts:
                if existing.ip == peer.ip:
                    existing.os = peer.os
                    existing.online = peer.online
                    existing.tags = peer.tags
                    existing.kind = "tailscale"
        return hosts

    try:
        net = constrain_network(nic.cidr, nic.ip)
    except ValueError:
        return hosts

    for ip, hostname in neighbors_from_arp():
        try:
            if ipaddress.ip_address(ip) in net:
                add(ip, hostname=hostname, source="arp")
        except ValueError:
            continue

    # For small subnets, include every address so a connect-scan can find quiet hosts.
    if net.prefixlen >= 24 and net.num_addresses <= 256:
        for addr in net.hosts():
            ip = str(addr)
            if ping and ip not in seen and not ping_host(ip):
                continue
            add(ip, source="subnet")

    return hosts


def collect_targets(kinds: Iterable[str] | None = None) -> dict:
    wanted = set(kinds or ("local", "wifi", "ethernet", "tailscale"))
    nics = [
        n
        for n in list_nics()
        if n.kind in wanted or (n.kind == "ethernet" and "wifi" in wanted)
    ]
    ts_hosts, ts_meta = load_tailscale() if "tailscale" in wanted else ([], {"available": False})

    groups: dict[str, dict] = {}
    for nic in nics:
        key = nic.kind
        if key == "ethernet":
            key = "wifi"
        bucket = groups.setdefault(
            key,
            {
                "kind": key,
                "nics": [],
                "hosts": [],
            },
        )
        bucket["nics"].append(nic.to_dict())
        for host in candidate_hosts_for_nic(nic, ping=False):
            bucket["hosts"].append(host.to_dict())

    if "tailscale" in wanted:
        bucket = groups.setdefault(
            "tailscale",
            {"kind": "tailscale", "nics": [], "hosts": []},
        )
        existing_ips = {h["ip"] for h in bucket["hosts"]}
        for host in ts_hosts:
            if host.ip not in existing_ips:
                bucket["hosts"].append(host.to_dict())
                existing_ips.add(host.ip)
        bucket["tailscale"] = ts_meta

    # Dedup hosts inside each group
    for bucket in groups.values():
        unique = []
        seen: set[str] = set()
        for host in bucket["hosts"]:
            if host["ip"] in seen:
                continue
            seen.add(host["ip"])
            unique.append(host)
        bucket["hosts"] = unique

    return {
        "nics": [n.to_dict() for n in list_nics()],
        "groups": groups,
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "tailscale": ts_meta if "tailscale" in wanted else {"available": False},
        "user": os.environ.get("USER") or os.environ.get("USERNAME") or "",
    }
