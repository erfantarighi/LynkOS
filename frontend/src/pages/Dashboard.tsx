import { useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import Sparkline from "../components/Sparkline";
import type { Interface, MetricsSeries, PppoeStatus, Snapshot, SystemStats } from "../types";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-slate-500 mb-2">{title}</h3>
      <div>{children}</div>
    </div>
  );
}

function formatBytes(n: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function formatBps(n: number) {
  const units = ["bps", "Kbps", "Mbps", "Gbps"];
  let i = 0;
  let v = n * 8; // bytes/s → bits/s
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function formatUptime(s: number) {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

export default function Dashboard() {
  const { data: stats } = useSWR<SystemStats>("/api/system/stats");
  const { data: pppoe } = useSWR<PppoeStatus>("/api/pppoe/status");
  const { data: ifaces } = useSWR<Interface[]>("/api/interfaces");
  const { data: snapshot } = useSWR<Snapshot>("/api/snapshot");
  const { data: series } = useSWR<MetricsSeries>("/api/metrics/series", { refreshInterval: 2000 });
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  const applyNow = async () => {
    setApplying(true);
    setApplyMsg(null);
    try {
      const r = await api.post<{ routes: unknown[]; hotspot: string | null; pppoe: string | null }>(
        "/api/snapshot/apply",
      );
      setApplyMsg(
        `Applied: ${r.routes.length} routes${r.hotspot ? `, hotspot: ${r.hotspot}` : ""}${
          r.pppoe ? `, pppoe: ${r.pppoe}` : ""
        }`,
      );
      mutate("/api/routes");
      mutate("/api/pppoe/status");
      mutate("/api/wifi/hotspot");
    } catch (e) {
      setApplyMsg(String(e));
    } finally {
      setApplying(false);
    }
  };

  const captureNow = async () => {
    setApplying(true);
    setApplyMsg(null);
    try {
      const r = await api.post<{ vlans: number; routes: number; hotspot: boolean; pppoe: boolean }>(
        "/api/snapshot/capture",
      );
      setApplyMsg(
        `Captured: ${r.vlans} VLAN${r.vlans === 1 ? "" : "s"}, ${r.routes} route${r.routes === 1 ? "" : "s"}` +
          `${r.hotspot ? ", hotspot" : ""}${r.pppoe ? ", pppoe (no password)" : ""}`,
      );
      mutate("/api/snapshot");
    } catch (e) {
      setApplyMsg(String(e));
    } finally {
      setApplying(false);
    }
  };

  const downloadBackup = () => {
    const token = localStorage.getItem("lynkos.token") ?? "";
    const a = document.createElement("a");
    // Browser follows the Content-Disposition header from /api/snapshot/export.
    // Use fetch to include Authorization, then blob-download.
    fetch("/api/snapshot/export", { headers: { Authorization: `Bearer ${token}` } })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        a.href = url;
        a.download = `lynkos-snapshot-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
        a.click();
        URL.revokeObjectURL(url);
        setApplyMsg("Backup downloaded");
      })
      .catch((e) => setApplyMsg(String(e)));
  };

  const uploadBackup = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json,.json";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      if (!confirm(`Replace the current snapshot with "${file.name}"? Your current snapshot will be lost.`)) return;
      setApplying(true);
      setApplyMsg(null);
      try {
        const token = localStorage.getItem("lynkos.token") ?? "";
        const form = new FormData();
        form.append("file", file);
        const res = await fetch("/api/snapshot/import", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        if (!res.ok) throw new Error(await res.text());
        const body = (await res.json()) as { detail?: string };
        setApplyMsg(body.detail ?? "Imported — click 'Re-apply now' to push to the system");
        mutate("/api/snapshot");
      } catch (e) {
        setApplyMsg(String(e));
      } finally {
        setApplying(false);
      }
    };
    input.click();
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="Uptime">
          <p className="text-2xl">{stats ? formatUptime(stats.uptime_seconds) : "…"}</p>
          <p className="text-sm text-slate-500 mt-1">
            load {stats ? stats.load_avg.join(" / ") : "…"}
          </p>
        </Card>
        <Card title="Memory">
          <p className="text-2xl">
            {stats ? `${stats.memory_used_mb} / ${stats.memory_total_mb} MB` : "…"}
          </p>
        </Card>
        <Card title="CPU temp">
          <p className="text-2xl">
            {stats?.cpu_temp_c != null ? `${stats.cpu_temp_c.toFixed(1)} °C` : "n/a"}
          </p>
        </Card>
        <Card title="WAN (PPPoE)">
          {pppoe?.configured ? (
            <div>
              <p className={pppoe.active ? "text-green-600" : "text-slate-500"}>
                {pppoe.active ? "Connected" : "Inactive"}
              </p>
              <p className="text-sm text-slate-500">IP: {pppoe.ip_address ?? "—"}</p>
              <p className="text-sm text-slate-500">User: {pppoe.username ?? "—"}</p>
            </div>
          ) : (
            <p className="text-slate-500">Not configured</p>
          )}
        </Card>
        <Card title="Throughput (total)">
          <p className="text-sm">RX {stats ? formatBytes(stats.rx_bytes) : "…"}</p>
          <p className="text-sm">TX {stats ? formatBytes(stats.tx_bytes) : "…"}</p>
        </Card>
        <Card title="Interfaces">
          <ul className="text-sm space-y-1">
            {ifaces?.map((i) => (
              <li key={i.name} className="flex justify-between">
                <span>
                  {i.name} <span className="text-slate-400">({i.type})</span>
                </span>
                <span
                  className={
                    i.state === "connected" ? "text-green-600" : "text-slate-500"
                  }
                >
                  {i.state}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <LiveCharts series={series} />

      <section className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium">Snapshot</h3>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={downloadBackup}
              disabled={applying}
              className="text-sm px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
              title="Download snapshot.json (contains secrets — keep safe)"
            >
              Download backup
            </button>
            <button
              onClick={uploadBackup}
              disabled={applying}
              className="text-sm px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
              title="Upload a snapshot.json to replace the current one"
            >
              Upload backup
            </button>
            <button
              onClick={captureNow}
              disabled={applying}
              className="text-sm px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
              title="Scan current system state and save it"
            >
              Capture from live
            </button>
            <button
              onClick={applyNow}
              disabled={applying}
              className="text-sm px-3 py-1 bg-slate-900 text-white rounded disabled:opacity-50"
            >
              {applying ? "Applying…" : "Re-apply now"}
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          Captured automatically when you change config. Re-applied idempotently on service start.
        </p>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-slate-500">Routes</div>
            <div>{snapshot?.routes?.length ?? 0} saved</div>
          </div>
          <div>
            <div className="text-slate-500">Hotspot</div>
            <div>{snapshot?.hotspot?.ssid ?? "—"}</div>
          </div>
          <div>
            <div className="text-slate-500">PPPoE</div>
            <div>{snapshot?.pppoe?.username ?? "—"}</div>
          </div>
        </div>
        {applyMsg && <p className="mt-3 text-xs text-slate-700">{applyMsg}</p>}
      </section>
    </div>
  );
}

function LiveCharts({ series }: { series: MetricsSeries | undefined }) {
  const samples = series?.samples ?? [];

  const cpuValues = useMemo(() => samples.map((s) => s.cpu_pct), [samples]);
  const memValues = useMemo(
    () => samples.map((s) => (s.mem_total_mb ? (100 * s.mem_used_mb) / s.mem_total_mb : 0)),
    [samples],
  );
  const tempValues = useMemo(
    () => samples.map((s) => s.cpu_temp_c ?? 0).filter((_, i, arr) => arr[i] != null),
    [samples],
  );

  // Collect per-interface rx/tx time-series, excluding loopback.
  const ifaceNames = useMemo(() => {
    const names = new Set<string>();
    for (const s of samples) {
      for (const name of Object.keys(s.interfaces)) names.add(name);
    }
    return Array.from(names).sort();
  }, [samples]);

  const latest = samples[samples.length - 1];

  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-medium text-slate-500">CPU usage</h3>
          <span className="text-sm">{latest ? `${latest.cpu_pct.toFixed(0)}%` : "—"}</span>
        </div>
        <Sparkline values={cpuValues} max={100} color="#1d4ed8" fill="rgba(29,78,216,0.12)" />
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-medium text-slate-500">Memory used</h3>
          <span className="text-sm">
            {latest ? `${latest.mem_used_mb} / ${latest.mem_total_mb} MB` : "—"}
          </span>
        </div>
        <Sparkline values={memValues} max={100} color="#059669" fill="rgba(5,150,105,0.12)" />
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-medium text-slate-500">CPU temp</h3>
          <span className="text-sm">
            {latest?.cpu_temp_c != null ? `${latest.cpu_temp_c.toFixed(1)} °C` : "n/a"}
          </span>
        </div>
        <Sparkline
          values={tempValues.length ? tempValues : [0]}
          max={Math.max(80, ...tempValues, 40)}
          color="#b45309"
          fill="rgba(180,83,9,0.12)"
        />
      </div>

      {ifaceNames.map((name) => {
        const rx = samples.map((s) => s.interfaces[name]?.rx_bps ?? 0);
        const tx = samples.map((s) => s.interfaces[name]?.tx_bps ?? 0);
        const maxRate = Math.max(1, ...rx, ...tx);
        const last = latest?.interfaces[name];
        return (
          <div key={name} className="bg-white rounded-lg shadow p-4 md:col-span-3">
            <div className="flex items-baseline justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-500">
                {name}{" "}
                <span className="text-slate-400 text-xs">
                  {last ? `rx ${formatBps(last.rx_bps)} · tx ${formatBps(last.tx_bps)}` : ""}
                </span>
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500 mb-1">RX (download)</div>
                <Sparkline
                  values={rx}
                  max={maxRate}
                  color="#2563eb"
                  fill="rgba(37,99,235,0.12)"
                  formatValue={(n) => formatBps(n)}
                />
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">TX (upload)</div>
                <Sparkline
                  values={tx}
                  max={maxRate}
                  color="#dc2626"
                  fill="rgba(220,38,38,0.12)"
                  formatValue={(n) => formatBps(n)}
                />
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
