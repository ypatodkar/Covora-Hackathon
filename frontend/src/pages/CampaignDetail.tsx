import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function CampaignDetail() {
  return (
    <>
      <PageHeader title="Campaign" />
      <EmptyState title="Nothing here yet" body="Campaign details arrive in the next task." />
    </>
  );
}
