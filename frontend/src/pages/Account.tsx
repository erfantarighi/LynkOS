import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearToken } from "../api";

export default function Account() {
  const nav = useNavigate();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    if (newPw !== confirm) {
      setErr("New passwords do not match");
      return;
    }
    if (newPw.length < 8) {
      setErr("New password must be at least 8 characters");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/auth/change-password", {
        old_password: oldPw,
        new_password: newPw,
      });
      setMsg("Password changed — signing you out…");
      setTimeout(() => {
        clearToken();
        nav("/login");
      }, 1200);
    } catch (e) {
      setErr(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-md">
      <h2 className="text-2xl font-semibold">Change password</h2>
      <form onSubmit={submit} className="bg-white rounded-lg shadow p-4 space-y-3 text-sm">
        <label className="block">
          <span>Current password</span>
          <input
            type="password"
            autoComplete="current-password"
            className="w-full border rounded px-2 py-1"
            value={oldPw}
            onChange={(e) => setOldPw(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span>New password</span>
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            className="w-full border rounded px-2 py-1"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span>Confirm new password</span>
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            className="w-full border rounded px-2 py-1"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </label>
        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={busy}
            className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50"
          >
            {busy ? "Saving…" : "Change password"}
          </button>
        </div>
        {msg && <p className="text-green-700">{msg}</p>}
        {err && <p className="text-red-700 whitespace-pre-wrap">{err}</p>}
        <p className="text-xs text-slate-500 pt-2">
          The new password is stored as a bcrypt hash in <code>data/admin_hash</code>
          {" "}(overrides the env-based default). Survives service restarts.
        </p>
      </form>
    </div>
  );
}
