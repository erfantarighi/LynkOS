import { FormEvent, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import type { PppoeStatus } from "../types";

export default function Pppoe() {
  const { data: status } = useSWR<PppoeStatus>("/api/pppoe/status");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [iface, setIface] = useState("");
  const [mtu, setMtu] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/pppoe/configure", {
        username,
        password,
        interface: iface || null,
        mtu: mtu ? Number(mtu) : null,
      });
      setMsg("Saved");
      mutate("/api/pppoe/status");
    } catch (e) {
      setErr(String(e));
    }
  };

  const up = async () => {
    setErr(null);
    try {
      await api.post("/api/pppoe/up");
      setMsg("Bringing link up…");
      mutate("/api/pppoe/status");
    } catch (e) {
      setErr(String(e));
    }
  };

  const down = async () => {
    await api.post("/api/pppoe/down");
    setMsg("Link down");
    mutate("/api/pppoe/status");
  };

  const remove = async () => {
    if (!confirm("Delete PPPoE connection?")) return;
    await api.del("/api/pppoe");
    setMsg("Removed");
    mutate("/api/pppoe/status");
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">PPPoE / WAN</h2>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Status</h3>
        {status ? (
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-slate-500">State</dt>
            <dd className={status.active ? "text-green-700" : "text-slate-700"}>
              {status.active ? "Connected" : status.configured ? "Configured (down)" : "Not configured"}
            </dd>
            <dt className="text-slate-500">Interface</dt>
            <dd>{status.interface ?? "—"}</dd>
            <dt className="text-slate-500">Username</dt>
            <dd>{status.username ?? "—"}</dd>
            <dt className="text-slate-500">IP address</dt>
            <dd>{status.ip_address ?? "—"}</dd>
          </dl>
        ) : (
          <p>Loading…</p>
        )}
        <div className="flex gap-2 mt-3">
          <button onClick={up} className="px-3 py-1 bg-slate-900 text-white rounded">Up</button>
          <button onClick={down} className="px-3 py-1 bg-slate-200 rounded">Down</button>
          <button onClick={remove} className="px-3 py-1 bg-red-100 text-red-700 rounded">Delete</button>
        </div>
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Configure</h3>
        <form onSubmit={save} className="grid grid-cols-2 gap-3 text-sm">
          <label className="block col-span-2">
            <span>ISP username</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label className="block col-span-2">
            <span>ISP password</span>
            <input
              type="password"
              className="w-full border rounded px-2 py-1"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label className="block">
            <span>Interface (optional)</span>
            <input
              className="w-full border rounded px-2 py-1"
              placeholder="eth0"
              value={iface}
              onChange={(e) => setIface(e.target.value)}
            />
          </label>
          <label className="block">
            <span>MTU (optional)</span>
            <input
              type="number"
              min={576}
              max={1500}
              className="w-full border rounded px-2 py-1"
              placeholder="1492"
              value={mtu}
              onChange={(e) => setMtu(e.target.value)}
            />
          </label>
          <div className="col-span-2">
            <button className="px-3 py-2 bg-slate-900 text-white rounded">Save</button>
          </div>
          {msg && <p className="col-span-2 text-green-700">{msg}</p>}
          {err && <p className="col-span-2 text-red-700">{err}</p>}
        </form>
      </section>
    </div>
  );
}
