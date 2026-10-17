import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function Prospects() {
  return (
    <>
      <PageHeader title="Prospects" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
