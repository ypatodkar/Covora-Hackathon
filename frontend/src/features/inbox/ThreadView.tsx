import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { apiFetch, postJson } from "../../api/client";
import type { ThreadDetail, ThreadMessage } from "../../api/types";
import {
  inputClass,
  labelClass,
  primaryButton,
  secondaryButton,
} from "../../components/ui";
import { LabelBadge, STATUS_TEXT } from "./labels";

const KIND_TEXT: Record<string, string> = {
  cold: "Cold email",
  handoff: "Handoff to sales",
  manual_reply: "Your reply",
  inbound: "Their reply",
};

function Message({ m }: { m: ThreadMessage }) {
  const when = m.received_at ?? m.sent_at ?? m.created_at;
  return (
    <li
      className={`rounded-lg border p-4 ${m.direction === "in" ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200 bg-white"}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          <span className="font-medium text-slate-700">
            {KIND_TEXT[m.kind] ?? m.kind}
          </span>{" "}
          · {m.status} · {new Date(when).toLocaleString()}
        </span>
        {m.label && <LabelBadge label={m.label} confidence={m.confidence} />}
      </div>
      {m.direction === "out" && (
        <p className="mt-2 inline-block rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
          {m.status === "sent" || m.delivery === "in_app"
            ? `Simulated: delivered in-app (intended for ${m.intended_to ?? "no address"})`
            : `Not sent yet · intended for ${m.intended_to ?? "no address"}`}
          {m.cc.length > 0 ? ` · cc ${m.cc.join(", ")}` : ""}
        </p>
      )}
      {m.direction === "in" && m.source && (
        <p className="mt-2 text-xs text-slate-500">Simulated reply</p>
      )}
      <p className="mt-2 text-sm font-medium text-slate-800">{m.subject}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
        {m.body}
      </p>
      {m.summary && (
        <p className="mt-2 text-xs text-slate-500">Agent's read: {m.summary}</p>
      )}
      {m.error && <p className="mt-2 text-xs text-orange-700">{m.error}</p>}
    </li>
  );
}

export function ThreadView({ prospectId }: { prospectId: string }) {
  const queryClient = useQueryClient();
  const thread = useQuery({
    queryKey: ["thread", prospectId],
    queryFn: () => apiFetch<ThreadDetail>(`/inbox/threads/${prospectId}`),
    refetchInterval: 5000,
  });
  const [reply, setReply] = useState("");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["thread", prospectId] });
    void queryClient.invalidateQueries({ queryKey: ["threads"] });
  };
  const send = useMutation({
    mutationFn: () =>
      postJson(`/inbox/threads/${prospectId}/reply`, { body: reply }),
    onSuccess: () => {
      setReply("");
      refresh();
    },
  });
  const meeting = useMutation({
    mutationFn: () => postJson(`/prospects/${prospectId}/meeting`, {}),
    onSuccess: refresh,
  });

  if (thread.isError)
    return (
      <p role="alert" className="text-sm text-red-600">
        {thread.error.message}
      </p>
    );
  if (!thread.data) return <p className="text-sm text-slate-500">Loading…</p>;
  const t = thread.data;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send.mutate();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            {t.contact.full_name}
          </h2>
          <p className="text-sm text-slate-500">
            {t.contact.title} · {t.company.name}
            {t.company.synthetic ? " · synthetic" : ""}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {STATUS_TEXT[t.prospect.status] ?? t.prospect.status}
            {t.rep ? ` · rep: ${t.rep.name}` : ""}
            {t.prospect.meeting_booked_at
              ? ` · meeting booked${t.prospect.meeting_synthetic ? " (simulated)" : ""}`
              : ""}
          </p>
        </div>
        <button
          type="button"
          className={secondaryButton}
          disabled={meeting.isPending}
          onClick={() => meeting.mutate()}
        >
          Mark meeting booked
        </button>
      </div>
      <ul className="space-y-3">
        {t.messages.map((m) => (
          <Message key={m.id} m={m} />
        ))}
      </ul>
      <form onSubmit={onSubmit} className="space-y-2">
        <label htmlFor="manual-reply" className={labelClass}>
          Reply
        </label>
        <textarea
          id="manual-reply"
          rows={3}
          className={inputClass}
          value={reply}
          onChange={(e) => setReply(e.target.value)}
        />
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className={primaryButton}
            disabled={send.isPending || !reply.trim()}
          >
            Send reply
          </button>
          <span className="text-xs text-slate-500">
            Delivered in-app only. No email reaches a real person.
          </span>
        </div>
        {send.isError && (
          <p role="alert" className="text-sm text-red-600">
            {send.error.message}
          </p>
        )}
      </form>
    </div>
  );
}
