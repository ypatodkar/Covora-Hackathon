import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { RunDetail as RunDetailData, SpanOut } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { cardClass } from "../components/ui";
import { LlmCallCard } from "../features/runs/LlmCallCard";
import { SpanTree } from "../features/runs/SpanTree";
import { WorkingMemoryPanel } from "../features/runs/WorkingMemoryPanel";
import { StatusBadge, formatDuration } from "../features/runs/format";

export function RunDetail() {
  const { runId = "" } = useParams();
  const [selected, setSelected] = useState<SpanOut | null>(null);
  const detail = useQuery({
    queryKey: ["run", runId],
    queryFn: () => apiFetch<RunDetailData>(`/runs/${runId}`),
    refetchInterval: (query) => (query.state.data?.run.status === "running" ? 2000 : false),
  });

  if (detail.isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {detail.error.message}
      </p>
    );
  }
  if (!detail.data) return <p className="text-sm text-slate-500">Loading…</p>;

  const { run, spans, llm_calls } = detail.data;
  const call = selected ? llm_calls.find((c) => c.span_id === selected.id) : undefined;

  return (
    <>
      <Link to="/workflow" className="text-sm text-slate-500 hover:text-slate-700">
        ← All runs
      </Link>
      <PageHeader
        title={`${run.kind} run`}
        actions={
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <StatusBadge status={run.status} />
            <span>{formatDuration(run.duration_ms)}</span>
          </div>
        }
      />
      {run.error && <p className="mb-6 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{run.error}</p>}
      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        <section className={cardClass}>
          <h2 className="mb-3 text-sm font-semibold">Steps</h2>
          <SpanTree spans={spans} selectedId={selected?.id ?? null} onSelect={setSelected} />
        </section>
        <aside className={cardClass}>
          {!selected && <p className="text-sm text-slate-400">Select a step to see its details.</p>}
          {selected?.kind === "llm" &&
            (call ? <LlmCallCard call={call} /> : <p className="text-sm text-slate-400">No model call recorded.</p>)}
          {selected?.kind === "agent" && <WorkingMemoryPanel runId={run.id} spanId={selected.id} />}
          {selected && selected.kind !== "llm" && selected.kind !== "agent" && (
            <pre className="overflow-auto text-xs text-slate-600">{JSON.stringify(selected.attributes, null, 2)}</pre>
          )}
        </aside>
      </div>
    </>
  );
}
