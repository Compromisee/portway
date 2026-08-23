export type HostMeta = {
  ip?: string;
  hostname?: string;
  kind?: string;
  source?: string;
  nic?: string;
  os?: string;
  online?: boolean;
  tags?: string[];
};

export type OpenItem = {
  host: string;
  port: number;
  label: string;
  key: string;
  group: string;
  scheme: string | null;
  url: string | null;
  openable: boolean;
  protected?: boolean;
  has_token?: boolean;
  token_target?: string;
  banner?: { server?: string; title?: string; status?: number };
  host_meta?: HostMeta;
};

export type Snapshot = {
  hostname?: string;
  platform?: string;
  tailscale?: { available?: boolean; error?: string; backend?: string };
  groups?: Record<
    string,
    {
      kind: string;
      nics: { name: string; ip: string; prefix: number; kind: string }[];
      hosts: HostMeta[];
    }
  >;
};

export type TokenRow = {
  target: string;
  token: string;
  style: string;
  query_key: string;
  note: string;
  has_token: boolean;
};
