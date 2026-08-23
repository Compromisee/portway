import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Chip,
  Input,
  Label,
  Modal,
  Spinner,
  Switch,
  TextField,
} from "@heroui/react";
import {
  Copy,
  DoorOpen,
  KeyRound,
  Laptop,
  Radar,
  RefreshCw,
  Router,
  Search,
  Share2,
  Wifi,
} from "lucide-react";
import { api } from "./api";
import type { OpenItem, Snapshot, TokenRow } from "./types";

const KIND_META: Record<string, { label: string; icon: typeof Wifi; className: string }> = {
  local: { label: "This machine", icon: Laptop, className: "text-amber-300" },
  wifi: { label: "Wi-Fi / LAN", icon: Wifi, className: "text-teal-300" },
  ethernet: { label: "Ethernet", icon: Router, className: "text-teal-300" },
  tailscale: { label: "Tailscale", icon: Share2, className: "text-violet-300" },
};

function kindOf(item: OpenItem) {
  return item.host_meta?.kind || "wifi";
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [items, setItems] = useState<OpenItem[]>([]);
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("developer");
  const [filterKind, setFilterKind] = useState("all");
  const [webOnly, setWebOnly] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [status, setStatus] = useState("Ready to sweep the harbor.");
  const [toast, setToast] = useState("");
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tokenTarget, setTokenTarget] = useState("");
  const [tokenValue, setTokenValue] = useState("");
  const [tokenStyle, setTokenStyle] = useState("query");
  const [pendingOpen, setPendingOpen] = useState<OpenItem | null>(null);

  const flash = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2800);
  };

  const loadSnapshot = useCallback(async () => {
    try {
      const data = await api.snapshot();
      setSnapshot(data);
    } catch {
      setStatus("Flask API is not reachable. Start it with portway serve.");
    }
  }, []);

  const loadTokens = useCallback(async () => {
    try {
      const data = await api.tokens();
      setTokens(data.tokens || []);
    } catch {
      setTokens([]);
    }
  }, []);

  useEffect(() => {
    void loadSnapshot();
    void loadTokens();
  }, [loadSnapshot, loadTokens]);

  useEffect(() => {
    if (!scanning) return;
    const timer = window.setInterval(async () => {
      const state = await api.status();
      setItems(state.items || []);
      const progress = state.progress || {};
      if (state.running) {
        setStatus(
          `Sweeping ${progress.current_host || ""}:${progress.current_port || ""} · ${state.count} open`,
        );
      } else {
        setScanning(false);
        setStatus(`Done. ${state.count} open ports.`);
      }
    }, 400);
    return () => window.clearInterval(timer);
  }, [scanning]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (filterKind !== "all" && kindOf(item) !== filterKind) return false;
      if (webOnly && !item.openable) return false;
      if (!q) return true;
      return [
        item.host,
        item.label,
        item.key,
        String(item.port),
        item.url || "",
        item.host_meta?.hostname || "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [items, filterKind, query, webOnly]);

  const grouped = useMemo(() => {
    const map = new Map<string, OpenItem[]>();
    for (const item of visible) {
      const list = map.get(item.host) || [];
      list.push(item);
      map.set(item.host, list);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [visible]);

  async function startScan(extra?: { profile?: string; host?: string }) {
    if (scanning) {
      await api.cancelScan();
      setScanning(false);
      setStatus("Scan cancelled.");
      return;
    }
    const chosen = extra?.profile || profile;
    if (chosen === "deep" && !extra?.host) {
      flash("All-port scans run on one host. Use All ports on a result row.");
      return;
    }
    setItems([]);
    const result = await api.startScan({
      networks: ["local", "wifi", "tailscale"],
      profile: chosen,
      host: extra?.host || null,
      fingerprint: true,
    });
    if (!result.ok) {
      setStatus(result.error || "Scan failed");
      flash(result.error || "Scan failed");
      return;
    }
    setScanning(true);
    setStatus(`Sweeping ${result.hosts} hosts · ${result.ports} ports`);
  }

  async function openItem(item: OpenItem, token?: string) {
    const result = await api.open({
      host: item.host,
      port: item.port,
      scheme: item.scheme,
      token,
      style: tokenStyle,
      save: Boolean(token),
    });
    if (result.needs_token) {
      setPendingOpen(item);
      setTokenTarget(result.target || `${item.host}:${item.port}`);
      setTokenValue("");
      setTokenOpen(true);
      return;
    }
    if (result.ok) {
      flash(`Opened ${result.url}`);
      setTokenOpen(false);
      setPendingOpen(null);
      await loadTokens();
    } else {
      flash(result.error || "Could not open");
    }
  }

  async function saveTokenOnly() {
    if (!tokenTarget || !tokenValue.trim()) return;
    const result = await api.saveToken({
      target: tokenTarget,
      token: tokenValue.trim(),
      style: tokenStyle,
    });
    if (!result.ok) {
      flash(result.error || "Could not save token");
      return;
    }
    flash(`Saved token for ${tokenTarget}`);
    setTokenOpen(false);
    await loadTokens();
    if (pendingOpen) {
      await openItem(pendingOpen, tokenValue.trim());
    }
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      flash(`Copied ${text}`);
    } catch {
      flash(text);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-4 border-b border-white/10 px-5 py-3">
        <div className="flex items-center gap-3 min-w-48">
          <span className="mark" />
          <div>
            <div className="font-display text-xl tracking-wide">Portway</div>
            <div className="text-xs text-white/50">HeroUI deck · Flask API</div>
          </div>
        </div>
        <div className="relative flex-1 min-w-56 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter hosts, ports, Flask, Vite..."
            className="w-full pl-9"
          />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={profile}
            onChange={(event) => setProfile(event.target.value)}
            className="rounded-full border border-white/15 bg-white/5 px-3 py-2 text-sm"
          >
            <option value="quick">Quick</option>
            <option value="developer">Developer</option>
            <option value="deep">All ports</option>
          </select>
          <Button variant="primary" onPress={() => void startScan()} isPending={scanning}>
            {scanning ? <Spinner size="sm" /> : <Radar className="h-4 w-4" />}
            {scanning ? "Stop" : "Scan"}
          </Button>
        </div>
      </header>

      <div className="grid min-h-[calc(100vh-118px)] grid-cols-1 md:grid-cols-[240px_1fr]">
        <aside className="space-y-3 border-r border-white/10 p-4">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-white/45">
            Piers
            <Button isIconOnly size="sm" variant="ghost" onPress={() => void loadSnapshot()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
          {(["local", "wifi", "tailscale"] as const).map((kind) => {
            const meta = KIND_META[kind];
            const Icon = meta.icon;
            const group = snapshot?.groups?.[kind];
            const nic = group?.nics?.[0];
            const count = items.filter((item) => kindOf(item) === kind).length;
            return (
              <button
                key={kind}
                type="button"
                onClick={() => setFilterKind(filterKind === kind ? "all" : kind)}
                className={`w-full rounded-xl border px-3 py-3 text-left ${
                  filterKind === kind ? "border-amber-400/40 bg-amber-400/10" : "border-white/10 bg-white/5"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`grid h-8 w-8 place-items-center rounded-lg bg-black/20 ${meta.className}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm">{meta.label}</span>
                    <span className="block truncate font-mono text-[11px] text-white/45">
                      {nic ? `${nic.ip}/${nic.prefix}` : "waiting"}
                    </span>
                  </span>
                  <span className="font-mono text-xs text-white/60">{count || group?.hosts?.length || 0}</span>
                </div>
              </button>
            );
          })}
          <div className="pt-4 text-xs text-white/45">
            Saved tokens: {tokens.length}
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => {
                setPendingOpen(null);
                setTokenTarget("");
                setTokenValue("");
                setTokenOpen(true);
              }}
            >
              add
            </button>
          </div>
        </aside>

        <main className="flex flex-col gap-4 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {[
                ["all", "All piers"],
                ["local", "This machine"],
                ["wifi", "Wi-Fi"],
                ["tailscale", "Tailscale"],
              ].map(([id, label]) => (
                <Chip
                  key={id}
                  size="sm"
                  color={filterKind === id ? "accent" : "default"}
                  variant={filterKind === id ? "primary" : "soft"}
                  onClick={() => setFilterKind(id)}
                >
                  {label}
                </Chip>
              ))}
            </div>
            <Switch isSelected={webOnly} onChange={setWebOnly}>
              <span className="text-sm text-white/70">Openable only</span>
            </Switch>
          </div>

          {snapshot?.tailscale?.available === false && snapshot.tailscale.error && (
            <Card>
              <Card.Content className="text-sm text-violet-200">
                Tailscale CLI not ready. {snapshot.tailscale.error} Wi-Fi and this machine still scan.
              </Card.Content>
            </Card>
          )}

          {grouped.length === 0 ? (
            <div className="grid min-h-96 place-items-center rounded-3xl border border-dashed border-white/15 text-center">
              <div className="max-w-md px-6">
                <DoorOpen className="mx-auto mb-3 h-8 w-8 text-amber-300" />
                <h2 className="font-display text-3xl">{scanning ? "Sweeping the harbor" : "No open doors yet"}</h2>
                <p className="mt-2 text-white/55">
                  Scan this machine, the Wi-Fi subnet, and Tailscale. Protected IPs ask for a token before they open.
                </p>
              </div>
            </div>
          ) : (
            grouped.map(([ip, ports]) => {
              const meta = ports[0].host_meta || {};
              const kind = kindOf(ports[0]);
              const info = KIND_META[kind] || KIND_META.wifi;
              const Icon = info.icon;
              return (
                <Card key={ip}>
                  <Card.Header className="flex items-center gap-3">
                    <span className={`grid h-9 w-9 place-items-center rounded-lg bg-black/20 ${info.className}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="flex-1">
                      <Card.Title>{meta.hostname || ip}</Card.Title>
                      <Card.Description>
                        {ip}
                        {meta.os ? ` · ${meta.os}` : ""} · {info.label}
                      </Card.Description>
                    </div>
                    <Button size="sm" variant="ghost" onPress={() => void startScan({ profile: "deep", host: ip })}>
                      All ports
                    </Button>
                  </Card.Header>
                  <Card.Content className="space-y-2">
                    {ports
                      .slice()
                      .sort((a, b) => a.port - b.port)
                      .map((item) => (
                        <div
                          key={`${item.host}:${item.port}`}
                          className="grid grid-cols-[72px_1fr_auto] items-center gap-3 rounded-xl px-1 py-2 hover:bg-white/5"
                        >
                          <div className="font-mono text-amber-300">{item.port}</div>
                          <div>
                            <div className="text-sm">{item.label}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-white/45">
                              <Chip size="sm" variant="soft">
                                {item.group}
                              </Chip>
                              {item.protected ? (
                                <Chip size="sm" color={item.has_token ? "success" : "warning"} variant="soft">
                                  {item.has_token ? "token saved" : "needs token"}
                                </Chip>
                              ) : null}
                              <span>{item.url || `${item.host}:${item.port}`}</span>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            {item.openable ? (
                              <Button size="sm" variant="secondary" onPress={() => void openItem(item)}>
                                <DoorOpen className="h-4 w-4" />
                                Open
                              </Button>
                            ) : null}
                            {item.protected || item.openable ? (
                              <Button
                                size="sm"
                                variant="ghost"
                                onPress={() => {
                                  setPendingOpen(item);
                                  setTokenTarget(`${item.host}:${item.port}`);
                                  setTokenValue("");
                                  setTokenOpen(true);
                                }}
                              >
                                <KeyRound className="h-4 w-4" />
                                Token
                              </Button>
                            ) : null}
                            <Button
                              size="sm"
                              variant="ghost"
                              onPress={() => void copyText(item.url || `${item.host}:${item.port}`)}
                            >
                              <Copy className="h-4 w-4" />
                              Copy
                            </Button>
                          </div>
                        </div>
                      ))}
                  </Card.Content>
                </Card>
              );
            })
          )}
        </main>
      </div>

      <footer className="flex items-center justify-between border-t border-white/10 px-5 py-3 text-xs text-white/50">
        <span>{status}</span>
        <span className="font-mono">
          {visible.length} open · {visible.filter((item) => item.openable).length} openable
        </span>
      </footer>

      {toast ? (
        <div className="fixed bottom-14 right-4 rounded-xl border border-white/10 bg-[#141b24] px-3 py-2 text-sm shadow-xl">
          {toast}
        </div>
      ) : null}

      <Modal isOpen={tokenOpen} onOpenChange={setTokenOpen}>
        <Modal.Backdrop>
          <Modal.Container>
            <Modal.Dialog>
              <Modal.Header>
                <Modal.Heading>Protected address</Modal.Heading>
              </Modal.Header>
              <Modal.Body className="space-y-3">
                <p className="text-sm text-white/60">
                  Jupyter and other locked services need a token. It is stored only on this machine.
                </p>
                <TextField
                  value={tokenTarget}
                  onChange={setTokenTarget}
                  name="target"
                >
                  <Label>IP or host:port</Label>
                  <Input placeholder="127.0.0.1:8888" />
                </TextField>
                <TextField
                  value={tokenValue}
                  onChange={setTokenValue}
                  name="token"
                  type="password"
                >
                  <Label>Token</Label>
                  <Input placeholder="paste token" />
                </TextField>
                <label className="block text-sm">
                  <span className="mb-1 block text-white/70">Attach as</span>
                  <select
                    value={tokenStyle}
                    onChange={(event) => setTokenStyle(event.target.value)}
                    className="w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2"
                  >
                    <option value="query">Query string (?token=)</option>
                    <option value="bearer">Authorization Bearer</option>
                    <option value="header">Authorization header</option>
                  </select>
                </label>
              </Modal.Body>
              <Modal.Footer>
                <Button slot="close" variant="ghost">
                  Cancel
                </Button>
                <Button variant="primary" onPress={() => void saveTokenOnly()}>
                  Save token
                </Button>
              </Modal.Footer>
            </Modal.Dialog>
          </Modal.Container>
        </Modal.Backdrop>
      </Modal>
    </div>
  );
}
