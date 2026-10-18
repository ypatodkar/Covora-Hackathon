import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { ThreadRow } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { ThreadList } from "../features/inbox/ThreadList";
import { ThreadView } from "../features/inbox/ThreadView";

const FILTERS = [
  ["needs_review", "Needs review"],
  ["interested", "Interested"],
  ["all", "All"],
] as const;
type Filter = (typeof FILTERS)[number][0];

export function Inbox() {
  const [params] = useSearchParams();
  const campaign = params.get("campaign");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(null);
  const query = new URLSearchParams();
  if (filter !== "all") query.set("filter", filter);
  if (campaign) query.set("campaign_id", campaign);
  const qs = query.toString();
  const threads = useQuery({
    queryKey: ["threads", filter, campaign],
    queryFn: () => apiFetch<ThreadRow[]>(`/inbox/threads${qs ? `?${qs}` : ""}`),
    refetchInterval: 5000,
  });

  return (
    <>
      <PageHeader
        title="Inbox"
        subtitle="Every email is simulated and delivered in-app. Replies are labeled by the reply agent."
      />
      <div className="mb-4 flex gap-2">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
            className={`rounded-full px-3 py-1 text-sm ${filter === value ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {threads.isError && (
        <p role="alert" className="text-sm text-red-600">
          {threads.error.message}
        </p>
      )}
      {threads.data && threads.data.length === 0 && (
        <EmptyState
          title="No conversations yet"
          body="Approve a campaign's first batch and simulated replies will show up here."
        />
      )}
      {threads.data && threads.data.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <ThreadList
              threads={threads.data}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            {selected ? (
              <ThreadView prospectId={selected} />
            ) : (
              <p className="text-sm text-slate-500">Pick a conversation.</p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
