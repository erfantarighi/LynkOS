import useSWR from "swr";
import type { DhcpLease } from "../types";

function stateColor(state: string | null): string {
  if (!state) return "text-slate-500";
  if (state.includes("REACHABLE")) return "text-green-600";
  if (state.includes("STALE") || state.includes("DELAY") || state.includes("PROBE"))
    return "text-amber-600";
  return "text-slate-500";
}

export default function Clients() {
  const { data: leases } = useSWR<DhcpLease[]>("/api/clients", { refreshInterval: 5000 });
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Connected clients</h2>
      <div className="bg-white rounded-lg shadow p-4">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Hostname</th>
              <th>IP</th>
              <th>MAC</th>
              <th>Interface</th>
              <th>State</th>
              <th>Lease</th>
            </tr>
          </thead>
          <tbody>
            {leases?.length ? (
              leases.map((l) => (
                <tr key={l.mac} className="border-t">
                  <td className="py-1">{l.hostname ?? "—"}</td>
                  <td className="font-mono">{l.ip}</td>
                  <td className="font-mono text-xs">{l.mac}</td>
                  <td>{l.interface ?? "—"}</td>
                  <td className={stateColor(l.state)}>{l.state ?? "—"}</td>
                  <td>{l.expires ?? "—"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-500">
                  No clients connected
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        Source: kernel ARP/neighbor table (<code>ip neigh</code>). Hostnames come from dnsmasq
        lease files when readable. State <span className="text-green-600">REACHABLE</span> means
        the device just responded; <span className="text-amber-600">STALE</span> means it&apos;s
        been idle but is probably still there.
      </p>
    </div>
  );
}
