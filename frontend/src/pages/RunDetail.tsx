import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function RunDetail() {
  return (
    <>
      <PageHeader title="Run" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
