"""Well-known ports, scan profiles, and URL helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ServiceHint:
    key: str
    label: str
    scheme: str | None = None
    group: str = "other"

    def to_dict(self) -> dict:
        return asdict(self)


CATALOG: dict[int, ServiceHint] = {
    20: ServiceHint("ftp-data", "FTP data", group="remote"),
    21: ServiceHint("ftp", "FTP", group="remote"),
    22: ServiceHint("ssh", "SSH", group="remote"),
    23: ServiceHint("telnet", "Telnet", group="remote"),
    25: ServiceHint("smtp", "SMTP", group="system"),
    53: ServiceHint("dns", "DNS", group="system"),
    80: ServiceHint("http", "HTTP", "http", "web"),
    110: ServiceHint("pop3", "POP3", group="system"),
    111: ServiceHint("rpcbind", "RPCbind", group="system"),
    123: ServiceHint("ntp", "NTP", group="system"),
    135: ServiceHint("msrpc", "MSRPC", group="system"),
    139: ServiceHint("netbios", "NetBIOS", group="system"),
    143: ServiceHint("imap", "IMAP", group="system"),
    161: ServiceHint("snmp", "SNMP", group="system"),
    389: ServiceHint("ldap", "LDAP", group="system"),
    443: ServiceHint("https", "HTTPS", "https", "web"),
    445: ServiceHint("smb", "SMB", group="remote"),
    465: ServiceHint("smtps", "SMTPS", group="system"),
    587: ServiceHint("submission", "SMTP submission", group="system"),
    631: ServiceHint("ipp", "IPP / CUPS", "http", "system"),
    636: ServiceHint("ldaps", "LDAPS", group="system"),
    993: ServiceHint("imaps", "IMAPS", group="system"),
    995: ServiceHint("pop3s", "POP3S", group="system"),
    1433: ServiceHint("mssql", "Microsoft SQL", group="data"),
    1521: ServiceHint("oracle", "Oracle DB", group="data"),
    1723: ServiceHint("pptp", "PPTP", group="remote"),
    1883: ServiceHint("mqtt", "MQTT", group="dev"),
    2049: ServiceHint("nfs", "NFS", group="remote"),
    2082: ServiceHint("cpanel", "cPanel", "http", "web"),
    2083: ServiceHint("cpanel-ssl", "cPanel TLS", "https", "web"),
    2181: ServiceHint("zookeeper", "ZooKeeper", group="data"),
    2222: ServiceHint("ssh-alt", "SSH alt", group="remote"),
    2375: ServiceHint("docker", "Docker", group="dev"),
    2376: ServiceHint("docker-tls", "Docker TLS", group="dev"),
    2379: ServiceHint("etcd", "etcd", "http", "dev"),
    2480: ServiceHint("orientdb", "OrientDB", "http", "data"),
    3000: ServiceHint("node", "Node / React", "http", "dev"),
    3001: ServiceHint("node-alt", "Dev server", "http", "dev"),
    3002: ServiceHint("dev", "Dev server", "http", "dev"),
    3128: ServiceHint("squid", "Squid", group="web"),
    3306: ServiceHint("mysql", "MySQL", group="data"),
    3389: ServiceHint("rdp", "RDP", group="remote"),
    4000: ServiceHint("dev", "Dev server", "http", "dev"),
    4040: ServiceHint("spark", "Spark UI", "http", "dev"),
    4173: ServiceHint("vite-preview", "Vite preview", "http", "dev"),
    4200: ServiceHint("angular", "Angular", "http", "dev"),
    4444: ServiceHint("selenium", "Selenium", "http", "dev"),
    4567: ServiceHint("sinatra", "Sinatra / HTTP", "http", "dev"),
    5000: ServiceHint("flask", "Flask", "http", "dev"),
    5001: ServiceHint("http-alt", "HTTP alt", "http", "dev"),
    5050: ServiceHint("http-alt", "HTTP alt", "http", "dev"),
    5173: ServiceHint("vite", "Vite", "http", "dev"),
    5432: ServiceHint("postgres", "PostgreSQL", group="data"),
    5500: ServiceHint("live-server", "Live Server", "http", "dev"),
    5601: ServiceHint("kibana", "Kibana", "http", "data"),
    5672: ServiceHint("amqp", "RabbitMQ", group="data"),
    5800: ServiceHint("vnc-http", "VNC HTTP", "http", "remote"),
    5900: ServiceHint("vnc", "VNC", group="remote"),
    5901: ServiceHint("vnc-1", "VNC :1", group="remote"),
    5984: ServiceHint("couchdb", "CouchDB", "http", "data"),
    5985: ServiceHint("winrm", "WinRM", "http", "remote"),
    6379: ServiceHint("redis", "Redis", group="data"),
    6443: ServiceHint("k8s", "Kubernetes API", "https", "dev"),
    6666: ServiceHint("irc", "IRC", group="other"),
    7001: ServiceHint("weblogic", "WebLogic", "http", "web"),
    7474: ServiceHint("neo4j", "Neo4j", "http", "data"),
    7687: ServiceHint("neo4j-bolt", "Neo4j Bolt", group="data"),
    8000: ServiceHint("django", "Django / HTTP", "http", "dev"),
    8001: ServiceHint("http-alt", "HTTP alt", "http", "dev"),
    8008: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8010: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8069: ServiceHint("odoo", "Odoo", "http", "web"),
    8080: ServiceHint("http-proxy", "HTTP / Tomcat", "http", "web"),
    8081: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8082: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8086: ServiceHint("influx", "InfluxDB", "http", "data"),
    8088: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8090: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8096: ServiceHint("jellyfin", "Jellyfin", "http", "web"),
    8161: ServiceHint("activemq", "ActiveMQ", "http", "data"),
    8181: ServiceHint("http-alt", "HTTP alt", "http", "web"),
    8200: ServiceHint("minio", "MinIO console", "http", "data"),
    8443: ServiceHint("https-alt", "HTTPS alt", "https", "web"),
    8500: ServiceHint("consul", "Consul", "http", "dev"),
    8501: ServiceHint("streamlit", "Streamlit", "http", "dev"),
    8530: ServiceHint("wsus", "WSUS", "http", "system"),
    8834: ServiceHint("nessus", "Nessus", "https", "system"),
    8888: ServiceHint("jupyter", "Jupyter", "http", "dev"),
    8889: ServiceHint("jupyter-alt", "Jupyter alt", "http", "dev"),
    8983: ServiceHint("solr", "Solr", "http", "data"),
    9000: ServiceHint("portainer", "Portainer / Sonar", "http", "dev"),
    9001: ServiceHint("supervisor", "Supervisor", "http", "dev"),
    9090: ServiceHint("prometheus", "Prometheus", "http", "dev"),
    9091: ServiceHint("transmission", "Transmission", "http", "web"),
    9092: ServiceHint("kafka", "Kafka", group="data"),
    9100: ServiceHint("node-exporter", "Node exporter", "http", "dev"),
    9200: ServiceHint("elasticsearch", "Elasticsearch", "http", "data"),
    9300: ServiceHint("es-transport", "Elastic transport", group="data"),
    9418: ServiceHint("git", "Git", group="dev"),
    9443: ServiceHint("https-alt", "HTTPS alt", "https", "web"),
    10250: ServiceHint("kubelet", "Kubelet", "https", "dev"),
    11211: ServiceHint("memcached", "Memcached", group="data"),
    15672: ServiceHint("rabbitmq-ui", "RabbitMQ UI", "http", "data"),
    25565: ServiceHint("minecraft", "Minecraft", group="other"),
    27017: ServiceHint("mongo", "MongoDB", group="data"),
    27018: ServiceHint("mongo-shard", "MongoDB shard", group="data"),
    28017: ServiceHint("mongo-http", "MongoDB HTTP", "http", "data"),
    32400: ServiceHint("plex", "Plex", "http", "web"),
}

QUICK_PORTS: tuple[int, ...] = (
    22,
    80,
    443,
    3000,
    5000,
    5173,
    8000,
    8080,
    8443,
    8888,
)

DEVELOPER_PORTS: tuple[int, ...] = tuple(sorted(CATALOG.keys()))

PROFILES = {
    "quick": {
        "label": "Quick",
        "hint": "SSH plus common web ports",
        "ports": QUICK_PORTS,
    },
    "developer": {
        "label": "Developer",
        "hint": "Web, Flask, Vite, databases, remote access",
        "ports": DEVELOPER_PORTS,
    },
    "deep": {
        "label": "All ports",
        "hint": "Every TCP port on a single host",
        "ports": tuple(range(1, 65536)),
    },
}


def hint_for(port: int, http_detected: bool = False) -> ServiceHint:
    if port in CATALOG:
        return CATALOG[port]
    if http_detected:
        return ServiceHint("http", "HTTP", "http", "web")
    return ServiceHint("unknown", "Unknown", None, "other")


def url_for(host: str, port: int, scheme: str | None = None) -> str | None:
    """Build a browser URL, or None when the service is not HTTP(S)."""
    hint = hint_for(port)
    chosen = scheme or hint.scheme
    if chosen not in {"http", "https"}:
        return None
    if not host:
        return None
    default = 443 if chosen == "https" else 80
    if port == default:
        return f"{chosen}://{host}/"
    return f"{chosen}://{host}:{port}/"


def ports_for_profile(name: str) -> tuple[int, ...]:
    profile = PROFILES.get(name)
    if profile is None:
        raise ValueError(f"Unknown scan profile: {name}")
    return profile["ports"]


def parse_port_list(text: str) -> list[int]:
    """Parse '80,443,8000-8010' into a de-duplicated sorted list."""
    found: set[int] = set()
    for chunk in text.split(","):
        piece = chunk.strip()
        if not piece:
            continue
        if "-" in piece:
            left, right = piece.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            if start < 1 or end > 65535:
                raise ValueError("Ports must be between 1 and 65535")
            found.update(range(start, end + 1))
        else:
            port = int(piece)
            if port < 1 or port > 65535:
                raise ValueError("Ports must be between 1 and 65535")
            found.add(port)
    return sorted(found)
