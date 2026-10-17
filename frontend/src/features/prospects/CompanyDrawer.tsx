import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";
import type { CompanyDetail, CompanyRow } from "../../api/types";
import { Drawer } from "./Drawer";
import { EmailBadge, EvidenceBadge } from "./EvidenceBadge";

const FIELD_LABELS: Record<string, string> = {
  employee_count: "Employees",
  revenue_usd: "Revenue (USD)",
  industry: "Industry",
  location: "Location",
  description: "About",
  founded_year: "Founded",
  recent_event: "Recent news",
};

export function CompanyDrawer({ row, onClose }: { row: CompanyRow; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["company", row.company_id],
    queryFn: () => apiFetch<CompanyDetail>(`/companies/${row.company_id}`),
  });
  return (
    <Drawer title={row.name} onClose={onClose}>
      <p className="mb-1 text-sm text-slate-500">{row.domain}</p>
      {row.reason && <p className="mb-6 text-sm text-slate-700">{row.reason}</p>}
      <h3 className="mb-2 text-sm font-semibold">Facts</h3>
      {detail.isPending && <p className="text-sm text-slate-400">Loading…</p>}
      {detail.isError && (
        <p role="alert" className="text-sm text-red-600">
          {detail.error.message}
        </p>
      )}
      {detail.data && detail.data.facts.length === 0 && <p className="text-sm text-slate-400">No facts found.</p>}
      <ul className="space-y-3">
        {detail.data?.facts.map((f, i) => (
          <li key={i} className="rounded-md border border-slate-200 p-3 text-sm">
            <div className="mb-1 flex items-center gap-2">
              <span className="font-medium">{FIELD_LABELS[f.field] ?? f.field}</span>
              <EvidenceBadge label={f.label} />
            </div>
            <p className="text-slate-900">{String(f.value)}</p>
            {f.quote && <p className="mt-1 italic text-slate-500">“{f.quote}”</p>}
            <a href={f.source_url} target="_blank" rel="noreferrer" className="mt-1 block break-all text-xs text-indigo-700 hover:underline">
              {f.source_url}
            </a>
          </li>
        ))}
      </ul>
      {detail.data && detail.data.contacts.length > 0 && (
        <>
          <h3 className="mb-2 mt-6 text-sm font-semibold">People found</h3>
          <ul className="space-y-2 text-sm">
            {detail.data.contacts.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2">
                <span>
                  {c.full_name} <span className="text-slate-500">· {c.title}</span>
                </span>
                <EmailBadge status={c.email_status} />
              </li>
            ))}
          </ul>
        </>
      )}
    </Drawer>
  );
}
