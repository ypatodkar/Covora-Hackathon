import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch, putJson } from "../../api/client";
import type { GoalType, WorkspaceSettings } from "../../api/types";
import { inputClass, labelClass, primaryButton } from "../../components/ui";

// Rates are fractions in the API and percentages on screen.
export const toPercent = (fraction: number) =>
  Number((fraction * 100).toFixed(4));
export const toFraction = (percent: number) =>
  Number((percent / 100).toFixed(6));

interface FormState {
  goalType: GoalType;
  target: string;
  ratePercent: string;
  meetingsPercent: string;
  dailyCap: string;
  firstBatch: string;
}

function toForm(s: WorkspaceSettings): FormState {
  return {
    goalType: s.goals.goal_type,
    target: String(s.goals.target),
    ratePercent: String(toPercent(s.goals.expected_positive_rate)),
    meetingsPercent: String(toPercent(s.goals.meetings_per_positive)),
    dailyCap: String(s.sending.daily_gmail_cap),
    firstBatch: String(s.sending.first_batch_size),
  };
}

function NumberField({
  id,
  label,
  value,
  onChange,
  step,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  step?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      <input
        id={id}
        type="number"
        min="0"
        step={step ?? "1"}
        className={`${inputClass} mt-1`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export function GoalsForm() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["workspace-settings"],
    queryFn: () => apiFetch<WorkspaceSettings>("/workspace/settings"),
  });
  const [form, setForm] = useState<FormState | null>(null);
  const save = useMutation({
    mutationFn: (value: WorkspaceSettings) =>
      putJson<WorkspaceSettings>("/workspace/settings", value),
    onSuccess: (value) =>
      queryClient.setQueryData(["workspace-settings"], value),
  });

  useEffect(() => {
    if (settings.data && form === null) setForm(toForm(settings.data));
  }, [settings.data, form]);

  if (settings.isError)
    return (
      <p role="alert" className="text-sm text-red-600">
        {settings.error.message}
      </p>
    );
  if (form === null || !settings.data)
    return <p className="text-sm text-slate-500">Loading…</p>;

  const update = (patch: Partial<FormState>) => {
    save.reset();
    setForm({ ...form, ...patch });
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({
      ...settings.data,
      goals: {
        goal_type: form.goalType,
        target: Number(form.target),
        expected_positive_rate: toFraction(Number(form.ratePercent)),
        meetings_per_positive: toFraction(Number(form.meetingsPercent)),
      },
      sending: {
        ...settings.data.sending,
        daily_gmail_cap: Number(form.dailyCap),
        first_batch_size: Number(form.firstBatch),
      },
    });
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <fieldset>
        <legend className={labelClass}>Goal</legend>
        <div className="mt-2 flex gap-6">
          {(
            [
              ["positive_replies", "Positive replies"],
              ["meetings", "Meetings"],
            ] as const
          ).map(([value, label]) => (
            <label
              key={value}
              className="flex items-center gap-2 text-sm text-slate-700"
            >
              <input
                type="radio"
                name="goal-type"
                value={value}
                checked={form.goalType === value}
                onChange={() => update({ goalType: value })}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-5 sm:grid-cols-3">
        <NumberField
          id="goal-target"
          label="Target"
          value={form.target}
          onChange={(target) => update({ target })}
        />
        <NumberField
          id="goal-rate"
          label="Expected positive reply rate (%)"
          step="0.01"
          value={form.ratePercent}
          onChange={(ratePercent) => update({ ratePercent })}
        />
        {form.goalType === "meetings" && (
          <NumberField
            id="goal-meetings"
            label="Meetings per positive reply (%)"
            step="1"
            value={form.meetingsPercent}
            onChange={(meetingsPercent) => update({ meetingsPercent })}
          />
        )}
      </div>
      <div className="grid gap-5 sm:grid-cols-3">
        <NumberField
          id="daily-cap"
          label="Daily Gmail limit"
          value={form.dailyCap}
          onChange={(dailyCap) => update({ dailyCap })}
        />
        <NumberField
          id="first-batch"
          label="First batch to review"
          value={form.firstBatch}
          onChange={(firstBatch) => update({ firstBatch })}
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          className={primaryButton}
          disabled={save.isPending}
        >
          Save
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
