import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { RunSummary } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge, formatCost, formatDuration, formatTokens } from "../features/runs/format";

export function AgentWorkflow() {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiFetch<RunSummary[]>("/runs"),
    refetchInterval: (query) => (query.state.data?.some((r) => r.status === "running") ? 3000 : false),
  });

  return (
    <>
      <PageHeader title="Agent Workflow" subtitle="Every agent run, with the model calls and memories behind it." />
      {runs.isError && (
        <p role="alert" className="text-sm text-red-600">
          {runs.error.message}
        </p>
      )}
      {runs.data && runs.data.length === 0 && (
        <EmptyState title="No agent runs yet" body="Interpret an ICP in ICP Studio to see your first run." />
      )}
      {runs.data && runs.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {["Kind", "Status", "Started", "Duration", "Model calls", "Tokens", "Est. cost"].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.data.map((run) => (
                <tr key={run.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/workflow/runs/${run.id}`} className="font-medium text-indigo-700 hover:underline">
                      {run.kind}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{new Date(run.started_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-600">{formatDuration(run.duration_ms)}</td>
                  <td className="px-4 py-3 text-slate-600">{run.llm_calls}</td>
                  <td className="px-4 py-3 text-slate-600">{formatTokens(run.prompt_tokens + run.completion_tokens)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatCost(run.est_cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
