import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { CampaignOut, CompanyRow, ProspectRow } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { inputClass, secondaryButton } from "../components/ui";
import { CompaniesTable } from "../features/prospects/CompaniesTable";
import { CompanyDrawer } from "../features/prospects/CompanyDrawer";
import { ContactDrawer } from "../features/prospects/ContactDrawer";
import { PeopleTable } from "../features/prospects/PeopleTable";

type Tab = "companies" | "people";

export function Prospects() {
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>("companies");
  const [company, setCompany] = useState<CompanyRow | null>(null);
  const [person, setPerson] = useState<ProspectRow | null>(null);
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => apiFetch<CampaignOut[]>("/campaigns") });
  const campaignId = params.get("campaign") ?? campaigns.data?.[0]?.id ?? null;

  const companies = useQuery({
    queryKey: ["campaign-companies", campaignId],
    queryFn: () => apiFetch<CompanyRow[]>(`/campaigns/${campaignId}/companies`),
    enabled: campaignId !== null,
  });
  const people = useQuery({
    queryKey: ["campaign-prospects", campaignId],
    queryFn: () => apiFetch<ProspectRow[]>(`/campaigns/${campaignId}/prospects`),
    enabled: campaignId !== null && tab === "people",
  });

  if (campaigns.data && campaigns.data.length === 0) {
    return (
      <>
        <PageHeader title="Prospects" />
        <EmptyState title="No prospects yet" body="Launch a campaign from ICP Studio to find companies and people." />
      </>
    );
  }

  const exportHref = (kind: "companies" | "prospects") => `/api/exports/${kind}.csv?campaign_id=${campaignId}`;
  const tabClass = (t: Tab) =>
    `rounded-md px-3 py-1.5 text-sm ${tab === t ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;

  return (
    <>
      <PageHeader
        title="Prospects"
        subtitle="Every company and person Covora found, with why and where it came from."
        actions={
          campaignId && (
            <div className="flex gap-2">
              <a href={exportHref("companies")} className={secondaryButton}>
                Export companies CSV
              </a>
              <a href={exportHref("prospects")} className={secondaryButton}>
                Export people CSV
              </a>
            </div>
          )
        }
      />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <select
          aria-label="Campaign"
          className={`${inputClass} w-auto`}
          value={campaignId ?? ""}
          onChange={(e) => setParams({ campaign: e.target.value })}
        >
          {campaigns.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <div role="tablist" className="flex gap-1 rounded-lg bg-slate-50 p-1">
          <button type="button" role="tab" aria-selected={tab === "companies"} className={tabClass("companies")}
            onClick={() => setTab("companies")}>
            Companies
          </button>
          <button type="button" role="tab" aria-selected={tab === "people"} className={tabClass("people")}
            onClick={() => setTab("people")}>
            People
          </button>
        </div>
      </div>

      {tab === "companies" && companies.data && companies.data.length === 0 && (
        <EmptyState title="No companies yet" body="The campaign is still finding companies." />
      )}
      {tab === "companies" && companies.data && companies.data.length > 0 && (
        <CompaniesTable rows={companies.data} onOpen={setCompany} />
      )}
      {tab === "people" && people.data && people.data.length === 0 && (
        <EmptyState title="No people picked yet" body="People are picked after companies qualify." />
      )}
      {tab === "people" && people.data && people.data.length > 0 && <PeopleTable rows={people.data} onOpen={setPerson} />}
      {(companies.isError || people.isError) && (
        <p role="alert" className="text-sm text-red-600">
          {(companies.error ?? people.error)?.message}
        </p>
      )}

      {company && <CompanyDrawer row={company} onClose={() => setCompany(null)} />}
      {person && <ContactDrawer row={person} onClose={() => setPerson(null)} />}
    </>
  );
}
