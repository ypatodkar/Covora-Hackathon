import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SETTINGS } from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";
import { GoalsForm } from "./GoalsForm";

it("shows rates as percentages and saves fractions", async () => {
  const calls = mockFetch({
    "GET /api/workspace/settings": SETTINGS,
    "PUT /api/workspace/settings": SETTINGS,
  });
  renderWithQuery(<GoalsForm />);
  const rate = await screen.findByLabelText("Expected positive reply rate (%)");
  expect(rate).toHaveValue(1);
  await userEvent.clear(rate);
  await userEvent.type(rate, "2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved")).toBeInTheDocument();
  const goals = calls.body("PUT /api/workspace/settings").goals as {
    expected_positive_rate: number;
  };
  expect(goals.expected_positive_rate).toBeCloseTo(0.02);
});

it("shows meetings rate only for meetings goal", async () => {
  mockFetch({ "GET /api/workspace/settings": SETTINGS });
  renderWithQuery(<GoalsForm />);
  expect(await screen.findByLabelText("Target")).toBeInTheDocument();
  expect(screen.queryByLabelText("Meetings per positive reply (%)")).toBeNull();
  await userEvent.click(screen.getByLabelText("Meetings"));
  expect(
    screen.getByLabelText("Meetings per positive reply (%)"),
  ).toBeInTheDocument();
});
