import { PageHeader } from "../components/PageHeader";
import { cardClass } from "../components/ui";
import { CompanyProfileForm } from "../features/settings/CompanyProfileForm";
import { GoalsForm } from "../features/settings/GoalsForm";

export function Settings() {
  return (
    <>
      <PageHeader title="Settings" />
      <section className={cardClass}>
        <h2 className="mb-1 text-base font-semibold">Company</h2>
        <p className="mb-6 text-sm text-slate-500">Covora's agents use this to understand what you sell.</p>
        <CompanyProfileForm />
      </section>
      <section className={`${cardClass} mt-6`}>
        <h2 className="mb-1 text-base font-semibold">Goals & sending</h2>
        <p className="mb-6 text-sm text-slate-500">
          Covora sizes each campaign from your goal: prospects needed = goal ÷ expected rate.
        </p>
        <GoalsForm />
      </section>
    </>
  );
}
