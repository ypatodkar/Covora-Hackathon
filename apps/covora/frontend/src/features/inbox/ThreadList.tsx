import type { ThreadRow } from "../../api/types";
import { LabelBadge, STATUS_TEXT } from "./labels";

export function ThreadList({
  threads,
  selected,
  onSelect,
}: {
  threads: ThreadRow[];
  selected: string | null;
  onSelect: (prospectId: string) => void;
}) {
  return (
    <ul className="divide-y divide-slate-100">
      {threads.map((t) => (
        <li key={t.prospect_id}>
          <button
            type="button"
            onClick={() => onSelect(t.prospect_id)}
            className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${selected === t.prospect_id ? "bg-indigo-50" : ""}`}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-slate-900">
                {t.contact.full_name}
              </span>
              {t.last_label && <LabelBadge label={t.last_label} />}
            </span>
            <span className="block truncate text-xs text-slate-500">
              {t.company.name} · {STATUS_TEXT[t.status] ?? t.status}
              {t.meeting_booked ? " · meeting booked" : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
