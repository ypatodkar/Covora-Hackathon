import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CampaignDetail } from "../../pages/CampaignDetail";
import { Campaigns } from "../../pages/Campaigns";
import { CAMPAIGN_COMPLETE, CAMPAIGN_FAILED } from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";

it("lists campaigns or shows empty state", async () => {
  mockFetch({ "GET /api/campaigns": [] });
  renderWithQuery(<Campaigns />, { route: "/campaigns" });
  expect(await screen.findByText("No campaigns yet")).toBeInTheDocument();
});

it("lists campaigns with prospects found vs target", async () => {
  mockFetch({ "GET /api/campaigns": [CAMPAIGN_COMPLETE] });
  renderWithQuery(<Campaigns />, { route: "/campaigns" });
  expect(await screen.findByRole("link", { name: "Ohio fab" })).toHaveAttribute(
    "href",
    "/campaigns/c1",
  );
  expect(screen.getByText("3 / 3")).toBeInTheDocument();
});

it("shows funnel and stop reason", async () => {
  mockFetch({ "GET /api/campaigns/c1": CAMPAIGN_COMPLETE });
  renderWithQuery(<CampaignDetail />, {
    route: "/campaigns/c1",
    path: "/campaigns/:campaignId",
  });
  expect(
    await screen.findByText("Stopped: found enough qualified companies"),
  ).toBeInTheDocument();
  expect(screen.getByText("Prospects picked")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View prospects" })).toHaveAttribute(
    "href",
    "/prospects?campaign=c1",
  );
  expect(screen.getByRole("link", { name: "View agent run" })).toHaveAttribute(
    "href",
    "/workflow/runs/r1",
  );
});

it("retries a failed campaign", async () => {
  const calls = mockFetch({
    "GET /api/campaigns/c2": CAMPAIGN_FAILED,
    "POST /api/campaigns/c2/retry": { ...CAMPAIGN_FAILED, status: "queued" },
  });
  renderWithQuery(<CampaignDetail />, {
    route: "/campaigns/c2",
    path: "/campaigns/:campaignId",
  });
  expect(
    await screen.findByText(/all model attempts failed/),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(calls.fn).toHaveBeenCalledWith(
    "/api/campaigns/c2/retry",
    expect.objectContaining({ method: "POST" }),
  );
});
