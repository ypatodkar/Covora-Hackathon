import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function Settings() {
  return (
    <>
      <PageHeader title="Settings" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
