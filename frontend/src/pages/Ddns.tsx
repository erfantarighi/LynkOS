import { FormEvent, useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";

type DdnsConfig = {
  enabled: boolean;
  api_token: string;
  zone: string;
  hostnames: string[];
  proxied: boolean;
  interval_seconds: number;
  last_ip: string;
};

type DdnsState = {
  running: boolean;
  zone_id: string | null;
  current_ip: string | null;
  last_check_at: string | null;
  last_update_at: string | null;
  last_error: string | null;
  records: { hostname: string; id: string; content: string; proxied: boolean }[];
};

type DdnsResponse = { config: DdnsConfig; state: DdnsState };

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function DdnsPage() {
  const { data } = useSWR<DdnsResponse>("/api/ddns", { refreshInterval: 10_000 });

  const [enabled, setEnabled] = useState(false);
  const [apiToken, setApiToken] = useState("");
  const [zone, setZone] = useState("");
  const [hostnames, setHostnames] = useState("");
  const [proxied, setProxied] = useState(false);
  const [interval, setIntervalSec] = useState("60");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [prefilled, setPrefilled] = useState(false);

  useEffect(() => {
    if (prefilled || !data?.config) return;
    const c = data.config;
    setEnabled(c.enabled);
    setApiToken(c.api_token || "");
    setZone(c.zone || "");
    setHostnames((c.hostnames || []).join(", "));
    setProxied(c.proxied);
    setIntervalSec(String(c.interval_seconds));
    setPrefilled(true);
  }, [data, prefilled]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/ddns", {
        enabled,
        api_token: apiToken,
        zone: zone.trim(),
        hostnames: hostnames.split(",").map((h) => h.trim()).filter(Boolean),
        proxied,
        interval_seconds: Number(interval),
      });
      setMsg("Saved");
      mutate("/api/ddns");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const updateNow = async () => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/ddns/update");
      setMsg("Update triggered");
      mutate("/api/ddns");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const state = data?.state;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Dynamic DNS (Cloudflare)</h2>

      <section className="bg-white rounded-lg shadow p-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <div className="text-slate-500">Status</div>
          <div className={state?.running ? "text-green-600" : "text-slate-600"}>
            {state?.running ? "running" : "stopped"}
          </div>
        </div>
        <div>
          <div className="text-slate-500">Current PPPoE IP</div>
          <div className="font-mono">{state?.current_ip ?? "—"}</div>
        </div>
        <div>
          <div className="text-slate-500">Last update</div>
          <div>{formatDate(state?.last_update_at ?? null)}</div>
        </div>
        <div>
          <div className="text-slate-500">Last check</div>
          <div>{formatDate(state?.last_check_at ?? null)}</div>
        </div>
        <div className="col-span-2">
          <div className="text-slate-500">Last error</div>
          <div className={state?.last_error ? "text-red-700 whitespace-pre-wrap" : ""}>
            {state?.last_error ?? "—"}
          </div>
        </div>
        {state?.records?.length ? (
          <div className="col-span-3">
            <div className="text-slate-500 mb-1">DNS records</div>
            <table className="w-full">
              <thead className="text-left text-slate-500">
                <tr>
                  <th>Hostname</th>
                  <th>Type</th>
                  <th>Points to</th>
                  <th>Proxied</th>
                </tr>
              </thead>
              <tbody>
                {state.records.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="py-1">{r.hostname}</td>
                    <td>A</td>
                    <td className="font-mono">{r.content}</td>
                    <td>{r.proxied ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Configuration</h3>
        <form onSubmit={save} className="grid grid-cols-6 gap-3 text-sm">
          <label className="col-span-6 flex items-center gap-2">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            <span>Enabled</span>
          </label>

          <label className="col-span-6">
            <span>Cloudflare API token</span>
            <input
              type="password"
              className="w-full border rounded px-2 py-1 font-mono"
              value={apiToken}
              onChange={(e) => setApiToken(e.target.value)}
              placeholder="Create a token with Zone → DNS → Edit on just this zone"
              autoComplete="off"
            />
            <p className="text-xs text-slate-500 mt-1">
              The saved token is never shown back — you&apos;ll see <code>••••••••xxxx</code> after saving.
              Re-type a new one to replace it.
            </p>
          </label>

          <label className="col-span-3">
            <span>Zone (root domain)</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={zone}
              onChange={(e) => setZone(e.target.value)}
              placeholder="example.com"
            />
          </label>
          <label className="col-span-3">
            <span>Hostnames (comma-separated)</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={hostnames}
              onChange={(e) => setHostnames(e.target.value)}
              placeholder="home, vpn.example.com"
            />
            <p className="text-xs text-slate-500 mt-1">
              Short names (<code>home</code>) get the zone appended. Full names are used as-is.
            </p>
          </label>

          <label className="col-span-2 flex items-center gap-2">
            <input type="checkbox" checked={proxied} onChange={(e) => setProxied(e.target.checked)} />
            <span>Proxied (orange cloud)</span>
          </label>
          <label className="col-span-2">
            <span>Poll interval (sec)</span>
            <input
              type="number"
              min={15}
              max={3600}
              className="w-full border rounded px-2 py-1"
              value={interval}
              onChange={(e) => setIntervalSec(e.target.value)}
            />
          </label>
          <div className="col-span-2 flex items-end justify-end gap-2">
            <button
              type="button"
              onClick={updateNow}
              disabled={busy}
              className="px-3 py-2 bg-slate-200 rounded disabled:opacity-50"
            >
              Update now
            </button>
            <button
              type="submit"
              disabled={busy}
              className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
            >
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
          {msg && <p className="col-span-6 text-green-700">{msg}</p>}
          {err && <p className="col-span-6 text-red-700 whitespace-pre-wrap">{err}</p>}
        </form>
      </section>
    </div>
  );
}
