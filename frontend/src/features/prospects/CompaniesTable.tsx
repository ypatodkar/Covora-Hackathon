import type { CompanyRow } from "../../api/types";
import { CriterionChip, SyntheticBadge } from "./EvidenceBadge";

const STATUS_LABELS: Record<string, string> = {
  contact_selected: "Contact picked",
  qualified: "Qualified",
  no_contact: "No contact",
  needs_review: "Needs review",
  rejected: "Rejected",
  candidate: "Scoring…",
};

export function CompaniesTable({
  rows,
  onOpen,
}: {
  rows: CompanyRow[];
  onOpen: (row: CompanyRow) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {["Company", "Fit", "Status", "Why", "Criteria"].map((h) => (
              <th key={h} className="px-4 py-3 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr
              key={r.company_id}
              className="cursor-pointer align-top hover:bg-slate-50"
              onClick={() => onOpen(r)}
            >
              <td className="px-4 py-3">
                <button
                  type="button"
                  className="text-left font-medium text-indigo-700 hover:underline"
                >
                  {r.name}
                </button>
                <div className="text-xs text-slate-500">{r.domain}</div>
                {r.synthetic && <SyntheticBadge />}
              </td>
              <td className="px-4 py-3 text-slate-700">
                {r.fit_score ?? "—"}
                {r.confidence && (
                  <div className="text-xs text-slate-400">{r.confidence}</div>
                )}
              </td>
              <td className="px-4 py-3 text-slate-600">
                {STATUS_LABELS[r.status] ?? r.status}
              </td>
              <td className="max-w-xs px-4 py-3 text-slate-600">{r.reason}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {r.criteria.map((c) => (
                    <CriterionChip
                      key={c.name}
                      name={c.name}
                      status={c.status}
                    />
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
