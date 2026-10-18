import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SETTINGS } from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";
import { SalesTeamForm } from "./SalesTeamForm";
import { SimulationForm } from "./SimulationForm";

it("adds a sales rep", async () => {
  const calls = mockFetch({
    "GET /api/sales-reps": [],
    "POST /api/sales-reps": {
      id: "r1",
      name: "Dana",
      email: "dana@seller.test",
      booking_url: null,
      active: true,
    },
  });
  renderWithQuery(<SalesTeamForm />);
  expect(await screen.findByText("No sales reps yet")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Name"), "Dana");
  await userEvent.type(screen.getByLabelText("Email"), "dana@seller.test");
  await userEvent.type(
    screen.getByLabelText("Booking link"),
    "https://cal.test/dana",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add rep" }));
  await waitFor(() =>
    expect(calls.body("POST /api/sales-reps")).toEqual({
      name: "Dana",
      email: "dana@seller.test",
      booking_url: "https://cal.test/dana",
      active: true,
    }),
  );
});

it("saves simulation profile", async () => {
  const withSim = {
    ...SETTINGS,
    simulation: { profile: "realistic", reply_delay_seconds: [5, 30], seed: 7 },
  };
  const calls = mockFetch({
    "GET /api/workspace/settings": withSim,
    "PUT /api/workspace/settings": withSim,
  });
  renderWithQuery(<SimulationForm />);
  await userEvent.click(await screen.findByLabelText(/Accelerated/));
  await userEvent.click(
    screen.getByRole("button", { name: "Save simulation" }),
  );
  await waitFor(() =>
    expect(calls.body("PUT /api/workspace/settings")).toMatchObject({
      goals: SETTINGS.goals,
      simulation: { profile: "accelerated" },
    }),
  );
});
