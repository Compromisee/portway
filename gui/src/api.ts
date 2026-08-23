import type { ScanStatus, Snapshot, TokenRow } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${path} failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export const api = {
  snapshot: () => request<Snapshot>("/api/snapshot"),
  startScan: (body: Record<string, unknown>) =>
    request<{ ok: boolean; error?: string; phase?: string; profile?: string }>(
      "/api/scan/start",
      { method: "POST", body: JSON.stringify(body) },
    ),
  cancelScan: () => request("/api/scan/cancel", { method: "POST", body: "{}" }),
  status: () => request<ScanStatus>("/api/scan/status"),
  open: (body: Record<string, unknown>) =>
    request<{
      ok: boolean;
      error?: string;
      needs_token?: boolean;
      url?: string;
      target?: string;
    }>("/api/open", { method: "POST", body: JSON.stringify(body) }),
  tokens: () => request<{ tokens: TokenRow[] }>("/api/tokens"),
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
