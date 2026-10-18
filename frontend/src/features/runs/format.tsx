export const formatDuration = (ms: number | null) =>
  ms === null ? "—" : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;

export const formatCost = (usd: number | null) =>
  usd === null ? "—" : `$${usd.toFixed(4)}`;

export const formatTokens = (n: number) => n.toLocaleString();

export const STATUS_STYLES: Record<string, string> = {
  running: "bg-sky-100 text-sky-800",
  succeeded: "bg-emerald-100 text-emerald-800",
  ok: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  error: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? "bg-slate-100"}`}
    >
      {status}
    </span>
  );
}
