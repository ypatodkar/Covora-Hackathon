import type { CriterionStatus, EvidenceLabel } from "../../api/types";

const EVIDENCE: Record<EvidenceLabel, [string, string]> = {
  verified: ["Verified", "bg-emerald-100 text-emerald-800"],
  unverified: ["Unverified", "bg-amber-100 text-amber-800"],
  unknown: ["Unknown", "bg-slate-100 text-slate-600"],
};

export function EvidenceBadge({ label }: { label: EvidenceLabel }) {
  const [text, style] = EVIDENCE[label] ?? EVIDENCE.unknown;
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{text}</span>;
}

const EMAIL: Record<string, [string, string]> = {
  verified: ["Email verified", "bg-emerald-100 text-emerald-800"],
  unverified: ["Email unverified", "bg-amber-100 text-amber-800"],
  missing: ["No email", "bg-slate-100 text-slate-600"],
};

export function EmailBadge({ status }: { status: string }) {
  const [text, style] = EMAIL[status] ?? EMAIL.missing;
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{text}</span>;
}

const CRITERION: Record<CriterionStatus, string> = {
  met: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  not_met: "bg-red-50 text-red-700 ring-red-200",
  unknown: "bg-slate-50 text-slate-500 ring-slate-200",
};

export const CRITERION_LABELS: Record<string, string> = {
  industry: "Industry",
  location: "Location",
  employee_range: "Size",
  revenue_range: "Revenue",
};

export function CriterionChip({ name, status }: { name: string; status: CriterionStatus }) {
  const label = CRITERION_LABELS[name] ?? (name.startsWith("exclusion") ? "Exclusion" : "Other");
  return (
    <span title={`${label}: ${status.replace("_", " ")}`} className={`rounded px-1.5 py-0.5 text-xs ring-1 ring-inset ${CRITERION[status]}`}>
      {label}
    </span>
  );
}

export function SyntheticBadge() {
  return <span className="rounded bg-violet-50 px-1.5 py-0.5 text-xs text-violet-700">Synthetic (mock web)</span>;
}
