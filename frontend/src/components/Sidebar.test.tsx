import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";

it("shows the seven sections in order", () => {
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
  expect(screen.getAllByRole("link").map((a) => a.textContent)).toEqual([
    "Overview",
    "ICP Studio",
    "Prospects",
    "Campaigns",
    "Inbox",
    "Agent Workflow",
    "Settings",
  ]);
});

it("marks the current section active", () => {
  render(
    <MemoryRouter initialEntries={["/icp"]}>
      <Sidebar />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "ICP Studio" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
