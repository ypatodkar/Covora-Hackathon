import type { CampaignStatus } from "../../api/types";

const STYLES: Record<CampaignStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  queued: "bg-sky-100 text-sky-800",
  running: "bg-sky-100 text-sky-800",
  awaiting_approval: "bg-amber-100 text-amber-800",
  sending: "bg-indigo-100 text-indigo-800",
  complete: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export const STOP_REASONS: Record<string, string> = {
  enough_qualified: "Stopped: found enough qualified companies",
  budget: "Stopped: You.com budget reached",
  no_new_companies: "Stopped: no new companies found",
  max_waves: "Stopped: reached the wave limit",
};

export const isActive = (status: CampaignStatus) =>
  status === "queued" || status === "running" || status === "sending";
