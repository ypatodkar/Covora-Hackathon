import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function Inbox() {
  return (
    <>
      <PageHeader title="Inbox" />
      <EmptyState title="Nothing here yet" body="This page arrives in a later plan." />
    </>
  );
}
