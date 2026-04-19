import { FormEvent, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import type { Vlan } from "../types";

export default function VlansPage() {
  const { data: vlans } = useSWR<Vlan[]>("/api/vlans");
  const [parent, setParent] = useState("eth0");
  const [vid, setVid] = useState("7");
  const [name, setName] = useState("");
  const [managed, setManaged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/vlans", {
        parent,
        vid: Number(vid),
        name: name.trim() || null,
        managed,
      });
      setMsg("VLAN created");
      setName("");
      mutate("/api/vlans");
      mutate("/api/interfaces");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (v: Vlan) => {
    if (!confirm(`Delete VLAN ${v.name}? This will also drop anything depending on it.`)) return;
    setErr(null);
    try {
      await api.del(`/api/vlans/${encodeURIComponent(v.name)}`);
      setMsg(`VLAN ${v.name} deleted`);
      mutate("/api/vlans");
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">VLANs</h2>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Add VLAN</h3>
        <form onSubmit={add} className="grid grid-cols-6 gap-3 text-sm">
          <label className="col-span-2">
            <span>Parent interface</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={parent}
              onChange={(e) => setParent(e.target.value)}
              placeholder="eth0"
              required
            />
          </label>
          <label className="col-span-1">
            <span>VLAN ID</span>
            <input
              type="number"
              min={1}
              max={4094}
              className="w-full border rounded px-2 py-1"
              value={vid}
              onChange={(e) => setVid(e.target.value)}
              required
            />
          </label>
          <label className="col-span-2">
            <span>Interface name (optional)</span>
            <input
              className="w-full border rounded px-2 py-1"
              placeholder={`${parent}.${vid}`}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <div className="col-span-6 flex flex-col gap-1">
            <span className="text-xs text-slate-500">Mode</span>
            <div className="flex gap-4">
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  className="mt-1"
                  name="mode"
                  checked={!managed}
                  onChange={() => setManaged(false)}
                />
                <span>
                  <span className="font-medium">Unmanaged</span>
                  <span className="block text-xs text-slate-500">
                    Raw VLAN via <code>ip link</code>. Use for PPPoE upstream, bridging, or anything pppd uses.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  className="mt-1"
                  name="mode"
                  checked={managed}
                  onChange={() => setManaged(true)}
                />
                <span>
                  <span className="font-medium">Managed (NetworkManager)</span>
                  <span className="block text-xs text-slate-500">
                    NM VLAN connection with ipv4/ipv6 auto. Use for LAN segments with DHCP.
                  </span>
                </span>
              </label>
            </div>
          </div>
          <div className="col-span-6">
            <button disabled={busy} className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50">
              {busy ? "Creating…" : "Create"}
            </button>
          </div>
          {msg && <p className="col-span-6 text-sm text-green-700">{msg}</p>}
          {err && <p className="col-span-6 text-sm text-red-700 whitespace-pre-wrap">{err}</p>}
        </form>
        <p className="text-xs text-slate-500 mt-2">
          VLANs are created as NetworkManager connections — they come up automatically on boot.
          Use this to create e.g. <code>eth0.7</code> so PPPoE has something to run on.
        </p>
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">VLAN interfaces</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Name</th>
              <th>Parent</th>
              <th>VID</th>
              <th>Mode</th>
              <th>State</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {vlans?.length ? (
              vlans.map((v) => (
                <tr key={v.name} className="border-t">
                  <td className="py-1">{v.name}</td>
                  <td>{v.parent}</td>
                  <td>{v.vid}</td>
                  <td>{v.managed ? "managed" : "unmanaged"}</td>
                  <td className={v.active ? "text-green-600" : "text-slate-500"}>
                    {v.active ? "active" : "inactive"}
                  </td>
                  <td className="text-right">
                    <button onClick={() => remove(v)} className="text-red-600 hover:underline">
                      delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-500">
                  No VLAN interfaces
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
