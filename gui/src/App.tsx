import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Chip, Input, Label, Modal, Spinner, Switch, TextField } from "@heroui/react";
import { Copy, DoorOpen, KeyRound, Laptop, Radar, Search, Share2, Trash2, Wifi } from "lucide-react";
import { Dropdown } from "./Dropdown";
import { api } from "./api";
import type { HostMeta, OpenItem, Snapshot, TokenRow } from "./types";

const KIND_META: Record<string, { label: string; icon: typeof Wifi; className: string }> = {
  local: { label: "This computer", icon: Laptop, className: "text-amber-300" },
  wifi: { label: "Wi-Fi", icon: Wifi, className: "text-teal-300" },
  ethernet: { label: "Wi-Fi", icon: Wifi, className: "text-teal-300" },
  tailscale: { label: "Tailscale", icon: Share2, className: "text-violet-300" },
};

const PROFILES = [
  { id: "quick", label: "Quick scan", hint: "Common web ports and SSH" },
  { id: "developer", label: "Developer", hint: "Flask, Vite, databases" },
  { id: "deep", label: "Every port", hint: "One computer at a time" },
];

const STYLES = [
  { id: "query", label: "Add to the link", hint: "?token=" },
  { id: "bearer", label: "Bearer header", hint: "Authorization: Bearer" },
  { id: "header", label: "Raw header", hint: "Authorization" },
];

function kindOf(item: { host_meta?: HostMeta; kind?: string }) {
  return item.host_meta?.kind || item.kind || "wifi";
}

