import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch, putJson } from "../../api/client";
import type { SimulationSettings, WorkspaceSettings } from "../../api/types";
import { inputClass, labelClass, primaryButton } from "../../components/ui";

const DEFAULT: SimulationSettings = {
  profile: "realistic",
  reply_delay_seconds: [5, 30],
  seed: 7,
};
const PROFILES = [
  ["realistic", "Realistic", "about 1% positive replies, like real cold email"],
  [
    "accelerated",
    "Accelerated",
    "about 6% positive replies, so a demo shows more activity",
  ],
] as const;

export function SimulationForm() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["workspace-settings"],
    queryFn: () => apiFetch<WorkspaceSettings>("/workspace/settings"),
  });
  const [sim, setSim] = useState<SimulationSettings | null>(null);
  const save = useMutation({
    mutationFn: (value: WorkspaceSettings) =>
      putJson<WorkspaceSettings>("/workspace/settings", value),
    onSuccess: (value) =>
      queryClient.setQueryData(["workspace-settings"], value),
  });

  useEffect(() => {
    if (settings.data && sim === null)
      setSim(settings.data.simulation ?? DEFAULT);
  }, [settings.data, sim]);

  if (settings.isError)
    return (
      <p role="alert" className="text-sm text-red-600">
        {settings.error.message}
      </p>
    );
  if (!settings.data || sim === null)
    return <p className="text-sm text-slate-500">Loading…</p>;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ ...settings.data!, simulation: sim });
  };
  const setDelay = (i: 0 | 1, value: string) => {
    const next: [number, number] = [...sim.reply_delay_seconds];
    next[i] = Number(value);
    setSim({ ...sim, reply_delay_seconds: next });
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <fieldset>
        <legend className={labelClass}>Reply profile</legend>
        <div className="mt-2 space-y-2">
          {PROFILES.map(([value, label, hint]) => (
            <label key={value} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="sim-profile"
                className="mt-1"
                checked={sim.profile === value}
                onChange={() => setSim({ ...sim, profile: value })}
              />
              <span>
                {label} <span className="text-slate-500">({hint})</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid max-w-md grid-cols-2 gap-4">
        <div>
          <label htmlFor="delay-min" className={labelClass}>
            Reply delay min (s)
          </label>
          <input
            id="delay-min"
            type="number"
            min="0"
            className={`${inputClass} mt-1`}
            value={sim.reply_delay_seconds[0]}
            onChange={(e) => setDelay(0, e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="delay-max" className={labelClass}>
            Reply delay max (s)
          </label>
          <input
            id="delay-max"
            type="number"
            min="0"
            className={`${inputClass} mt-1`}
            value={sim.reply_delay_seconds[1]}
            onChange={(e) => setDelay(1, e.target.value)}
          />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          className={primaryButton}
          disabled={save.isPending}
        >
          Save simulation
        </button>
        {save.isSuccess && (
          <span className="text-sm text-emerald-700">Saved</span>
        )}
        {save.isError && (
          <span role="alert" className="text-sm text-red-600">
            {save.error.message}
          </span>
        )}
      </div>
    </form>
  );
}
