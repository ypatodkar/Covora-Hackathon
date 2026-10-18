import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function Overview() {
  return (
    <>
      <PageHeader title="Overview" />
      <EmptyState
        title="Nothing here yet"
        body="This page arrives in a later plan."
      />
    </>
  );
}
