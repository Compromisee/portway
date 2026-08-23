import json
from pathlib import Path

from portway.discovery import (
    classify_iface,
    constrain_network,
    is_tailscale_ip,
    parse_arp_table,
    parse_default_gateway_linux,
    parse_ifconfig,
    parse_ip_o_addr,
    parse_ipconfig,
    parse_tailscale_status,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_classify_tailscale_by_ip():
    assert classify_iface("utun4", "100.92.14.8") == "tailscale"
    assert is_tailscale_ip("100.64.0.1")
    assert not is_tailscale_ip("192.168.1.4")


def test_classify_wifi_and_local():
    assert classify_iface("wlp3s0", "192.168.1.20") == "wifi"
    assert classify_iface("lo", "127.0.0.1") == "local"
    assert classify_iface("eth0", "10.0.0.5") == "ethernet"
    assert classify_iface("docker0", "172.17.0.1") == "virtual"


def test_constrain_caps_large_prefix():
    net = constrain_network("10.0.0.0/8", "10.4.2.9")
    assert str(net) == "10.4.2.0/24"


def test_constrain_rejects_public():
    try:
        constrain_network("8.8.8.0/24", "8.8.8.8")
    except ValueError as exc:
        assert "non-local" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_ip_o_addr():
    text = (
        "1: lo    inet 127.0.0.1/8 scope host lo\n"
        "2: wlp3s0    inet 192.168.1.42/24 brd 192.168.1.255 scope global\n"
        "3: tailscale0    inet 100.101.20.3/32 scope global\n"
        "4: docker0    inet 172.17.0.1/16 scope global\n"
    )
    nics = parse_ip_o_addr(text)
    kinds = {n.name: n.kind for n in nics}
    assert kinds["lo"] == "local"
    assert kinds["wlp3s0"] == "wifi"
    assert kinds["tailscale0"] == "tailscale"
    assert "docker0" not in kinds


def test_parse_ifconfig():
    text = """\
lo0: flags=8049 mtu 16384
	inet 127.0.0.1 netmask 0xff000000
en0: flags=8863 mtu 1500
	inet 192.168.0.24 netmask 0xffffff00 broadcast 192.168.0.255
"""
    nics = parse_ifconfig(text)
    assert nics[0].kind == "local"
    assert nics[1].name == "en0"
    assert nics[1].prefix == 24


def test_parse_ipconfig():
    text = """
Wireless LAN adapter Wi-Fi:

   IPv4 Address. . . . . . . . . . . : 192.168.1.77
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
"""
    nics = parse_ipconfig(text)
    assert len(nics) == 1
    assert nics[0].kind == "wifi"
    assert nics[0].prefix == 24


def test_parse_gateway_and_arp():
    routes = "default via 192.168.1.1 dev wlp3s0 proto dhcp\n"
    assert parse_default_gateway_linux(routes)["wlp3s0"] == "192.168.1.1"
    arp = (
        "router (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on wlan0\n"
        "192.168.1.14 dev wlan0 lladdr 11:22:33:44:55:66 REACHABLE\n"
    )
    pairs = parse_arp_table(arp)
    ips = [ip for ip, _name in pairs]
    assert "192.168.1.1" in ips
    assert "192.168.1.14" in ips


def test_parse_tailscale_status():
    payload = json.loads((FIXTURES / "tailscale_status.json").read_text())
    hosts = parse_tailscale_status(payload)
    ips = {h.ip: h for h in hosts}
    assert "100.101.20.3" in ips
    assert ips["100.101.20.3"].hostname == "studio"
    assert "this-node" in ips["100.101.20.3"].tags
    assert ips["100.88.12.9"].hostname == "nas"
    assert ips["100.88.12.9"].online is True
    assert ips["100.70.1.4"].online is False