function stateLabel(state: string, scanning: boolean, hasPorts: boolean) {
  if (state === "scanning" || (scanning && !hasPorts && state !== "open")) return "Checking";
  if (hasPorts || state === "open") return "Has services";
  if (state === "live" || state === "known") return "Found";
  if (state === "quiet") return "Nothing open";
  return "";
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [items, setItems] = useState<OpenItem[]>([]);
  const [hosts, setHosts] = useState<HostMeta[]>([]);
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("developer");
  const [filterKind, setFilterKind] = useState("all");
  const [webOnly, setWebOnly] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState<Record<string, number | string>>({});
  const [status, setStatus] = useState("Looking at your networks.");
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
    const data = await api.snapshot();
    setSnapshot(data);
    return data;
  }, []);

  const loadTokens = useCallback(async () => {
    const data = await api.tokens();
    setTokens(data.tokens || []);
  }, []);

  const applyStatus = useCallback(async () => {
    const state = await api.status();
    setItems(state.items || []);
    setHosts(state.hosts || []);
    setProgress(state.progress || {});
    if (state.snapshot) setSnapshot(state.snapshot);
    setScanning(state.running);
    const prog = state.progress || {};
    if (state.running && state.phase === "discover") {
      setStatus(`Looking for computers on the network (${prog.done || 0}/${prog.total || 0}).`);
    } else if (state.running) {
      setStatus(`Checking ${prog.current_host || "hosts"} · ${state.count} services found.`);
    } else if (state.phase === "done") {
      setStatus(`Finished. ${state.count} open services on ${state.hosts?.length || 0} computers.`);
    }
    return state;
  }, []);

  async function startScan(extra?: { profile?: string; host?: string }) {
    if (scanning) {
      await api.cancelScan();
      setScanning(false);
      setStatus("Stopped.");
      return;
    }
    const chosen = extra?.profile || profile;
    if (chosen === "deep" && !extra?.host) {
      flash("Pick a computer first, then use Check every port.");
      return;
    }
    setItems([]);
    setHosts([]);
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
    setStatus("Starting.");
  }

  useEffect(() => {
    document.title = "Portway — Find open ports on Wi-Fi and Tailscale";
    void (async () => {
      try {
        await loadSnapshot();
        await loadTokens();
        await startScan({ profile: "quick" });
      } catch {
        setStatus("The Portway server is not running. Start it with portway serve.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!scanning) return;
    const timer = window.setInterval(() => {
      void applyStatus();
    }, 350);
    return () => window.clearInterval(timer);
  }, [scanning, applyStatus]);

  const pct = Number(progress.total) ? Number(progress.done) / Number(progress.total) : scanning ? 0.08 : 0;

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (filterKind !== "all" && kindOf(item) !== filterKind) return false;
      if (webOnly && !item.openable) return false;
      if (!q) return true;
      return [item.host, item.label, item.key, String(item.port), item.url || "", item.host_meta?.hostname || ""]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [items, filterKind, query, webOnly]);

  const hostCards = useMemo(() => {
    const map = new Map<string, { meta: HostMeta; ports: OpenItem[] }>();
    for (const host of hosts) {
      if (!host.ip) continue;
      if (filterKind !== "all" && (host.kind || "wifi") !== filterKind) continue;
      map.set(host.ip, { meta: host, ports: [] });
    }
    for (const item of visibleItems) {
      const current = map.get(item.host) || { meta: { ip: item.host, ...(item.host_meta || {}) }, ports: [] };
      current.ports.push(item);
      if (item.host_meta) current.meta = { ...current.meta, ...item.host_meta };
      map.set(item.host, current);
    }
    const rows = Array.from(map.values()).filter((row) => {
      if (webOnly && row.ports.every((item) => !item.openable) && row.ports.length) return false;
      const q = query.trim().toLowerCase();
      if (!q) return true;
      return `${row.meta.ip} ${row.meta.hostname || ""}`.toLowerCase().includes(q) || row.ports.length > 0;
    });
    rows.sort((a, b) => String(a.meta.ip).localeCompare(String(b.meta.ip), undefined, { numeric: true }));
    return rows;
  }, [hosts, visibleItems, filterKind, webOnly, query]);

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
    if (pendingOpen) await openItem(pendingOpen, tokenValue.trim());
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
    <div className="shell">
      <header className="topbar">
        <div className="flex items-center gap-3">
          <span className="mark" aria-hidden="true" />
          <div>
            <div className="font-display text-[22px] tracking-wide">Portway</div>
            <div className="text-xs text-white/50">Find open ports on Wi-Fi and Tailscale</div>
          </div>
        </div>
        <div className="search-wrap">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search a computer, port, or app"
          />
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Dropdown label="How deep" value={profile} options={PROFILES} onChange={setProfile} />
          <Button variant="primary" onPress={() => void startScan()} isPending={scanning}>
            {scanning ? <Spinner size="sm" /> : <Radar className="h-4 w-4" />}
            {scanning ? "Stop" : "Find services"}
          </Button>
        </div>
      </header>

      <div className="progress" aria-hidden="true">
        <i style={{ width: `${Math.max(0, Math.min(100, pct * 100))}%` }} />
      </div>

      <div className="body">
        <aside className="pane side space-y-4">
          <div className="text-[11px] uppercase tracking-[0.16em] text-white/45">Where to look</div>
          {(["local", "wifi", "tailscale"] as const).map((kind) => {
            const meta = KIND_META[kind];
            const Icon = meta.icon;
            const group = snapshot?.groups?.[kind];
            const nic = group?.nics?.[0];
            const count = hosts.filter((host) => (host.kind || "wifi") === kind).length;
            return (
              <button
                key={kind}
                type="button"
                className={`pier ${filterKind === kind ? "on" : ""}`}
                onClick={() => setFilterKind(filterKind === kind ? "all" : kind)}
              >
                <div className="flex items-center gap-3">
                  <span className={`grid h-10 w-10 place-items-center rounded-xl bg-black/25 ${meta.className}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm">{meta.label}</span>
                    <span className="block truncate font-mono text-[11px] text-white/45">
                      {nic ? nic.ip : "Not connected"}
                    </span>
                  </span>
                  <span className="font-mono text-xs text-white/60">{count}</span>
                </div>
              </button>
            );
          })}

          <Switch isSelected={webOnly} onChange={setWebOnly}>
            <span className="text-sm text-white/70">Only sites I can open</span>
          </Switch>

          <div className="rounded-2xl border border-white/10 p-4">
            <div className="mb-3 text-[11px] uppercase tracking-[0.16em] text-white/45">Access tokens</div>
            {tokens.length === 0 ? (
              <p className="text-sm text-white/45">Needed for locked apps such as Jupyter.</p>
            ) : (
              <ul className="space-y-2">
                {tokens.map((row) => (
                  <li key={row.target} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate font-mono text-xs">{row.target}</span>
                    <Button
                      isIconOnly
                      size="sm"
                      variant="ghost"
                      onPress={() => void api.deleteToken(row.target).then(loadTokens)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              onPress={() => {
                setPendingOpen(null);
                setTokenTarget("");
                setTokenValue("");
                setTokenOpen(true);
              }}
            >
              <KeyRound className="h-4 w-4" />
              Add token
            </Button>
          </div>
        </aside>

        <main className="pane space-y-4">
          {snapshot?.tailscale?.available === false && snapshot.tailscale.error ? (
            <Card>
              <Card.Content className="px-5 py-4 text-sm text-white/70">
                Tailscale is not running. This computer and Wi-Fi still work.
              </Card.Content>
            </Card>
          ) : null}

          {hostCards.length === 0 ? (
            <div className="grid min-h-80 place-items-center rounded-3xl border border-dashed border-white/15 px-8 py-16 text-center">
              <div className="max-w-md">
                {scanning ? (
                  <span className="pulse mx-auto mb-4 block" />
                ) : (
                  <DoorOpen className="mx-auto mb-4 h-8 w-8 text-amber-300" />
                )}
                <h2 className="font-display text-3xl">{scanning ? "Looking for computers" : "Nothing found yet"}</h2>
                <p className="mt-3 text-white/55">
                  Press Find services to scan this computer, Wi-Fi, and Tailscale.
                </p>
              </div>
            </div>
          ) : (
            hostCards.map(({ meta, ports }) => {
              const kind = kindOf(meta);
              const info = KIND_META[kind] || KIND_META.wifi;
              const Icon = info.icon;
              const label = stateLabel(meta.state || "", scanning, ports.length > 0);
              return (
                <article key={meta.ip} className="host-card">
                  <div className="mb-2 flex items-center gap-3 px-1 pb-3">
                    <span className={`grid h-11 w-11 place-items-center rounded-xl bg-black/25 ${info.className}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="truncate text-[15px]">{meta.hostname || meta.ip}</h3>
                        {label ? (
                          <Chip size="sm" variant="soft">
                            {label}
                          </Chip>
                        ) : null}
                      </div>
                      <p className="mt-1 font-mono text-xs text-white/45">
                        {meta.ip} · {info.label}
                      </p>
                    </div>
                    <Button size="sm" variant="ghost" onPress={() => void startScan({ profile: "deep", host: meta.ip })}>
                      Check every port
                    </Button>
                  </div>
                  {ports.length === 0 ? (
                    <div className="px-1 pb-3 text-sm text-white/40">
                      {scanning ? "Checking for apps..." : "No open apps on this computer."}
                    </div>
                  ) : (
                    ports
                      .slice()
                      .sort((a, b) => a.port - b.port)
                      .map((item) => (
                        <div key={`${item.host}:${item.port}`} className="port-row">
                          <div className="font-mono text-amber-300">{item.port}</div>
                          <div className="min-w-0">
                            <div className="text-sm">{item.label}</div>
                            <div className="mt-1 truncate text-[12px] text-white/45">
                              {item.url || `${item.host}:${item.port}`}
                            </div>
                          </div>
                          <div className="flex flex-wrap justify-end gap-2">
                            {item.openable ? (
                              <Button size="sm" variant="secondary" onPress={() => void openItem(item)}>
                                <DoorOpen className="h-4 w-4" />
                                Open
                              </Button>
                            ) : null}
                            {item.protected ? (
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
                      ))
                  )}
                </article>
              );
            })
          )}
        </main>
      </div>

      <footer className="flex items-center justify-between border-t border-white/10 px-6 py-3 text-xs text-white/50">
        <span>{status}</span>
        <span>{visibleItems.length} open services</span>
      </footer>

      {toast ? (
        <div className="fixed bottom-16 right-5 rounded-xl border border-white/10 bg-[#141b24] px-4 py-3 text-sm shadow-xl">
          {toast}
        </div>
      ) : null}

      <Modal isOpen={tokenOpen} onOpenChange={setTokenOpen}>
        <Modal.Backdrop>
          <Modal.Container>
            <Modal.Dialog>
              <Modal.Header>
                <Modal.Heading>This service needs a token</Modal.Heading>
              </Modal.Header>
              <Modal.Body className="space-y-4 px-1 py-2">
                <p className="text-sm text-white/60">
                  Paste the token from the app (for example Jupyter). It stays on this computer.
                </p>
                <TextField value={tokenTarget} onChange={setTokenTarget} name="target">
                  <Label>Computer and port</Label>
                  <Input placeholder="127.0.0.1:8888" />
                </TextField>
                <TextField value={tokenValue} onChange={setTokenValue} name="token" type="password">
                  <Label>Token</Label>
                  <Input placeholder="paste token" />
                </TextField>
                <Dropdown label="How to send it" value={tokenStyle} options={STYLES} onChange={setTokenStyle} wide />
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
