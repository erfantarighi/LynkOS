import { FormEvent, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import type { IpRoute, IpRouteRequest } from "../types";

export default function RoutesPage() {
  const { data: routes } = useSWR<IpRoute[]>("/api/routes");

  const [family, setFamily] = useState<4 | 6>(4);
  const [destination, setDestination] = useState("");
  const [gateway, setGateway] = useState("");
  const [device, setDevice] = useState("");
  const [metric, setMetric] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const buildReq = (): IpRouteRequest => ({
    family,
    destination: destination.trim(),
    gateway: gateway.trim() || null,
    device: device.trim() || null,
    metric: metric ? Number(metric) : null,
  });

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/routes", buildReq());
      setMsg("Route added");
      setDestination("");
      setGateway("");
      setDevice("");
      setMetric("");
      mutate("/api/routes");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (r: IpRoute) => {
    const desc = `${r.destination} ${r.gateway ? `via ${r.gateway}` : ""} ${r.device ? `dev ${r.device}` : ""}`.trim();
    if (!confirm(`Delete route: ${desc}?`)) return;
    setErr(null);
    try {
      await api.del("/api/routes");
      // DELETE with body isn't supported via api.del helper — use fetch directly
    } catch { /* handled below */ }
    try {
      const res = await fetch("/api/routes", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("lynkos.token") ?? ""}`,
        },
        body: JSON.stringify({
          family: r.family,
          destination: r.destination,
          gateway: r.gateway,
          device: r.device,
          metric: r.metric,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMsg("Route deleted");
      mutate("/api/routes");
    } catch (e) {
      setErr(String(e));
    }
  };

  const v4 = routes?.filter((r) => r.family === 4) ?? [];
  const v6 = routes?.filter((r) => r.family === 6) ?? [];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Routes</h2>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Add static route</h3>
        <form onSubmit={add} className="grid grid-cols-6 gap-3 text-sm">
          <label className="col-span-1">
            <span>Family</span>
            <select
              className="w-full border rounded px-2 py-1"
              value={family}
              onChange={(e) => setFamily(Number(e.target.value) as 4 | 6)}
            >
              <option value={4}>IPv4</option>
              <option value={6}>IPv6</option>
            </select>
          </label>
          <label className="col-span-2">
            <span>Destination</span>
            <input
              className="w-full border rounded px-2 py-1"
              placeholder={family === 4 ? "0.0.0.0/0 or default" : "::/0"}
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              required
            />
          </label>
          <label className="col-span-2">
            <span>Gateway</span>
            <input
              className="w-full border rounded px-2 py-1"
              placeholder={family === 4 ? "192.168.1.1" : "fe80::1"}
              value={gateway}
              onChange={(e) => setGateway(e.target.value)}
            />
          </label>
          <label className="col-span-1">
            <span>Device</span>
            <input
              className="w-full border rounded px-2 py-1"
              placeholder="eth0"
              value={device}
              onChange={(e) => setDevice(e.target.value)}
            />
          </label>
          <label className="col-span-1">
            <span>Metric</span>
            <input
              type="number"
              min={0}
              className="w-full border rounded px-2 py-1"
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
            />
          </label>
          <div className="col-span-6">
            <button
              disabled={busy}
              className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
            >
              {busy ? "Adding…" : "Add route"}
            </button>
          </div>
          {msg && <p className="col-span-6 text-sm text-green-700">{msg}</p>}
          {err && <p className="col-span-6 text-sm text-red-700 whitespace-pre-wrap">{err}</p>}
        </form>
        <p className="text-xs text-slate-500 mt-2">
          Gateway or device is required. Routes apply immediately and are not persisted across reboots.
        </p>
      </section>

      {[
        { title: "IPv4 routing table", rows: v4 },
        { title: "IPv6 routing table", rows: v6 },
      ].map(({ title, rows }) => (
        <section key={title} className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium mb-3">{title}</h3>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Destination</th>
                <th>Gateway</th>
                <th>Dev</th>
                <th>Metric</th>
                <th>Proto</th>
                <th>Src</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((r, i) => (
                  <tr key={`${r.destination}-${r.device}-${i}`} className="border-t">
                    <td className="py-1">{r.destination}</td>
                    <td>{r.gateway ?? "—"}</td>
                    <td>{r.device ?? "—"}</td>
                    <td>{r.metric ?? "—"}</td>
                    <td>{r.protocol ?? "—"}</td>
                    <td>{r.prefsrc ?? "—"}</td>
                    <td className="text-right">
                      <button
                        onClick={() => remove(r)}
                        className="text-red-600 hover:underline"
                        title="Delete route"
                      >
                        delete
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-4 text-center text-slate-500">
                    No routes
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
