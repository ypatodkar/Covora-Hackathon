import type { ProspectRow } from "../../api/types";
import { Drawer } from "./Drawer";
import { EmailBadge } from "./EvidenceBadge";

export function ContactDrawer({ row, onClose }: { row: ProspectRow; onClose: () => void }) {
  const c = row.contact;
  return (
    <Drawer title={c.full_name} onClose={onClose}>
      <p className="mb-4 text-sm text-slate-600">
        {c.title} at {row.company.name}
      </p>
      <dl className="space-y-2 text-sm">
        <div>
          <dt className="text-slate-500">Why picked ({row.role}, {row.confidence} confidence)</dt>
          <dd>{row.pick_reason}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Email</dt>
          <dd className="flex items-center gap-2">
            {c.email ?? "—"} <EmailBadge status={c.email_status} />
          </dd>
        </div>
      </dl>
      <h3 className="mb-2 mt-6 text-sm font-semibold">Sources</h3>
      <ul className="space-y-1">
        {c.source_urls.map((url) => (
          <li key={url}>
            <a href={url} target="_blank" rel="noreferrer" className="break-all text-xs text-indigo-700 hover:underline">
              {url}
            </a>
          </li>
        ))}
      </ul>
    </Drawer>
  );
}
