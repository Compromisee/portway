async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  const data = (await response.json()) as T;
  return data;
}

export const api = {
  snapshot: () => request<import("./types").Snapshot>("/api/snapshot"),
  startScan: (body: Record<string, unknown>) =>
    request<{ ok: boolean; error?: string; hosts?: number; ports?: number }>(
      "/api/scan/start",
      { method: "POST", body: JSON.stringify(body) },
    ),
  cancelScan: () => request("/api/scan/cancel", { method: "POST", body: "{}" }),
  status: () =>
    request<{
      running: boolean;
      items: import("./types").OpenItem[];
      progress: Record<string, number | string>;
      count: number;
    }>("/api/scan/status"),
  open: (body: Record<string, unknown>) =>
    request<{
      ok: boolean;
      error?: string;
      needs_token?: boolean;
      url?: string;
      target?: string;
    }>("/api/open", { method: "POST", body: JSON.stringify(body) }),
  tokens: () => request<{ tokens: import("./types").TokenRow[] }>("/api/tokens"),
  saveToken: (body: Record<string, unknown>) =>
    request<{ ok: boolean; error?: string }>("/api/tokens", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteToken: (target: string) =>
    request<{ ok: boolean }>(`/api/tokens/${encodeURIComponent(target)}`, {
      method: "DELETE",
    }),
};
