import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { CampaignOut } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { CampaignStatusBadge, isActive } from "../features/campaigns/status";

export function Campaigns() {
  const campaigns = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiFetch<CampaignOut[]>("/campaigns"),
    refetchInterval: (query) => (query.state.data?.some((c) => isActive(c.status)) ? 3000 : false),
  });

  return (
    <>
      <PageHeader title="Campaigns" subtitle="Each campaign finds companies and the right person at each." />
      {campaigns.isError && (
        <p role="alert" className="text-sm text-red-600">
          {campaigns.error.message}
        </p>
      )}
      {campaigns.data && campaigns.data.length === 0 && (
        <EmptyState title="No campaigns yet" body="Save an ICP in ICP Studio, then launch a campaign." />
      )}
      {campaigns.data && campaigns.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {["Name", "Status", "Prospects", "Created"].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {campaigns.data.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/campaigns/${c.id}`} className="font-medium text-indigo-700 hover:underline">
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <CampaignStatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{`${c.funnel.prospects} / ${c.target_prospects}`}</td>
                  <td className="px-4 py-3 text-slate-600">{new Date(c.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
