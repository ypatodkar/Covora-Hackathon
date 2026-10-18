const LABEL_STYLES: Record<string, string> = {
  interested: "bg-emerald-100 text-emerald-800",
  not_now: "bg-amber-100 text-amber-800",
  not_interested: "bg-slate-200 text-slate-700",
  wrong_person: "bg-violet-100 text-violet-800",
  unsubscribe: "bg-red-100 text-red-800",
  bounce: "bg-red-100 text-red-800",
  out_of_office: "bg-sky-100 text-sky-800",
  needs_review: "bg-orange-100 text-orange-800",
  other: "bg-slate-100 text-slate-700",
};

export function LabelBadge({
  label,
  confidence,
}: {
  label: string;
  confidence?: number | null;
}) {
  const text =
    confidence == null ? label : `${label} · ${Math.round(confidence * 100)}%`;
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${LABEL_STYLES[label] ?? LABEL_STYLES.other}`}
    >
      {text}
    </span>
  );
}

export const STATUS_TEXT: Record<string, string> = {
  sent: "Waiting for a reply",
  handed_off: "Handed off to sales",
  needs_review: "Needs your review",
  not_now: "Not now",
  closed_lost: "Closed",
  suppressed: "Unsubscribed",
  bounced: "Bounced",
  no_reply: "No reply: backup contacted",
  queued: "Queued",
};
