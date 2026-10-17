import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch, putJson } from "../../api/client";
import type { OfferingType, WorkspaceOut, WorkspaceProfile } from "../../api/types";
import { inputClass, labelClass, primaryButton } from "../../components/ui";

interface FormState {
  name: string;
  website: string;
  description: string;
  proofPoints: string;
  offeringType: OfferingType;
}

function toForm(ws: WorkspaceOut): FormState {
  return {
    name: ws.name,
    website: ws.website ?? "",
    description: ws.description ?? "",
    proofPoints: ws.value_props.join("\n"),
    offeringType: ws.offering_type,
  };
}

function toProfile(form: FormState): WorkspaceProfile {
  return {
    name: form.name.trim(),
    website: form.website.trim() || null,
    description: form.description.trim() || null,
    value_props: form.proofPoints
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    offering_type: form.offeringType,
  };
}

const OFFERINGS: { value: OfferingType; label: string }[] = [
  { value: "sales_call", label: "Needs a sales call" },
  { value: "dealer", label: "Bulk product for dealers" },
];

export function CompanyProfileForm() {
  const queryClient = useQueryClient();
  const workspace = useQuery({ queryKey: ["workspace"], queryFn: () => apiFetch<WorkspaceOut>("/workspace") });
  const [form, setForm] = useState<FormState | null>(null);
  const save = useMutation({
    mutationFn: (profile: WorkspaceProfile) => putJson<WorkspaceOut>("/workspace", profile),
    onSuccess: (ws) => queryClient.setQueryData(["workspace"], ws),
  });

  useEffect(() => {
    if (workspace.data && form === null) setForm(toForm(workspace.data));
  }, [workspace.data, form]);

  if (workspace.isError) return <p role="alert" className="text-sm text-red-600">{workspace.error.message}</p>;
  if (form === null) return <p className="text-sm text-slate-500">Loading…</p>;

  const update = (patch: Partial<FormState>) => {
    save.reset();
    setForm({ ...form, ...patch });
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(toProfile(form));
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="company-name" className={labelClass}>
            Company name
          </label>
          <input
            id="company-name"
            className={`${inputClass} mt-1`}
            value={form.name}
            onChange={(e) => update({ name: e.target.value })}
            required
          />
        </div>
        <div>
          <label htmlFor="company-website" className={labelClass}>
            Website
          </label>
          <input
            id="company-website"
            className={`${inputClass} mt-1`}
            value={form.website}
            placeholder="https://"
            onChange={(e) => update({ website: e.target.value })}
          />
        </div>
      </div>
      <div>
        <label htmlFor="company-description" className={labelClass}>
          What you sell
        </label>
        <textarea
          id="company-description"
          className={`${inputClass} mt-1`}
          rows={3}
          value={form.description}
          placeholder="The product or service, and the problem it solves"
          onChange={(e) => update({ description: e.target.value })}
        />
      </div>
      <div>
        <label htmlFor="company-proof" className={labelClass}>
          Proof points
        </label>
        <textarea
          id="company-proof"
          className={`${inputClass} mt-1`}
          rows={3}
          value={form.proofPoints}
          placeholder="One per line"
          onChange={(e) => update({ proofPoints: e.target.value })}
        />
      </div>
      <fieldset>
        <legend className={labelClass}>Offering type</legend>
        <div className="mt-2 flex gap-6">
          {OFFERINGS.map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="radio"
                name="offering-type"
                value={o.value}
                checked={form.offeringType === o.value}
                onChange={() => update({ offeringType: o.value })}
              />
              {o.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex items-center gap-3">
        <button type="submit" className={primaryButton} disabled={save.isPending}>
          Save
        </button>
        {save.isSuccess && <span className="text-sm text-emerald-700">Saved</span>}
        {save.isError && (
          <span role="alert" className="text-sm text-red-600">
            {save.error.message}
          </span>
        )}
      </div>
    </form>
  );
}
