import { FormEvent, useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";

type AdblockStatus = {
  enabled: boolean;
  blocklists: string[];
  allowlist: string[];
  entry_count: number;
  last_update: string;
  last_error: string;
};

function formatDate(iso: string): string {
  if (!iso) return "never";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function Adblock() {
  const { data } = useSWR<AdblockStatus>("/api/adblock", { refreshInterval: 5000 });
  const [blocklists, setBlocklists] = useState("");
  const [allowlist, setAllowlist] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [prefilled, setPrefilled] = useState(false);

  useEffect(() => {
    if (prefilled || !data) return;
    setBlocklists((data.blocklists || []).join("\n"));
    setAllowlist((data.allowlist || []).join("\n"));
    setPrefilled(true);
  }, [data, prefilled]);

  const post = async (path: string, label: string) => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const r = await api.post<{ detail?: string }>(path);
      setMsg(r.detail ?? label);
      mutate("/api/adblock");
    } catch (e) {
      setErr(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const saveConfig = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/adblock", {
        enabled: data?.enabled ?? false,
        blocklists: blocklists.split("\n").map((s) => s.trim()).filter(Boolean),
        allowlist: allowlist.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      setMsg("Saved — click 'Update blocklists' to re-fetch");
      mutate("/api/adblock");
    } catch (e) {
      setErr(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const enable = () => post("/api/adblock/enable", "enabled");
  const disable = () => post("/api/adblock/disable", "disabled");
  const update = () => post("/api/adblock/update", "updated");

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">DNS Adblock</h2>

      <section className="bg-white rounded-lg shadow p-4 grid grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-slate-500">Status</div>
          <div className={data?.enabled ? "text-green-600" : "text-slate-600"}>
            {data?.enabled ? "enabled" : "disabled"}
          </div>
        </div>
        <div>
          <div className="text-slate-500">Blocked domains</div>
          <div className="text-lg">{data?.entry_count?.toLocaleString() ?? "—"}</div>
        </div>
        <div>
          <div className="text-slate-500">Last update</div>
          <div>{formatDate(data?.last_update ?? "")}</div>
        </div>
        <div className="text-right space-x-2">
          {data?.enabled ? (
            <button
              onClick={disable}
              disabled={busy}
              className="px-3 py-1 bg-red-100 text-red-700 rounded disabled:opacity-50"
            >
              Disable
            </button>
          ) : (
            <button
              onClick={enable}
              disabled={busy}
              className="px-3 py-1 bg-slate-900 text-white rounded disabled:opacity-50"
            >
              Enable
            </button>
          )}
          <button
            onClick={update}
            disabled={busy}
            className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
            title="Re-download blocklists"
          >
            Update
          </button>
        </div>
        {data?.last_error && (
          <div className="col-span-4 text-xs text-red-700 whitespace-pre-wrap">
            {data.last_error}
          </div>
        )}
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Configuration</h3>
        <form onSubmit={saveConfig} className="space-y-4 text-sm">
          <label className="block">
            <span>Blocklist URLs (one per line)</span>
            <textarea
              className="w-full border rounded px-2 py-1 font-mono text-xs"
              rows={4}
              value={blocklists}
              onChange={(e) => setBlocklists(e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-1">
              Leave empty to use StevenBlack&apos;s unified hosts list. Any URL in
              <code> 0.0.0.0 domain</code> or plain-domain format works.
            </p>
          </label>
          <label className="block">
            <span>Allowlist (one domain per line)</span>
            <textarea
              className="w-full border rounded px-2 py-1 font-mono text-xs"
              rows={4}
              value={allowlist}
              onChange={(e) => setAllowlist(e.target.value)}
              placeholder={"example.com\ndoubleclick.net"}
            />
            <p className="text-xs text-slate-500 mt-1">
              Domains here are removed from the merged blocklist. Use if you hit a
              site that was blocked aggressively.
            </p>
          </label>
          <div>
            <button
              disabled={busy}
              className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
            >
              {busy ? "Saving…" : "Save config"}
            </button>
          </div>
          {msg && <p className="text-green-700">{msg}</p>}
          {err && <p className="text-red-700 whitespace-pre-wrap">{err}</p>}
        </form>
      </section>

      <p className="text-xs text-slate-500">
        Enabling briefly restarts the hotspot (dnsmasq needs to relaunch with the
        new <code>--addn-hosts</code> argument). Subsequent blocklist updates
        reload without dropping clients. DNS adblock won&apos;t stop YouTube /
        Instagram / TikTok ads — those come from the same CDN as the content.
      </p>
    </div>
  );
}
