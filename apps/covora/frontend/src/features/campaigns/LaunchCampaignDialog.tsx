import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, postJson } from "../../api/client";
import type {
  CampaignOut,
  GoalType,
  IcpVersionOut,
  SizingEstimate,
  WorkspaceSettings,
} from "../../api/types";
import {
  inputClass,
  labelClass,
  primaryButton,
  secondaryButton,
} from "../../components/ui";
import { toFraction, toPercent } from "../settings/GoalsForm";

const n = (value: number) => value.toLocaleString("en-US");

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export function LaunchCampaignDialog({
  icpVersion,
  onClose,
}: {
  icpVersion: IcpVersionOut;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const settings = useQuery({
    queryKey: ["workspace-settings"],
    queryFn: () => apiFetch<WorkspaceSettings>("/workspace/settings"),
  });
  const [name, setName] = useState(icpVersion.structured.summary.slice(0, 60));
  const [goalType, setGoalType] = useState<GoalType>("positive_replies");
  const [target, setTarget] = useState("10");
  const [ratePercent, setRatePercent] = useState("1");
  const [meetingsPercent, setMeetingsPercent] = useState("50");
  const [limit, setLimit] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (settings.data && !loaded) {
      const g = settings.data.goals;
      setGoalType(g.goal_type);
      setTarget(String(g.target));
      setRatePercent(String(toPercent(g.expected_positive_rate)));
      setMeetingsPercent(String(toPercent(g.meetings_per_positive)));
      setLoaded(true);
    }
  }, [settings.data, loaded]);

  const goals = {
    goal_type: goalType,
    target: Number(target) || 1,
    expected_positive_rate: toFraction(Number(ratePercent) || 0.01),
    meetings_per_positive: toFraction(Number(meetingsPercent) || 50),
  };
  const prospectLimit = limit.trim() === "" ? null : Number(limit);
  const payload = useDebounced(
    { ...goals, prospect_limit: prospectLimit },
    400,
  );
  const estimate = useQuery({
    queryKey: ["estimate", payload],
    queryFn: () => postJson<SizingEstimate>("/campaigns/estimate", payload),
    enabled: loaded,
  });

  const launch = useMutation({
    mutationFn: async () => {
      const campaign = await postJson<CampaignOut>("/campaigns", {
        icp_version_id: icpVersion.id,
        name: name.trim() || "Campaign",
        goals,
        prospect_limit: prospectLimit,
      });
      return postJson<CampaignOut>(`/campaigns/${campaign.id}/run`, {});
    },
    onSuccess: (campaign) => navigate(`/campaigns/${campaign.id}`),
  });

  const e = estimate.data;
  const withinBudget = e
    ? e.fits_budget ||
      (prospectLimit !== null && prospectLimit <= e.max_affordable_prospects)
    : false;

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/30 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="launch-title"
        className="w-full max-w-xl rounded-xl bg-white p-6 shadow-xl"
      >
        <h2 id="launch-title" className="mb-5 text-lg font-semibold">
          Launch campaign
        </h2>
        <div className="space-y-4">
          <div>
            <label htmlFor="campaign-name" className={labelClass}>
              Campaign name
            </label>
            <input
              id="campaign-name"
              className={`${inputClass} mt-1`}
              value={name}
              onChange={(ev) => setName(ev.target.value)}
            />
          </div>
          <div className="flex gap-6">
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
                  name="launch-goal"
                  checked={goalType === value}
                  onChange={() => setGoalType(value)}
                />
                {label}
              </label>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="launch-target" className={labelClass}>
                Target
              </label>
              <input
                id="launch-target"
                type="number"
                min="1"
                className={`${inputClass} mt-1`}
                value={target}
                onChange={(ev) => setTarget(ev.target.value)}
              />
            </div>
            <div>
              <label htmlFor="launch-rate" className={labelClass}>
                Expected positive reply rate (%)
              </label>
              <input
                id="launch-rate"
                type="number"
                min="0"
                step="0.01"
                className={`${inputClass} mt-1`}
                value={ratePercent}
                onChange={(ev) => setRatePercent(ev.target.value)}
              />
            </div>
            {goalType === "meetings" && (
              <div>
                <label htmlFor="launch-meetings" className={labelClass}>
                  Meetings per positive reply (%)
                </label>
                <input
                  id="launch-meetings"
                  type="number"
                  min="0"
                  className={`${inputClass} mt-1`}
                  value={meetingsPercent}
                  onChange={(ev) => setMeetingsPercent(ev.target.value)}
                />
              </div>
            )}
            <div>
              <label htmlFor="launch-limit" className={labelClass}>
                Find up to
              </label>
              <input
                id="launch-limit"
                type="number"
                min="1"
                placeholder="All needed"
                className={`${inputClass} mt-1`}
                value={limit}
                onChange={(ev) => setLimit(ev.target.value)}
              />
            </div>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
            {!e && <p className="text-slate-400">Estimating…</p>}
            {e && (
              <div className="space-y-1">
                <p className="font-medium text-slate-900">
                  {`You need about ${n(e.prospects_needed)} prospects. This campaign will find ${n(e.prospects_planned)}.`}
                </p>
                <p>
                  {`≈ ${n(e.est_searches)} searches · $${e.est_youcom_usd.toFixed(2)} of You.com credit · ${n(e.est_model_calls)} model calls`}
                </p>
                <p>{`${n(e.gmail_emails)} via Gmail, ${n(e.in_app_emails)} delivered in-app`}</p>
                <p className="text-slate-500">
                  {`$${e.budget_remaining_usd.toFixed(2)} left · ${
                    e.cost_model_source === "measured"
                      ? "Based on your past campaigns"
                      : "Based on your expected rate"
                  }`}
                </p>
              </div>
            )}
          </div>
          {e && !e.fits_budget && (
            <p
              role="alert"
              className="rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-800"
            >
              This is more than your remaining budget — at most{" "}
              {n(e.max_affordable_prospects)} prospects fit.
            </p>
          )}
          {launch.isError && (
            <p role="alert" className="text-sm text-red-600">
              {launch.error.message}
            </p>
          )}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" className={secondaryButton} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={primaryButton}
            disabled={!withinBudget || launch.isPending}
            onClick={() => launch.mutate()}
          >
            Launch
          </button>
        </div>
      </div>
    </div>
  );
}
