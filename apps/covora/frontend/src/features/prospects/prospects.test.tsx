import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Prospects } from "../../pages/Prospects";
import {
  CAMPAIGN_COMPLETE,
  COMPANIES,
  COMPANY_DETAIL,
  PROSPECTS,
} from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";

it("shows companies with criteria chips and opens facts", async () => {
  mockFetch({
    "GET /api/campaigns": [CAMPAIGN_COMPLETE],
    "GET /api/campaigns/c1/companies": COMPANIES,
    "GET /api/companies/co1": COMPANY_DETAIL,
  });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  await userEvent.click(await screen.findByText("Ohio Precision Fabrication"));
  const drawer = await screen.findByRole("dialog");
  expect(await within(drawer).findByText("Verified")).toBeInTheDocument();
  expect(
    within(drawer).getByRole("link", { name: /ohio-precision\.test/ }),
  ).toHaveAttribute("target", "_blank");
});

it("shows people with email status", async () => {
  mockFetch({
    "GET /api/campaigns": [CAMPAIGN_COMPLETE],
    "GET /api/campaigns/c1/companies": COMPANIES,
    "GET /api/campaigns/c1/prospects": PROSPECTS,
  });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  await userEvent.click(await screen.findByRole("tab", { name: "People" }));
  expect(await screen.findByText("Dana Ruiz")).toBeInTheDocument();
  expect(screen.getByText("No email")).toBeInTheDocument();
});

it("links CSV exports for the selected campaign", async () => {
  mockFetch({
    "GET /api/campaigns": [CAMPAIGN_COMPLETE],
    "GET /api/campaigns/c1/companies": COMPANIES,
  });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  expect(
    await screen.findByRole("link", { name: "Export companies CSV" }),
  ).toHaveAttribute("href", "/api/exports/companies.csv?campaign_id=c1");
});

it("shows empty state without campaigns", async () => {
  mockFetch({ "GET /api/campaigns": [] });
  renderWithQuery(<Prospects />, { route: "/prospects" });
  expect(await screen.findByText("No prospects yet")).toBeInTheDocument();
});
