import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReviewDraft } from "../../api/types";
import { mockFetch, renderWithQuery } from "../../test/utils";
import { ReviewQueue } from "./ReviewQueue";

const draft = (
  id: string,
  name: string,
  extra: Partial<ReviewDraft> = {},
): ReviewDraft => ({
  id,
  prospect_id: `p-${id}`,
  arm_key: "A",
  kind: "cold",
  status: "draft",
  subject: `Hello ${name}`,
  body: `Hi ${name}, short note.`,
  problems: [],
  intended_to: `${name.toLowerCase()}@acme.test`,
  contact: { full_name: name, title: "VP Operations" },
  company: { name: `${name} Co`, domain: "acme.test" },
  ...extra,
});

it("approves selected drafts", async () => {
  const calls = mockFetch({
    "GET /api/campaigns/c1/review": [draft("e1", "Ana"), draft("e2", "Ben")],
    "POST /api/campaigns/c1/approve": { id: "c1", status: "queued" },
  });
  renderWithQuery(<ReviewQueue campaignId="c1" />);
  expect(await screen.findByText("Hello Ana")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Approve email to Ben" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Approve 1 and send" }),
  );
  await waitFor(() =>
    expect(calls.body("POST /api/campaigns/c1/approve")).toEqual({
      approved: ["e1"],
      rejected: ["e2"],
    }),
  );
});

it("edits a draft", async () => {
  const calls = mockFetch({
    "GET /api/campaigns/c1/review": [draft("e1", "Ana")],
    "PATCH /api/emails/e1": draft("e1", "Ana", { subject: "New subject" }),
  });
  renderWithQuery(<ReviewQueue campaignId="c1" />);
  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const subject = screen.getByLabelText("Subject");
  await userEvent.clear(subject);
  await userEvent.type(subject, "New subject");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(calls.body("PATCH /api/emails/e1")).toMatchObject({
      subject: "New subject",
    }),
  );
});
