import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch, patchJson, postJson } from "../../api/client";
import type { CampaignOut, ReviewDraft } from "../../api/types";
import {
  inputClass,
  labelClass,
  primaryButton,
  secondaryButton,
} from "../../components/ui";

function DraftCard({
  draft,
  approved,
  onToggle,
}: {
  draft: ReviewDraft;
  approved: boolean;
  onToggle: () => void;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const save = useMutation({
    mutationFn: () =>
      patchJson<ReviewDraft>(`/emails/${draft.id}`, { subject, body }),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    },
  });
  const to = draft.contact?.full_name ?? "unknown";

  return (
    <li
      className={`rounded-lg border p-4 ${approved ? "border-slate-200 bg-white" : "border-slate-200 bg-slate-50 opacity-70"}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">
            {to}{" "}
            <span className="font-normal text-slate-500">
              · {draft.contact?.title} at {draft.company?.name}
            </span>
          </p>
          <p className="text-xs text-slate-500">
            Arm {draft.arm_key ?? "–"} · intended for{" "}
            {draft.intended_to ?? "no address"} · delivered in-app only
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={approved}
            onChange={onToggle}
            aria-label={`Approve email to ${to}`}
          />
          Send
        </label>
      </div>
      {draft.problems.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-amber-700">
          {draft.problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {editing ? (
        <div className="mt-3 space-y-3">
          <div>
            <label htmlFor={`subject-${draft.id}`} className={labelClass}>
              Subject
            </label>
            <input
              id={`subject-${draft.id}`}
              className={`${inputClass} mt-1`}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor={`body-${draft.id}`} className={labelClass}>
              Body
            </label>
            <textarea
              id={`body-${draft.id}`}
              rows={8}
              className={`${inputClass} mt-1`}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className={primaryButton}
              disabled={save.isPending}
              onClick={() => save.mutate()}
            >
              Save
            </button>
            <button
              type="button"
              className={secondaryButton}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
          {save.isError && (
            <p role="alert" className="text-sm text-red-600">
              {save.error.message}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-3">
          <p className="text-sm font-medium text-slate-800">{draft.subject}</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
            {draft.body}
          </p>
          <button
            type="button"
            className={`${secondaryButton} mt-3`}
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        </div>
      )}
    </li>
  );
}

export function ReviewQueue({ campaignId }: { campaignId: string }) {
  const queryClient = useQueryClient();
  const drafts = useQuery({
    queryKey: ["review", campaignId],
    queryFn: () => apiFetch<ReviewDraft[]>(`/campaigns/${campaignId}/review`),
  });
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  const approve = useMutation({
    mutationFn: (value: { approved: string[]; rejected: string[] }) =>
      postJson<CampaignOut>(`/campaigns/${campaignId}/approve`, value),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["campaign", campaignId],
      });
    },
  });

  if (drafts.isError)
    return (
      <p role="alert" className="text-sm text-red-600">
        {drafts.error.message}
      </p>
    );
  if (!drafts.data)
    return <p className="text-sm text-slate-500">Loading drafts…</p>;
  const list = drafts.data;
  const approvedIds = list.filter((d) => !rejected.has(d.id)).map((d) => d.id);
  const toggle = (id: string) =>
    setRejected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-4">
        <p className="text-sm text-slate-600">
          Review the first batch. Approved emails go out, and the rest of the
          campaign then sends on its own.
        </p>
        <button
          type="button"
          className={primaryButton}
          disabled={approve.isPending || list.length === 0}
          onClick={() =>
            approve.mutate({
              approved: approvedIds,
              rejected: list.filter((d) => rejected.has(d.id)).map((d) => d.id),
            })
          }
        >
          Approve {approvedIds.length} and send
        </button>
      </div>
      {approve.isError && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          {approve.error.message}
        </p>
      )}
      <ul className="space-y-3">
        {list.map((d) => (
          <DraftCard
            key={d.id}
            draft={d}
            approved={!rejected.has(d.id)}
            onToggle={() => toggle(d.id)}
          />
        ))}
      </ul>
    </div>
  );
}
