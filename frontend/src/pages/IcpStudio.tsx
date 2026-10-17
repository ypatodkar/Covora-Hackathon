import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function IcpStudio() {
  return (
    <>
      <PageHeader title="ICP Studio" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
