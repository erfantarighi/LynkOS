import { FormEvent, useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import type { WifiNetwork } from "../types";

type HotspotInfo = {
  active: boolean;
  ssid: string | null;
  band: string | null;
  channel: number | null;
  connection_name: string | null;
};

export default function Wifi() {
  const { data: networks } = useSWR<WifiNetwork[]>("/api/wifi/scan");
  const { data: hotspot } = useSWR<HotspotInfo>("/api/wifi/hotspot");

  const [ssid, setSsid] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [band, setBand] = useState<"bg" | "a">("bg");
  const [channel, setChannel] = useState<string>("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [prefilled, setPrefilled] = useState(false);

  // Populate form fields from the current hotspot config on first load so the
  // user can see what's running instead of empty boxes. Only done once to
  // avoid wiping in-progress edits.
  useEffect(() => {
    if (prefilled || !hotspot) return;
    if (hotspot.ssid) setSsid(hotspot.ssid);
    if (hotspot.band === "a" || hotspot.band === "bg") setBand(hotspot.band);
    if (hotspot.channel != null) setChannel(String(hotspot.channel));
    setPrefilled(true);
  }, [hotspot, prefilled]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      await api.post("/api/wifi/hotspot", {
        ssid,
        passphrase,
        band,
        channel: channel ? Number(channel) : null,
      });
      setMsg("Hotspot started");
      mutate("/api/wifi/hotspot");
    } catch (e) {
      setErr(String(e));
    }
  };

  const stop = async () => {
    try {
      await api.post("/api/wifi/hotspot/stop");
      setMsg("Hotspot stopped");
      mutate("/api/wifi/hotspot");
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">WiFi / Hotspot</h2>

      <section className="bg-white rounded-lg shadow p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium">
            Hotspot
            {hotspot?.connection_name && (
              <span className="text-xs text-slate-400 ml-2">({hotspot.connection_name})</span>
            )}
          </h3>
          <span
            className={`text-sm px-2 py-1 rounded ${
              hotspot?.active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
            }`}
          >
            {hotspot?.active ? "Active" : "Inactive"}
          </span>
        </div>
        <form onSubmit={save} className="grid grid-cols-2 gap-3">
          <label className="block col-span-2">
            <span className="text-sm">SSID</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={ssid}
              onChange={(e) => setSsid(e.target.value)}
              required
              minLength={1}
              maxLength={32}
            />
          </label>
          <label className="block col-span-2">
            <span className="text-sm">Passphrase</span>
            <input
              type="password"
              className="w-full border rounded px-2 py-1"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              required
              minLength={8}
              maxLength={63}
            />
          </label>
          <label className="block">
            <span className="text-sm">Band</span>
            <select
              className="w-full border rounded px-2 py-1"
              value={band}
              onChange={(e) => setBand(e.target.value as "bg" | "a")}
            >
              <option value="bg">2.4 GHz (bg)</option>
              <option value="a">5 GHz (a)</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm">Channel (optional)</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              type="number"
              min={1}
              max={165}
            />
          </label>
          <div className="col-span-2 flex gap-2">
            <button type="submit" className="px-3 py-2 bg-slate-900 text-white rounded">
              Apply & start
            </button>
            <button
              type="button"
              onClick={stop}
              className="px-3 py-2 bg-slate-200 rounded"
            >
              Stop hotspot
            </button>
          </div>
          {msg && <p className="col-span-2 text-sm text-green-700">{msg}</p>}
          {err && <p className="col-span-2 text-sm text-red-700">{err}</p>}
        </form>
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Nearby networks</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">SSID</th>
              <th>Signal</th>
              <th>Security</th>
              <th>Channel</th>
            </tr>
          </thead>
          <tbody>
            {networks?.map((n) => (
              <tr key={n.ssid} className="border-t">
                <td className="py-1">
                  {n.in_use ? "★ " : ""}
                  {n.ssid}
                </td>
                <td>{n.signal}</td>
                <td>{n.security}</td>
                <td>{n.channel ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
