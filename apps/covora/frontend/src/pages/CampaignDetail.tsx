import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { apiFetch, postJson } from "../api/client";
import type { CampaignOut } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { cardClass, primaryButton } from "../components/ui";
import { Funnel } from "../features/campaigns/Funnel";
import { ReviewQueue } from "../features/review/ReviewQueue";
import {
  CampaignStatusBadge,
  STOP_REASONS,
  isActive,
} from "../features/campaigns/status";

export function CampaignDetail() {
  const { campaignId = "" } = useParams();
  const queryClient = useQueryClient();
  const campaign = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => apiFetch<CampaignOut>(`/campaigns/${campaignId}`),
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data.status) ? 3000 : false,
  });
  const retry = useMutation({
    mutationFn: () =>
      postJson<CampaignOut>(`/campaigns/${campaignId}/retry`, {}),
    onSuccess: (c) => queryClient.setQueryData(["campaign", campaignId], c),
  });

  if (campaign.isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {campaign.error.message}
      </p>
    );
  }
  if (!campaign.data) return <p className="text-sm text-slate-500">Loading…</p>;
  const c = campaign.data;
  const stop = c.progress.stop_reason
    ? STOP_REASONS[c.progress.stop_reason]
    : null;

  return (
    <>
      <Link
        to="/campaigns"
        className="text-sm text-slate-500 hover:text-slate-700"
      >
        ← All campaigns
      </Link>
      <PageHeader
        title={c.name}
        subtitle={`Goal: ${c.goal.target} ${c.goal.goal_type === "meetings" ? "meetings" : "positive replies"} · finding ${c.target_prospects} prospects`}
        actions={<CampaignStatusBadge status={c.status} />}
      />
      {isActive(c.status) && (
        <p className="mb-6 text-sm text-sky-700">
          Agents are working — wave {c.progress.waves}. This page updates
          itself.
        </p>
      )}
      {stop && <p className="mb-6 text-sm text-slate-600">{stop}</p>}
      {c.status === "failed" && (
        <div className="mb-6 flex items-start justify-between gap-4 rounded-md bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{c.last_error}</p>
          <button
            type="button"
            className={primaryButton}
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            Retry
          </button>
        </div>
      )}
      {c.status === "awaiting_approval" && (
        <section className={`${cardClass} mb-6`}>
          <h2 className="mb-1 text-sm font-semibold">
            Approve the first batch
          </h2>
          <ReviewQueue campaignId={c.id} />
        </section>
      )}
      {c.arms && c.arms.length > 0 && (
        <p className="mb-6 text-sm text-slate-600">
          A/B test:{" "}
          {c.arms
            .map(
              (a) =>
                `${a.key} = ${a.template_name} (${a.length}, ${a.cta} CTA)`,
            )
            .join(" vs ")}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
        <section className={cardClass}>
          <h2 className="mb-4 text-sm font-semibold">Funnel</h2>
          <Funnel funnel={c.funnel} />
        </section>
        <aside className={`${cardClass} space-y-3 text-sm`}>
          <Link
            to={`/prospects?campaign=${c.id}`}
            className="block font-medium text-indigo-700 hover:underline"
          >
            View prospects
          </Link>
          <Link
            to={`/inbox?campaign=${c.id}`}
            className="block font-medium text-indigo-700 hover:underline"
          >
            Open inbox
          </Link>
          {c.latest_run_id && (
            <Link
              to={`/workflow/runs/${c.latest_run_id}`}
              className="block font-medium text-indigo-700 hover:underline"
            >
              View agent run
            </Link>
          )}
        </aside>
      </div>
    </>
  );
}
