export type WifiNetwork = {
  ssid: string;
  signal: number;
  security: string;
  channel: number | null;
  in_use: boolean;
};

export type HotspotConfig = {
  ssid: string;
  passphrase: string;
  band: "a" | "bg";
  channel: number | null;
  interface: string | null;
};

export type PppoeStatus = {
  configured: boolean;
  active: boolean;
  connection_name: string | null;
  interface: string | null;
  username: string | null;
  ip_address: string | null;
};

export type Interface = {
  name: string;
  type: string;
  state: string;
  ip_address: string | null;
  mac: string | null;
};

export type DhcpLease = {
  mac: string;
  ip: string;
  hostname: string | null;
  expires: string | null;
  interface: string | null;
  state: string | null;
};

export type Vlan = {
  name: string;
  parent: string;
  vid: number;
  active: boolean;
  managed: boolean;
  autoconnect: boolean;
};

export type VlanRequest = {
  parent: string;
  vid: number;
  name?: string | null;
  managed: boolean;
};

export type IpRoute = {
  family: number;
  destination: string;
  gateway: string | null;
  device: string | null;
  metric: number | null;
  protocol: string | null;
  scope: string | null;
  prefsrc: string | null;
};

export type Snapshot = {
  version: number;
  routes: {
    family: number;
    destination: string;
    gateway: string | null;
    device: string | null;
    metric: number | null;
  }[];
  hotspot: {
    ssid: string;
    passphrase: string;
    band: string;
    channel: number | null;
    interface: string | null;
  } | null;
  pppoe: {
    username: string;
    password: string;
    interface: string | null;
    mtu: number | null;
  } | null;
};

export type IpRouteRequest = {
  family: 4 | 6;
  destination: string;
  gateway: string | null;
  device: string | null;
  metric: number | null;
};

export type MetricsSample = {
  ts: number;
  cpu_pct: number;
  mem_used_mb: number;
  mem_total_mb: number;
  cpu_temp_c: number | null;
  interfaces: Record<string, { rx_bps: number; tx_bps: number }>;
};

export type MetricsSeries = {
  interval_seconds: number;
  window_seconds: number;
  samples: MetricsSample[];
};

export type SystemStats = {
  uptime_seconds: number;
  load_avg: [number, number, number];
  cpu_temp_c: number | null;
  memory_total_mb: number;
  memory_used_mb: number;
  rx_bytes: number;
  tx_bytes: number;
};

export type AIStatus = {
  enabled: boolean;
  provider: string;
  execution_enabled: boolean;
  available: boolean;
  reason: string | null;
};

export type AIInsight = {
  summary: string;
  highlights: string[];
  generated_at: string;
};

export type AIRecommendation = {
  id: string;
  title: string;
  severity: "low" | "medium" | "high";
  reason: string;
  recommended_action: string;
};

export type AIRecommendationsResponse = {
  items: AIRecommendation[];
  generated_at: string;
};

export type AIAnomaly = {
  id: string;
  severity: "low" | "medium" | "high";
  title: string;
  explanation: string;
  detected_at: string;
};

export type AIAnomaliesResponse = {
  items: AIAnomaly[];
  generated_at: string;
};

export type AIAction =
  | {
      type: "create_wireguard_peer";
      params: { name: string; platform: "mobile" | "desktop" | "generic"; full_tunnel: boolean };
    }
  | { type: "disable_ssh"; params: Record<string, never> }
  | { type: "enable_ssh"; params: Record<string, never> }
  | { type: "enable_adblock"; params: Record<string, never> }
  | { type: "disable_adblock"; params: Record<string, never> }
  | { type: "summarize_network"; params: Record<string, never> }
  | { type: "explain_anomalies"; params: Record<string, never> };

export type AIIntentPlan = {
  intent: string;
  confidence: number;
  requires_confirmation: boolean;
  risk_level: "low" | "medium" | "high";
  explanation: string;
  actions: AIAction[];
  missing_inputs: string[];
};

export type AIExecutionResponse = {
  ok: boolean;
  results: { type: string; result: unknown }[];
  executed_at: string;
};
