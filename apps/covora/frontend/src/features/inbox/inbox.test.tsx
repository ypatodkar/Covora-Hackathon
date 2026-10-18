import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ThreadDetail, ThreadRow } from "../../api/types";
import { Inbox } from "../../pages/Inbox";
import { mockFetch, renderWithQuery } from "../../test/utils";

const contact = {
  id: "ct1",
  full_name: "Ana Ruiz",
  title: "VP Ops",
  email: "ana@acme.test",
  synthetic: true,
};
const company = {
  id: "co1",
  name: "Acme Fab",
  domain: "acme.test",
  synthetic: true,
};
const ROW: ThreadRow = {
  prospect_id: "p1",
  campaign_id: "c1",
  contact,
  company,
  status: "handed_off",
  meeting_booked: false,
  simulated: true,
  message_count: 2,
  last_message_at: "2026-10-17T10:00:00Z",
  last_label: "interested",
};
const msg = {
  cc: [],
  sent_at: null,
  received_at: null,
  created_at: "2026-10-17T10:00:00Z",
  error: null,
  summary: null,
};
const DETAIL: ThreadDetail = {
  prospect: {
    id: "p1",
    campaign_id: "c1",
    role: "primary",
    status: "handed_off",
    arm_key: "A",
    pick_reason: "Runs operations",
    meeting_booked_at: null,
    meeting_synthetic: false,
  },
  contact,
  company,
  rep: null,
  messages: [
    { ...msg, id: "m1", direction: "out", kind: "cold", subject: "Quick idea", body: "Hi Ana", status: "sent",
      delivery: "in_app", source: "in_app_sim", intended_to: "ana@acme.test", actual_to: "in-app", label: null, confidence: null }, // prettier-ignore
    { ...msg, id: "m2", direction: "in", kind: "inbound", subject: "Re: Quick idea", body: "Sounds interesting", status: "received",
      delivery: null, source: "in_app_sim", intended_to: null, actual_to: null, label: "interested", confidence: 0.92 }, // prettier-ignore
  ],
};

const routes = (extra = {}) => ({
  "GET /api/inbox/threads": [ROW, { ...ROW, prospect_id: "p2", last_label: "not_now", status: "not_now",
    contact: { ...contact, id: "ct2", full_name: "Ben Ode" } }], // prettier-ignore
  "GET /api/inbox/threads?filter=interested": [ROW],
  "GET /api/inbox/threads/p1": DETAIL,
  ...extra,
});

it("filters threads", async () => {
  mockFetch(routes());
  renderWithQuery(<Inbox />, { route: "/inbox" });
  expect(await screen.findByText("Ben Ode")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Interested" }));
  await waitFor(() =>
    expect(screen.queryByText("Ben Ode")).not.toBeInTheDocument(),
  );
  expect(screen.getAllByText("Ana Ruiz").length).toBeGreaterThan(0);
});

it("shows simulated delivery badge", async () => {
  mockFetch(routes());
  renderWithQuery(<Inbox />, { route: "/inbox" });
  await userEvent.click(
    await screen.findByRole("button", { name: /Ana Ruiz/ }),
  );
  expect(
    await screen.findByText(
      "Simulated: delivered in-app (intended for ana@acme.test)",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("interested · 92%")).toBeInTheDocument();
});

it("sends a manual reply", async () => {
  const calls = mockFetch(
    routes({
      "POST /api/inbox/threads/p1/reply": { id: "m3", status: "queued" },
    }),
  );
  renderWithQuery(<Inbox />, { route: "/inbox" });
  await userEvent.click(
    await screen.findByRole("button", { name: /Ana Ruiz/ }),
  );
  await userEvent.type(await screen.findByLabelText("Reply"), "Thanks Ana");
  await userEvent.click(screen.getByRole("button", { name: "Send reply" }));
  await waitFor(() =>
    expect(calls.body("POST /api/inbox/threads/p1/reply")).toEqual({
      body: "Thanks Ana",
    }),
  );
});

it("marks meeting", async () => {
  const calls = mockFetch(
    routes({
      "POST /api/prospects/p1/meeting": { id: "p1", meeting_booked_at: "now" },
    }),
  );
  renderWithQuery(<Inbox />, { route: "/inbox" });
  await userEvent.click(
    await screen.findByRole("button", { name: /Ana Ruiz/ }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Mark meeting booked" }),
  );
  await waitFor(() =>
    expect(calls.fn).toHaveBeenCalledWith(
      "/api/prospects/p1/meeting",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
