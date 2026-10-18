import { PageHeader } from "../components/PageHeader";
import { cardClass } from "../components/ui";
import { CompanyProfileForm } from "../features/settings/CompanyProfileForm";
import { GoalsForm } from "../features/settings/GoalsForm";
import { SalesTeamForm } from "../features/settings/SalesTeamForm";
import { SimulationForm } from "../features/settings/SimulationForm";

export function Settings() {
  return (
    <>
      <PageHeader title="Settings" />
      <section className={cardClass}>
        <h2 className="mb-1 text-base font-semibold">Company</h2>
        <p className="mb-6 text-sm text-slate-500">
          Covora's agents use this to understand what you sell.
        </p>
        <CompanyProfileForm />
      </section>
      <section className={`${cardClass} mt-6`}>
        <h2 className="mb-1 text-base font-semibold">Goals & sending</h2>
        <p className="mb-6 text-sm text-slate-500">
          Covora sizes each campaign from your goal: prospects needed = goal ÷
          expected rate.
        </p>
        <GoalsForm />
      </section>
      <section className={`${cardClass} mt-6`}>
        <h2 className="mb-1 text-base font-semibold">Sales team</h2>
        <p className="mb-6 text-sm text-slate-500">
          Interested replies go to these reps in turn, with their booking link.
          Covora never quotes prices.
        </p>
        <SalesTeamForm />
      </section>
      <section className={`${cardClass} mt-6`}>
        <h2 className="mb-1 text-base font-semibold">Simulation</h2>
        <p className="mb-6 text-sm text-slate-500">
          No email reaches a real person. Simulated prospects reply according to
          this profile.
        </p>
        <SimulationForm />
      </section>
    </>
  );
}
