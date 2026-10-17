import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function Campaigns() {
  return (
    <>
      <PageHeader title="Campaigns" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
