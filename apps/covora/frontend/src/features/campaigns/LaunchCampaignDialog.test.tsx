import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  CAMPAIGN_DRAFT,
  ESTIMATE_1000,
  SETTINGS,
  VERSION,
} from "../../test/fixtures";
import { LocationProbe, mockFetch, renderWithQuery } from "../../test/utils";
import { LaunchCampaignDialog } from "./LaunchCampaignDialog";

it("shows the owner's example estimate", async () => {
  mockFetch({
    "GET /api/workspace/settings": SETTINGS,
    "POST /api/campaigns/estimate": ESTIMATE_1000,
  });
  renderWithQuery(
    <LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} />,
  );
  expect(await screen.findByText(/1,000/)).toBeInTheDocument();
  expect(screen.getByText(/\$44\.00/)).toBeInTheDocument();
  expect(
    screen.getByText(/100 via Gmail, 900 delivered in-app/),
  ).toBeInTheDocument();
});

it("blocks launch when over budget until capped", async () => {
  mockFetch({
    "GET /api/workspace/settings": SETTINGS,
    "POST /api/campaigns/estimate": {
      ...ESTIMATE_1000,
      fits_budget: false,
      max_affordable_prospects: 300,
    },
  });
  renderWithQuery(
    <LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "at most 300 prospects",
  );
  expect(screen.getByRole("button", { name: "Launch" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Find up to"), "200");
  expect(screen.getByRole("button", { name: "Launch" })).toBeEnabled();
});

it("creates, runs, and navigates", async () => {
  const calls = mockFetch({
    "GET /api/workspace/settings": SETTINGS,
    "POST /api/campaigns/estimate": ESTIMATE_1000,
    "POST /api/campaigns": CAMPAIGN_DRAFT,
    "POST /api/campaigns/c1/run": { ...CAMPAIGN_DRAFT, status: "queued" },
  });
  renderWithQuery(
    <>
      <LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} />
      <LocationProbe />
    </>,
  );
  await screen.findByText(/1,000/);
  await userEvent.click(screen.getByRole("button", { name: "Launch" }));
  await waitFor(() =>
    expect(screen.getByTestId("location")).toHaveTextContent("/campaigns/c1"),
  );
  expect(calls.body("POST /api/campaigns").icp_version_id).toBe("v1");
});
