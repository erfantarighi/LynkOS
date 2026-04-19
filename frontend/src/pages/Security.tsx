import { useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";

type SshStatus = { enabled: boolean; active: boolean; port: number };

function SshCard() {
  const { data } = useSWR<SshStatus>("/api/ssh", { refreshInterval: 10_000 });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggle = async () => {
    const action = data?.enabled || data?.active ? "disable" : "enable";
    if (action === "disable" && !confirm("Disable SSH? You can re-enable it from here anytime — this button works whether SSH is on or off.")) return;
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/api/ssh/${action}`);
      mutate("/api/ssh");
    } catch (e) {
      setErr(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const on = !!data?.active;
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-medium">SSH</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            on ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
          }`}
        >
          {on ? "running" : "stopped"}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-y-1 text-sm mt-2">
        <dt className="text-slate-500">Enabled on boot</dt>
        <dd>{data?.enabled ? "yes" : "no"}</dd>
        <dt className="text-slate-500">Port</dt>
        <dd>{data?.port ?? 22}</dd>
      </dl>
      <button
        onClick={toggle}
        disabled={busy}
        className={`mt-3 px-3 py-1 rounded text-sm ${
          on ? "bg-red-100 text-red-700" : "bg-slate-900 text-white"
        } disabled:opacity-50`}
      >
        {busy ? "…" : on ? "Disable SSH" : "Enable SSH"}
      </button>
      {err && <p className="text-xs text-red-700 mt-2 whitespace-pre-wrap">{err}</p>}
    </div>
  );
}

type Jail = {
  enabled: boolean;
  error?: string;
  currently_failed?: number;
  total_failed?: number;
  currently_banned?: number;
  total_banned?: number;
  banned_ips?: string[];
};

type StatusResp = { jails: Record<string, Jail> };
type LogsResp = { lines: string[]; error?: string };

function JailCard({ name, jail, onUnban }: { name: string; jail: Jail; onUnban: (ip: string) => void }) {
  if (!jail.enabled) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium">{name}</h3>
        <p className="text-sm text-slate-500 mt-2">{jail.error ?? "unavailable"}</p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-medium">{name}</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            (jail.currently_banned ?? 0) > 0
              ? "bg-red-100 text-red-700"
              : "bg-green-100 text-green-700"
          }`}
        >
          {jail.currently_banned ?? 0} banned
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-y-1 text-sm mt-2">
        <dt className="text-slate-500">Currently failed</dt>
        <dd>{jail.currently_failed ?? 0}</dd>
        <dt className="text-slate-500">Total failed</dt>
        <dd>{jail.total_failed ?? 0}</dd>
        <dt className="text-slate-500">Total banned</dt>
        <dd>{jail.total_banned ?? 0}</dd>
      </dl>
      {jail.banned_ips && jail.banned_ips.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-slate-500 mb-1">Currently banned</div>
          <ul className="space-y-1 text-sm">
            {jail.banned_ips.map((ip) => (
              <li key={ip} className="flex items-center justify-between font-mono">
                <span>{ip}</span>
                <button
                  onClick={() => onUnban(ip)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  unban
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function Security() {
  const { data: status } = useSWR<StatusResp>("/api/fail2ban/status", { refreshInterval: 5000 });
  const { data: logs } = useSWR<LogsResp>("/api/fail2ban/logs?n=100", { refreshInterval: 10_000 });

  const unban = async (jail: string, ip: string) => {
    if (!confirm(`Unban ${ip} from ${jail}?`)) return;
    try {
      await api.post(`/api/fail2ban/unban?jail=${encodeURIComponent(jail)}&ip=${encodeURIComponent(ip)}`);
      mutate("/api/fail2ban/status");
    } catch (e) {
      alert(String(e));
    }
  };

  const jails = status?.jails ?? {};
  const names = Object.keys(jails);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Security</h2>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SshCard />
      </section>

      <h3 className="text-lg font-semibold mt-4">fail2ban</h3>
      {names.length ? (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {names.map((name) => (
            <JailCard
              key={name}
              name={name}
              jail={jails[name]}
              onUnban={(ip) => unban(name, ip)}
            />
          ))}
        </section>
      ) : (
        <p className="text-sm text-slate-500">Loading…</p>
      )}

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-2">Recent log</h3>
        {logs?.error ? (
          <p className="text-sm text-red-700">{logs.error}</p>
        ) : logs?.lines?.length ? (
          <pre className="bg-slate-900 text-slate-100 text-xs rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap">
            {logs.lines.join("\n")}
          </pre>
        ) : (
          <p className="text-sm text-slate-500">No recent events.</p>
        )}
      </section>

      <p className="text-xs text-slate-500">
        Internal networks (<code>10.0.0.0/8</code>, <code>172.16.0.0/12</code>,{" "}
        <code>192.168.0.0/16</code>, WireGuard, loopback) are always ignored — only external IPs get banned.
      </p>
    </div>
  );
}
