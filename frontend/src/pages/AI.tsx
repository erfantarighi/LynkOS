import { FormEvent, useState } from "react";
import useSWR, { mutate } from "swr";
import { api } from "../api";
import type {
  AIAnomaliesResponse,
  AIExecutionResponse,
  AIInsight,
  AIIntentPlan,
  AIRecommendationsResponse,
  AIStatus,
} from "../types";

function badgeClasses(level: "low" | "medium" | "high") {
  if (level === "high") return "bg-red-100 text-red-700";
  if (level === "medium") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-700";
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AIPage() {
  const { data: status } = useSWR<AIStatus>("/api/ai/status");
  const enabled = !!status?.enabled;
  const available = !!status?.available;

  const { data: insight } = useSWR<AIInsight>(enabled ? "/api/ai/insights" : null, {
    refreshInterval: 15_000,
  });
  const { data: recommendations } = useSWR<AIRecommendationsResponse>(
    enabled ? "/api/ai/recommendations" : null,
    { refreshInterval: 15_000 },
  );
  const { data: anomalies } = useSWR<AIAnomaliesResponse>(enabled ? "/api/ai/anomalies" : null, {
    refreshInterval: 15_000,
  });

  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState<AIIntentPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const parseIntent = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const parsed = await api.post<AIIntentPlan>("/api/ai/intent/parse", { text: prompt.trim() });
      setPlan(parsed);
    } catch (error) {
      setErr(String(error).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const closePlan = async (approved: boolean) => {
    if (!plan) return;
    setBusy(true);
    setErr(null);
    try {
      if (approved && status?.execution_enabled && plan.actions.length > 0) {
        const result = await api.post<AIExecutionResponse>("/api/ai/intent/execute", {
          text: prompt.trim(),
          plan,
        });
        setMsg(`Executed ${result.results.length} action${result.results.length === 1 ? "" : "s"}.`);
      } else {
        await api.post("/api/ai/intent/review", {
          text: prompt.trim(),
          plan,
          approved,
        });
        setMsg(approved ? "Action plan approved and logged." : "Action plan rejected and logged.");
      }
      setPlan(null);
      mutate("/api/ai/insights");
      mutate("/api/ai/recommendations");
      mutate("/api/ai/anomalies");
    } catch (error) {
      setErr(String(error).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return <p className="text-sm text-slate-500">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">AI</h2>
          <p className="text-sm text-slate-500 mt-1">
            Structured router insights, recommendations, anomalies, and safe intent parsing.
          </p>
        </div>
        <div className="bg-white rounded-lg shadow px-4 py-3 text-sm">
          <div className="text-slate-500">Provider</div>
          <div className="font-medium">{status.provider}</div>
          <div className="text-xs text-slate-500 mt-1">
            {status.execution_enabled ? "Execution enabled" : "Proposal-only mode"}
          </div>
        </div>
      </div>

      {!status.enabled || !available ? (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium mb-2">AI unavailable</h3>
          <p className="text-sm text-slate-600">{status.reason ?? "AI is not available right now."}</p>
        </section>
      ) : (
        <>
          <section className="grid grid-cols-1 xl:grid-cols-[1.4fr,1fr] gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium">Insights</h3>
                <span className="text-xs text-slate-500">
                  {insight ? formatDate(insight.generated_at) : "Loading…"}
                </span>
              </div>
              <p className="text-sm text-slate-800">{insight?.summary ?? "Loading current summary…"}</p>
              <ul className="mt-3 space-y-2 text-sm">
                {(insight?.highlights ?? []).map((item) => (
                  <li key={item} className="border-l-2 border-slate-200 pl-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-medium mb-3">Ask LynkOS</h3>
              <form onSubmit={parseIntent} className="space-y-3">
                <textarea
                  className="w-full border rounded px-3 py-2 text-sm"
                  rows={5}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={
                    'Create a WireGuard peer for my phone\nDisable SSH\nSummarize my network'
                  }
                />
                <button
                  disabled={busy || !prompt.trim()}
                  className="px-3 py-2 bg-slate-900 text-white rounded disabled:opacity-50 text-sm"
                >
                  {busy ? "Working…" : "Parse request"}
                </button>
              </form>
              <p className="text-xs text-slate-500 mt-3">
                The AI only maps supported requests to validated LynkOS actions. It does not run shell commands.
              </p>
            </div>
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium">Recommendations</h3>
                <span className="text-xs text-slate-500">
                  {recommendations ? formatDate(recommendations.generated_at) : "Loading…"}
                </span>
              </div>
              <div className="space-y-3">
                {(recommendations?.items ?? []).map((item) => (
                  <div key={item.id} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-sm">{item.title}</div>
                      <span className={`text-xs px-2 py-0.5 rounded ${badgeClasses(item.severity)}`}>
                        {item.severity}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">{item.reason}</p>
                    <p className="text-xs text-slate-500 mt-2">{item.recommended_action}</p>
                  </div>
                ))}
                {!recommendations?.items?.length && (
                  <p className="text-sm text-slate-500">No recommendations right now.</p>
                )}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium">Anomalies</h3>
                <span className="text-xs text-slate-500">
                  {anomalies ? formatDate(anomalies.generated_at) : "Loading…"}
                </span>
              </div>
              <div className="space-y-3">
                {(anomalies?.items ?? []).map((item) => (
                  <div key={item.id} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-sm">{item.title}</div>
                      <span className={`text-xs px-2 py-0.5 rounded ${badgeClasses(item.severity)}`}>
                        {item.severity}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">{item.explanation}</p>
                    <p className="text-xs text-slate-500 mt-2">{formatDate(item.detected_at)}</p>
                  </div>
                ))}
                {!anomalies?.items?.length && (
                  <p className="text-sm text-slate-500">No anomalies detected.</p>
                )}
              </div>
            </div>
          </section>
        </>
      )}

      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {err && <p className="text-sm text-red-700 whitespace-pre-wrap">{err}</p>}

      {plan && (
        <div className="fixed inset-0 bg-slate-950/40 flex items-center justify-center p-6">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold">Action review</h3>
                <p className="text-sm text-slate-600 mt-1">{plan.explanation}</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${badgeClasses(plan.risk_level)}`}>
                {plan.risk_level} risk
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500">Intent</div>
                <div>{plan.intent}</div>
              </div>
              <div>
                <div className="text-slate-500">Confidence</div>
                <div>{Math.round(plan.confidence * 100)}%</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-medium mb-2">Structured actions</div>
              <pre className="bg-slate-900 text-slate-100 rounded p-3 text-xs overflow-auto max-h-72 whitespace-pre-wrap">
                {JSON.stringify(plan.actions, null, 2)}
              </pre>
            </div>

            {!!plan.missing_inputs.length && (
              <div className="text-sm text-amber-700">
                Missing inputs: {plan.missing_inputs.join(", ")}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => closePlan(false)}
                disabled={busy}
                className="px-3 py-2 rounded bg-slate-200 text-sm disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => closePlan(true)}
                disabled={busy}
                className="px-3 py-2 rounded bg-slate-900 text-white text-sm disabled:opacity-50"
              >
                {busy
                  ? "Working…"
                  : status.execution_enabled && plan.actions.length
                    ? "Confirm and apply"
                    : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
