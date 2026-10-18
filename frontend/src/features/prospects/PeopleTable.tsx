import type { ProspectRow } from "../../api/types";
import { EmailBadge, SyntheticBadge } from "./EvidenceBadge";

export function PeopleTable({
  rows,
  onOpen,
}: {
  rows: ProspectRow[];
  onOpen: (row: ProspectRow) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {[
              "Name",
              "Title",
              "Company",
              "Role",
              "Why picked",
              "Confidence",
              "Email",
            ].map((h) => (
              <th key={h} className="px-4 py-3 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr
              key={r.prospect_id}
              className="cursor-pointer align-top hover:bg-slate-50"
              onClick={() => onOpen(r)}
            >
              <td className="px-4 py-3">
                <button
                  type="button"
                  className="text-left font-medium text-indigo-700 hover:underline"
                >
                  {r.contact.full_name}
                </button>
                {r.synthetic && <SyntheticBadge />}
              </td>
              <td className="px-4 py-3 text-slate-600">{r.contact.title}</td>
              <td className="px-4 py-3 text-slate-600">{r.company.name}</td>
              <td className="px-4 py-3 text-slate-600">
                {r.role === "primary" ? "Primary" : "Backup"}
              </td>
              <td className="max-w-xs px-4 py-3 text-slate-600">
                {r.pick_reason}
              </td>
              <td className="px-4 py-3 text-slate-600">{r.confidence}</td>
              <td className="px-4 py-3">
                <div className="text-xs text-slate-600">{r.contact.email}</div>
                <EmailBadge status={r.contact.email_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
