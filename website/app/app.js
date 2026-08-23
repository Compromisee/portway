/* Portway desktop UI */
(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const state = {
    snapshot: null,
    items: [],
    filterKind: "all",
    query: "",
    webOnly: false,
    scanning: false,
    selectedHost: null,
    profiles: {},
  };

  const KIND_META = {
    local: { label: "This machine", icon: "laptop", sub: "loopback" },
    wifi: { label: "Wi-Fi / LAN", icon: "wifi", sub: "local subnet" },
    ethernet: { label: "Ethernet", icon: "ethernet-port", sub: "wired LAN" },
    tailscale: { label: "Tailscale", icon: "share-2", sub: "mesh overlay" },
  };

  function iconize(root) {
    $$("[data-icon]", root || document).forEach((el) => {
      const name = el.getAttribute("data-icon");
      const size = Number(el.getAttribute("data-size") || 16);
      el.innerHTML = window.Lucide.svg(name, size);
    });
  }

  function hasApi() {
    return Boolean(window.pywebview && window.pywebview.api);
  }

  async function call(name, ...args) {
    if (hasApi()) {
      return window.pywebview.api[name](...args);
    }
    return Mock[name](...args);
  }

  function toast(message) {
    const box = document.createElement("div");
    box.className = "toast";
    box.textContent = message;
    $("#toasts").appendChild(box);
    setTimeout(() => box.remove(), 2800);
  }

  function setStatus(text, progress) {
    $("#status-text").textContent = text;
    if (typeof progress === "number") {
      $("#bar i").style.width = `${Math.max(0, Math.min(100, progress * 100))}%`;
    }
  }

  function hostKind(item) {
    return (item.host_meta && item.host_meta.kind) || item.kind || "wifi";
  }

  function matches(item) {
    if (state.filterKind !== "all" && hostKind(item) !== state.filterKind) return false;
    if (state.webOnly && !item.openable) return false;
    const q = state.query.trim().toLowerCase();
    if (!q) return true;
    const hay = [
      item.host,
      item.label,
      item.key,
      String(item.port),
      item.url || "",
      (item.host_meta && item.host_meta.hostname) || "",
    ]
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  }

  function groupItems(items) {
    const map = new Map();
    for (const item of items) {
      if (!matches(item)) continue;
      const key = item.host;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
    return map;
  }

  function renderPiers() {
    const groups = (state.snapshot && state.snapshot.groups) || {};
    const order = ["local", "wifi", "tailscale"];
    const mount = $("#pier-list");
    mount.innerHTML = "";
    for (const kind of order) {
      const group = groups[kind] || { hosts: [], nics: [] };
      const meta = KIND_META[kind];
      const openCount = state.items.filter((i) => hostKind(i) === kind).length;
      const nic = (group.nics || [])[0];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pier" + (state.filterKind === kind ? " active" : "");
      btn.dataset.kind = kind;
      const sub = nic ? `${nic.ip}/${nic.prefix}` : meta.sub;
      btn.innerHTML = `
        <span class="glyph">${window.Lucide.svg(meta.icon, 16)}</span>
        <span class="meta">
          <span class="name">${meta.label}</span>
          <span class="sub">${sub}</span>
        </span>
        <span class="count">${openCount || (group.hosts || []).length}</span>
      `;
      btn.addEventListener("click", () => {
        state.filterKind = state.filterKind === kind ? "all" : kind;
        render();
      });
      mount.appendChild(btn);
    }
  }

  function renderChips() {
    const mount = $("#chips");
    const chips = [
      ["all", "All piers"],
      ["local", "This machine"],
      ["wifi", "Wi-Fi"],
      ["tailscale", "Tailscale"],
    ];
    mount.innerHTML = chips
      .map(
        ([id, label]) =>
          `<button class="chip ${state.filterKind === id ? "on" : ""}" data-chip="${id}">${label}</button>`
      )
      .join("");
    $$("[data-chip]", mount).forEach((el) => {
      el.addEventListener("click", () => {
        state.filterKind = el.dataset.chip;
        render();
      });
    });
  }

  function renderNotice() {
    const box = $("#notice");
    const ts = state.snapshot && state.snapshot.tailscale;
    if (ts && ts.available === false && ts.error) {
      box.className = "notice info";
      box.innerHTML = `${window.Lucide.svg("share-2", 16)} <div><strong>Tailscale CLI not ready.</strong> ${escapeHtml(
        ts.error
      )} Wi-Fi and this machine still scan normally.</div>`;
      box.classList.remove("hidden");
    } else {
      box.className = "notice hidden";
      box.innerHTML = "";
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderEmpty() {
    const empty = $("#empty");
    if (state.items.some(matches)) {
      empty.classList.add("hidden");
      return;
    }
    empty.classList.remove("hidden");
    const scanning = state.scanning;
    empty.innerHTML = `
      <div class="empty-card">
        <div>${window.Lucide.svg(scanning ? "radar" : "door-open", 28)}</div>
        <h2>${scanning ? "Sweeping the harbor" : "No open doors yet"}</h2>
        <p>${
          scanning
            ? "Connect scans stay on this machine, the Wi-Fi subnet, and Tailscale peers."
            : "Scan to find Flask apps, Vite, dashboards, and anything else listening nearby."
        }</p>
      </div>
    `;
  }

  function hostIcon(kind) {
    if (kind === "local") return "laptop";
    if (kind === "tailscale") return "share-2";
    return "router";
  }

  function renderResults() {
    const mount = $("#results");
    const grouped = groupItems(state.items);
    mount.innerHTML = "";
    const hosts = Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    for (const [ip, ports] of hosts) {
      const meta = (ports[0] && ports[0].host_meta) || {};
      const kind = hostKind(ports[0]);
      const name = meta.hostname || ip;
      const card = document.createElement("article");
      card.className = "host";
      card.dataset.kind = kind;
      const deep = `<button class="btn small ghost" data-deep="${ip}">${window.Lucide.svg(
        "scan-search",
        14
      )} All ports</button>`;
      card.innerHTML = `
        <header class="host-h">
          <span class="glyph">${window.Lucide.svg(hostIcon(kind), 16)}</span>
          <div>
            <div class="title">${escapeHtml(name)}</div>
            <div class="addr">${escapeHtml(ip)}${meta.os ? " · " + escapeHtml(meta.os) : ""} · ${
              KIND_META[kind] ? KIND_META[kind].label : kind
            }</div>
          </div>
          <div class="host-actions">${deep}</div>
        </header>
        <div class="ports"></div>
      `;
      const list = $(".ports", card);
      for (const item of ports.sort((a, b) => a.port - b.port)) {
        const row = document.createElement("div");
        row.className = "port";
        const sub = [];
        if (item.banner && item.banner.server) sub.push(item.banner.server);
        if (item.url) sub.push(item.url);
        else sub.push(`${item.host}:${item.port}`);
        const openBtn = item.openable
          ? `<button class="btn small sea" data-open="${item.host}:${item.port}" data-scheme="${
              item.scheme || ""
            }">${window.Lucide.svg("door-open", 14)} Open</button>`
          : "";
        row.innerHTML = `
          <div class="num">${item.port}</div>
          <div>
            <div class="label">${escapeHtml(item.label)}</div>
            <div class="sub">
              <span class="pill ${item.group}">${item.group}</span>
              <span>${escapeHtml(sub.join(" · "))}</span>
            </div>
          </div>
          <div class="acts">
            ${openBtn}
            <button class="btn small ghost" data-copy="${escapeHtml(
              item.url || item.host + ":" + item.port
            )}">${window.Lucide.svg("copy", 14)} Copy</button>
          </div>
        `;
        list.appendChild(row);
      }
      mount.appendChild(card);
    }

    $$("[data-open]", mount).forEach((btn) => {
      btn.addEventListener("click", async () => {
        const [host, port] = btn.dataset.open.split(":");
        const scheme = btn.dataset.scheme || null;
        const res = await call("open_service", host, Number(port), scheme);
        if (res && res.ok) toast("Opened " + res.url);
        else toast((res && res.error) || "Could not open");
      });
    });
    $$("[data-copy]", mount).forEach((btn) => {
      btn.addEventListener("click", async () => {
        const text = btn.dataset.copy;
        try {
          await navigator.clipboard.writeText(text);
          toast("Copied " + text);
        } catch {
          toast(text);
        }
      });
    });
    $$("[data-deep]", mount).forEach((btn) => {
      btn.addEventListener("click", () => startScan({ profile: "deep", host: btn.dataset.deep }));
    });
  }

  function renderCounts() {
    const visible = state.items.filter(matches);
    const openable = visible.filter((i) => i.openable).length;
    $("#counts").textContent = `${visible.length} open · ${openable} openable`;
  }

  function render() {
    renderPiers();
    renderChips();
    renderNotice();
    renderEmpty();
    renderResults();
    renderCounts();
  }

  async function loadSnapshot() {
    state.snapshot = await call("snapshot", ["local", "wifi", "tailscale"]);
    render();
  }

  async function startScan(extra) {
    if (state.scanning) {
      await call("cancel_scan");
      state.scanning = false;
      $("#scan .btn-label").textContent = "Scan";
      document.body.classList.remove("scanning");
      setStatus("Scan cancelled.", 0);
      return;
    }
    const profile = (extra && extra.profile) || $("#profile").value;
    const host = extra && extra.host;
    if (profile === "deep" && !host) {
      toast("All-port scans run on one host. Use All ports on a result row.");
      return;
    }
    state.items = [];
    state.scanning = true;
    document.body.classList.add("scanning");
    $("#scan .btn-label").textContent = "Stop";
    setStatus("Starting sweep...", 0);
    render();
    const res = await call("start_scan", {
      networks: ["local", "wifi", "tailscale"],
      profile,
      host: host || null,
      fingerprint: true,
    });
    if (!res.ok) {
      state.scanning = false;
      document.body.classList.remove("scanning");
      $("#scan .btn-label").textContent = "Scan";
      toast(res.error || "Scan failed");
      setStatus(res.error || "Scan failed", 0);
    } else {
      setStatus(`Sweeping ${res.hosts} hosts · ${res.ports} ports`, 0);
    }
  }

  window.portway = {
    ingest(event) {
      if (!event || !event.type) return;
      if (event.type === "open") {
        state.items.push(event.item);
        render();
      } else if (event.type === "progress") {
        const pct = event.total ? event.done / event.total : 0;
        setStatus(
          `Sweeping ${event.current_host}:${event.current_port} · ${event.open} open`,
          pct
        );
        $("#elapsed").textContent = `${event.elapsed.toFixed(1)}s`;
      } else if (event.type === "done") {
        state.scanning = false;
        document.body.classList.remove("scanning");
        $("#scan .btn-label").textContent = "Scan";
        setStatus(
          event.cancelled ? "Scan cancelled." : `Done. ${event.count} open ports.`,
          event.cancelled ? undefined : 1
        );
        $("#elapsed").textContent = `${(event.elapsed || 0).toFixed(1)}s`;
        render();
      } else if (event.type === "start") {
        setStatus(`Checking ${event.hosts} hosts · ${event.ports} ports`, 0);
      }
    },
  };

  const Mock = {
    async snapshot() {
      return {
        hostname: "studio",
        platform: "Linux",
        tailscale: { available: true, backend: "Running" },
        nics: [
          { name: "lo", ip: "127.0.0.1", prefix: 8, kind: "local", cidr: "127.0.0.1/8" },
          { name: "wlp3s0", ip: "192.168.1.42", prefix: 24, kind: "wifi", cidr: "192.168.1.42/24" },
          { name: "tailscale0", ip: "100.101.20.3", prefix: 32, kind: "tailscale", cidr: "100.101.20.3/32" },
        ],
        groups: {
          local: {
            kind: "local",
            nics: [{ name: "lo", ip: "127.0.0.1", prefix: 8, kind: "local" }],
            hosts: [{ ip: "127.0.0.1", hostname: "localhost", kind: "local" }],
          },
          wifi: {
            kind: "wifi",
            nics: [{ name: "wlp3s0", ip: "192.168.1.42", prefix: 24, kind: "wifi" }],
            hosts: [
              { ip: "192.168.1.1", hostname: "gateway", kind: "wifi" },
              { ip: "192.168.1.42", hostname: "studio", kind: "wifi" },
            ],
          },
          tailscale: {
            kind: "tailscale",
            nics: [{ name: "tailscale0", ip: "100.101.20.3", prefix: 32, kind: "tailscale" }],
            hosts: [
              { ip: "100.101.20.3", hostname: "studio", kind: "tailscale", os: "linux" },
              { ip: "100.88.12.9", hostname: "nas", kind: "tailscale", os: "linux" },
            ],
          },
        },
      };
    },
    async start_scan() {
      const demo = [
        {
          host: "127.0.0.1",
          port: 5000,
          label: "Flask",
          key: "flask",
          group: "dev",
          scheme: "http",
          url: "http://127.0.0.1:5000/",
          openable: true,
          banner: { server: "Werkzeug/3.0" },
          host_meta: { hostname: "localhost", kind: "local" },
        },
        {
          host: "127.0.0.1",
          port: 22,
          label: "SSH",
          key: "ssh",
          group: "remote",
          scheme: null,
          url: null,
          openable: false,
          banner: {},
          host_meta: { hostname: "localhost", kind: "local" },
        },
        {
          host: "192.168.1.1",
          port: 80,
          label: "Router",
          key: "http",
          group: "web",
          scheme: "http",
          url: "http://192.168.1.1/",
          openable: true,
          banner: { server: "nginx" },
          host_meta: { hostname: "gateway", kind: "wifi" },
        },
        {
          host: "100.88.12.9",
          port: 8096,
          label: "Jellyfin",
          key: "jellyfin",
          group: "web",
          scheme: "http",
          url: "http://100.88.12.9:8096/",
          openable: true,
          banner: { server: "Jellyfin" },
          host_meta: { hostname: "nas", kind: "tailscale", os: "linux" },
        },
      ];
      setTimeout(() => {
        window.portway.ingest({ type: "start", hosts: 4, ports: 80, total: 320 });
        demo.forEach((item, i) => {
          setTimeout(() => window.portway.ingest({ type: "open", item }), 180 * (i + 1));
        });
        setTimeout(
          () =>
            window.portway.ingest({
              type: "done",
              count: demo.length,
              elapsed: 0.9,
              cancelled: false,
            }),
          1000
        );
      }, 80);
      return { ok: true, hosts: 4, ports: 80, profile: "developer" };
    },
    async cancel_scan() {
      return { ok: true };
    },
    async open_service(host, port, scheme) {
      const url = `${scheme || "http"}://${host}:${port}/`;
      window.open(url, "_blank");
      return { ok: true, url };
    },
  };

  function bind() {
    iconize(document);
    $("#scan").addEventListener("click", () => startScan());
    $("#refresh").addEventListener("click", loadSnapshot);
    $("#q").addEventListener("input", (e) => {
      state.query = e.target.value;
      render();
    });
    $("#web-only").addEventListener("change", (e) => {
      state.webOnly = e.target.checked;
      render();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== $("#q")) {
        e.preventDefault();
        $("#q").focus();
      }
      if ((e.key === "r" || e.key === "R") && document.activeElement.tagName !== "INPUT") {
        startScan();
      }
    });
  }

  async function boot() {
    bind();
    await loadSnapshot();
    setStatus(hasApi() ? "Ready to sweep the harbor." : "Preview mode. Scan still runs a local demo.");
  }

  window.addEventListener("pywebviewready", boot);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      if (!hasApi()) boot();
    });
  } else if (!hasApi()) {
    boot();
  }
})();
