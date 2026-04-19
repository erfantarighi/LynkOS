import { useState } from "react";
import useSWR, { mutate } from "swr";
import Sparkline from "../components/Sparkline";
import { api } from "../api";

type Run = {
  timestamp: string;
  ping_ms: number;
  download_mbps: number;
  upload_mbps: number;
  server: string | null;
  server_location: string | null;
  client_ip: string | null;
  isp: string | null;
};

type HistoryResponse = { runs: Run[]; running: boolean };

function fmt(n: number, unit: string) {
  return `${n.toFixed(n < 10 ? 2 : 1)} ${unit}`;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function Speedtest() {
  const { data } = useSWR<HistoryResponse>("/api/speedtest/history", { refreshInterval: 5000 });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const runTest = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.post("/api/speedtest/run");
      mutate("/api/speedtest/history");
    } catch (e) {
      setErr(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const runs = data?.runs ?? [];
  const latest = runs[runs.length - 1];
  const downloads = runs.map((r) => r.download_mbps);
  const uploads = runs.map((r) => r.upload_mbps);
  const pings = runs.map((r) => r.ping_ms);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Speedtest</h2>
        <button
          onClick={runTest}
          disabled={busy || data?.running}
          className="px-4 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
        >
          {busy || data?.running ? "Running…" : "Run speedtest"}
        </button>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-slate-500">Download</div>
          <div className="text-3xl font-semibold">
            {latest ? fmt(latest.download_mbps, "Mbps") : "—"}
          </div>
          <div className="mt-3">
            <Sparkline
              values={downloads}
              color="#2563eb"
              fill="rgba(37,99,235,0.12)"
              max={downloads.length ? Math.max(...downloads) * 1.1 : 100}
            />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-slate-500">Upload</div>
          <div className="text-3xl font-semibold">
            {latest ? fmt(latest.upload_mbps, "Mbps") : "—"}
          </div>
          <div className="mt-3">
            <Sparkline
              values={uploads}
              color="#dc2626"
              fill="rgba(220,38,38,0.12)"
              max={uploads.length ? Math.max(...uploads) * 1.1 : 50}
            />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-slate-500">Ping</div>
          <div className="text-3xl font-semibold">
            {latest ? fmt(latest.ping_ms, "ms") : "—"}
          </div>
          <div className="mt-3">
            <Sparkline
              values={pings}
              color="#b45309"
              fill="rgba(180,83,9,0.12)"
              max={pings.length ? Math.max(...pings) * 1.1 : 100}
            />
          </div>
        </div>
      </section>

      {latest && (
        <section className="bg-white rounded-lg shadow p-4 text-sm">
          <h3 className="font-medium mb-2">Latest run</h3>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-y-1">
            <dt className="text-slate-500">Server</dt>
            <dd>{latest.server ?? "—"}</dd>
            <dt className="text-slate-500">Location</dt>
            <dd>{latest.server_location ?? "—"}</dd>
            <dt className="text-slate-500">ISP</dt>
            <dd>{latest.isp ?? "—"}</dd>
            <dt className="text-slate-500">Public IP</dt>
            <dd className="font-mono">{latest.client_ip ?? "—"}</dd>
            <dt className="text-slate-500">When</dt>
            <dd className="col-span-3">{formatTime(latest.timestamp)}</dd>
          </dl>
        </section>
      )}

      {err && <p className="text-sm text-red-700 whitespace-pre-wrap">{err}</p>}

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-2">History</h3>
        {runs.length ? (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">When</th>
                <th>Download</th>
                <th>Upload</th>
                <th>Ping</th>
                <th>Server</th>
              </tr>
            </thead>
            <tbody>
              {[...runs].reverse().map((r, i) => (
                <tr key={`${r.timestamp}-${i}`} className="border-t">
                  <td className="py-1">{formatTime(r.timestamp)}</td>
                  <td>{fmt(r.download_mbps, "Mbps")}</td>
                  <td>{fmt(r.upload_mbps, "Mbps")}</td>
                  <td>{fmt(r.ping_ms, "ms")}</td>
                  <td>{r.server ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-slate-500 text-sm">No runs yet — click "Run speedtest".</p>
        )}
      </section>
    </div>
  );
}
