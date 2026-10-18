import type { Origin } from "../../api/types";

export function OriginBadge({ origin }: { origin: Origin }) {
  return origin === "stated" ? (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      You said
    </span>
  ) : (
    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
      Inferred
    </span>
  );
}

export function originRowClass(origin: Origin): string {
  return origin === "inferred"
    ? "border-l-2 border-amber-400 pl-3"
    : "border-l-2 border-transparent pl-3";
}
