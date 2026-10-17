import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";
import type { WorkingMemoryItem } from "../../api/types";

const EVIDENCE_STYLES: Record<string, string> = {
  evidence: "bg-emerald-100 text-emerald-800",
  signal: "bg-amber-100 text-amber-800",
};

export function WorkingMemoryPanel({ runId, spanId }: { runId: string; spanId: string }) {
  const memory = useQuery({
    queryKey: ["working-memory", runId, spanId],
    queryFn: () => apiFetch<WorkingMemoryItem[]>(`/runs/${runId}/spans/${spanId}/memory`),
  });

  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold">Working memory</h3>
      <p className="mb-3 text-xs text-slate-500">What this agent step had in front of it when it decided.</p>
      {memory.isPending && <p className="text-sm text-slate-400">Loading…</p>}
      {memory.isError && (
        <p role="alert" className="text-sm text-red-600">
          {memory.error.message}
        </p>
      )}
      {memory.data && memory.data.length === 0 && (
        <p className="text-sm text-slate-400">This step had no relevant memories.</p>
      )}
      {memory.data && memory.data.length > 0 && (
        <ol className="space-y-3">
          {memory.data.map((item) => (
            <li key={item.memory_item_id} className="rounded-md border border-slate-200 p-3 text-sm">
              <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-700">#{item.rank}</span>
                <span>
                  {item.kind}/{item.subtype}
                </span>
                {item.evidence_level && (
                  <span
                    className={`rounded-full px-2 py-0.5 font-medium ${EVIDENCE_STYLES[item.evidence_level] ?? "bg-slate-100"}`}
                  >
                    {item.evidence_level}
                  </span>
                )}
              </div>
              <p className="text-slate-900">{item.summary}</p>
              <p className="mt-1 text-xs text-slate-500">Retrieved as: {item.reason}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
