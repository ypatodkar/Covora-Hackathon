import type { Funnel as FunnelData } from "../../api/types";

const STEPS: {
  key: keyof FunnelData;
  label: string;
  aside?: { key: keyof FunnelData; label: string };
}[] = [
  { key: "candidates", label: "Companies found" },
  {
    key: "qualified",
    label: "Qualified",
    aside: { key: "rejected", label: "rejected" },
  },
  {
    key: "with_contacts",
    label: "With contacts",
    aside: { key: "no_contact", label: "no contact" },
  },
  { key: "prospects", label: "Prospects picked" },
];

export function Funnel({ funnel }: { funnel: FunnelData }) {
  const top = Math.max(funnel.candidates, 1);
  return (
    <ol className="space-y-3">
      {STEPS.map((step) => (
        <li key={step.key}>
          <div className="mb-1 flex items-baseline justify-between text-sm">
            <span className="font-medium text-slate-700">{step.label}</span>
            <span className="text-slate-900">
              {funnel[step.key]}
              {step.aside && funnel[step.aside.key] > 0 && (
                <span className="ml-2 text-xs text-slate-400">
                  {funnel[step.aside.key]} {step.aside.label}
                </span>
              )}
            </span>
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div
              className="h-2 rounded-full bg-indigo-500"
              style={{
                width: `${Math.round((100 * funnel[step.key]) / top)}%`,
              }}
            />
          </div>
        </li>
      ))}
      {funnel.needs_review > 0 && (
        <li className="text-xs text-amber-700">
          {funnel.needs_review} need review
        </li>
      )}
    </ol>
  );
}
