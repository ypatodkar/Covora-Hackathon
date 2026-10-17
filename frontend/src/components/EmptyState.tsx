import type { ReactNode } from "react";

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 px-6 py-12 text-center">
      <p className="text-sm font-medium text-slate-900">{title}</p>
      {body && <p className="mt-1 text-sm text-slate-500">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
