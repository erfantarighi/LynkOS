import { FormEvent, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import useSWR, { mutate } from "swr";
import { api } from "../api";

type WgStatus = {
  initialized: boolean;
  meta: {
    subnet: string;
    port: number;
    endpoint: string;
    server_public: string;
    server_ip: string;
    next_host: number;
  } | null;
  running: boolean;
  peers: {
    name: string;
    public_key: string;
    allowed_ips: string;
    endpoint: string | null;
    latest_handshake: number;
    rx_bytes: number;
    tx_bytes: number;
  }[];
};

function formatBytes(n: number): string {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${u[i]}`;
}

function formatHandshake(t: number): string {
  if (!t) return "never";
  const ago = Math.floor(Date.now() / 1000) - t;
  if (ago < 60) return `${ago}s ago`;
  if (ago < 3600) return `${Math.floor(ago / 60)}m ago`;
  if (ago < 86400) return `${Math.floor(ago / 3600)}h ago`;
  return `${Math.floor(ago / 86400)}d ago`;
}

export default function Wireguard() {
  const { data } = useSWR<WgStatus>("/api/wireguard/status", { refreshInterval: 5000 });

  if (!data) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">WireGuard VPN</h2>
      {data.initialized ? <Running data={data} /> : <Setup />}
    </div>
  );
}

function Setup() {
  const [subnet, setSubnet] = useState("10.7.0.0/24");
  const [port, setPort] = useState("51820");
  const [endpoint, setEndpoint] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.post("/api/wireguard/setup", {
        subnet: subnet.trim(),
        port: Number(port),
        endpoint: endpoint.trim(),
      });
      mutate("/api/wireguard/status");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="bg-white rounded-lg shadow p-4">
      <h3 className="font-medium mb-3">Initial setup</h3>
      <form onSubmit={submit} className="grid grid-cols-6 gap-3 text-sm">
        <label className="col-span-2">
          <span>VPN subnet (CIDR)</span>
          <input className="w-full border rounded px-2 py-1" value={subnet} onChange={(e) => setSubnet(e.target.value)} />
        </label>
        <label className="col-span-1">
          <span>Port</span>
          <input
            type="number"
            min={1}
            max={65535}
            className="w-full border rounded px-2 py-1"
            value={port}
            onChange={(e) => setPort(e.target.value)}
          />
        </label>
        <label className="col-span-3">
          <span>Public endpoint</span>
          <input
            className="w-full border rounded px-2 py-1"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="home.example.com (use your DDNS hostname)"
            required
          />
        </label>
        <div className="col-span-6">
          <button
            disabled={busy}
            className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
          >
            {busy ? "Setting up…" : "Enable WireGuard"}
          </button>
        </div>
        {err && <p className="col-span-6 text-red-700 whitespace-pre-wrap">{err}</p>}
      </form>
      <p className="text-xs text-slate-500 mt-3">
        Generates a server keypair, writes <code>/etc/wireguard/wg0.conf</code>, enables
        <code> wg-quick@wg0</code>, and adds NAT masquerading out of <code>ppp0</code>.
        Make sure your router/ISP forwards UDP {port} to this Pi (it&apos;s already on PPPoE so that&apos;s automatic).
      </p>
    </section>
  );
}

function Running({ data }: { data: WgStatus }) {
  const [name, setName] = useState("");
  const [fullTunnel, setFullTunnel] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [newPeer, setNewPeer] = useState<{ name: string; config: string } | null>(null);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<{ name: string; config: string }>("/api/wireguard/peers", {
        name: name.trim(),
        full_tunnel: fullTunnel,
      });
      setNewPeer(r);
      setName("");
      mutate("/api/wireguard/status");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (publicKey: string, peerName: string) => {
    if (!confirm(`Delete peer ${peerName}?`)) return;
    try {
      await api.del(`/api/wireguard/peers/${encodeURIComponent(publicKey)}`);
      mutate("/api/wireguard/status");
    } catch (e) {
      setErr(String(e));
    }
  };

  const teardown = async () => {
    if (!confirm("Tear down WireGuard entirely? All peers will be disconnected.")) return;
    await api.post("/api/wireguard/teardown");
    mutate("/api/wireguard/status");
  };

  return (
    <>
      <section className="bg-white rounded-lg shadow p-4 grid grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-slate-500">Status</div>
          <div className={data.running ? "text-green-600" : "text-slate-600"}>
            {data.running ? "running" : "stopped"}
          </div>
        </div>
        <div>
          <div className="text-slate-500">Endpoint</div>
          <div className="font-mono">{data.meta?.endpoint}:{data.meta?.port}</div>
        </div>
        <div>
          <div className="text-slate-500">Subnet</div>
          <div className="font-mono">{data.meta?.subnet}</div>
        </div>
        <div className="text-right">
          <button onClick={teardown} className="text-red-600 text-sm hover:underline">
            Tear down
          </button>
        </div>
      </section>

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Add peer</h3>
        <form onSubmit={add} className="grid grid-cols-6 gap-3 text-sm">
          <label className="col-span-3">
            <span>Name</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="iphone"
              required
            />
          </label>
          <label className="col-span-3 flex items-center gap-2 pt-5">
            <input
              type="checkbox"
              checked={fullTunnel}
              onChange={(e) => setFullTunnel(e.target.checked)}
            />
            <span>
              Full tunnel <span className="text-slate-500 text-xs">(route all internet traffic through VPN)</span>
            </span>
          </label>
          <div className="col-span-6">
            <button disabled={busy} className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50">
              {busy ? "Creating…" : "Add peer"}
            </button>
          </div>
          {err && <p className="col-span-6 text-red-700 whitespace-pre-wrap">{err}</p>}
        </form>
      </section>

      {newPeer && <PeerConfigModal peer={newPeer} onClose={() => setNewPeer(null)} />}

      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="font-medium mb-3">Peers</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Name</th>
              <th>Allowed IPs</th>
              <th>Endpoint</th>
              <th>Handshake</th>
              <th>Traffic (rx / tx)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.peers.length ? (
              data.peers.map((p) => (
                <tr key={p.public_key} className="border-t">
                  <td className="py-1">{p.name}</td>
                  <td className="font-mono text-xs">{p.allowed_ips}</td>
                  <td className="font-mono text-xs">{p.endpoint ?? "—"}</td>
                  <td>{formatHandshake(p.latest_handshake)}</td>
                  <td>{formatBytes(p.rx_bytes)} / {formatBytes(p.tx_bytes)}</td>
                  <td className="text-right">
                    <button
                      onClick={() => remove(p.public_key, p.name)}
                      className="text-red-600 hover:underline"
                    >
                      delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-500">
                  No peers — add one above
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </>
  );
}

function PeerConfigModal({ peer, onClose }: { peer: { name: string; config: string }; onClose: () => void }) {
  const downloadConfig = () => {
    const blob = new Blob([peer.config], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${peer.name}.conf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 max-w-2xl w-full">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Peer config: {peer.name}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-800">✕</button>
        </div>
        <div className="grid grid-cols-5 gap-4">
          <div className="col-span-2 flex flex-col items-center bg-slate-50 rounded p-3">
            <QRCodeSVG value={peer.config} size={240} includeMargin />
            <p className="text-xs text-slate-500 mt-2 text-center">
              Scan this in the WireGuard mobile app
            </p>
          </div>
          <div className="col-span-3">
            <pre className="bg-slate-900 text-slate-100 text-xs rounded p-3 overflow-auto max-h-72">{peer.config}</pre>
            <button
              onClick={downloadConfig}
              className="mt-3 px-3 py-1 bg-slate-200 rounded text-sm"
            >
              Download .conf
            </button>
          </div>
        </div>
        <p className="text-xs text-amber-700 mt-3">
          This is the only time the private key is shown — save the config or scan the QR now.
        </p>
      </div>
    </div>
  );
}
