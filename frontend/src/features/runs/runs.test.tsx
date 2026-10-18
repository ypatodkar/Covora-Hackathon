import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentWorkflow } from "../../pages/AgentWorkflow";
import { RunDetail } from "../../pages/RunDetail";
import { FAILED_RUN_DETAIL, RUN_DETAIL } from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";

it("shows empty runs state", async () => {
  mockFetch({ "GET /api/runs": [] });
  renderWithQuery(<AgentWorkflow />, { route: "/workflow" });
  expect(await screen.findByText("No agent runs yet")).toBeInTheDocument();
});

it("nests spans and shows the routing decision", async () => {
  mockFetch({
    "GET /api/runs/r1": RUN_DETAIL,
    "GET /api/runs/r1/spans/s-agent/memory": [],
  });
  renderWithQuery(<RunDetail />, {
    route: "/workflow/runs/r1",
    path: "/workflow/runs/:runId",
  });
  await userEvent.click(await screen.findByText("llm:icp_parsing"));
  expect(screen.getByText("fixed: icp_parsing → super")).toBeInTheDocument();
  expect(
    screen.getByText("nvidia/nemotron-3-super-120b-a12b"),
  ).toBeInTheDocument();
});

it("shows working memory for an agent step", async () => {
  mockFetch({
    "GET /api/runs/r1": RUN_DETAIL,
    "GET /api/runs/r1/spans/s-agent/memory": [
      {
        memory_item_id: "m1",
        kind: "episodic",
        subtype: "icp_edit",
        source: "research",
        summary: "User changed employee_range 5–25 → 10–50",
        evidence_level: null,
        reason: "past ICP corrections by the user",
        rank: 1,
      },
    ],
  });
  renderWithQuery(<RunDetail />, {
    route: "/workflow/runs/r1",
    path: "/workflow/runs/:runId",
  });
  await userEvent.click(await screen.findByText("icp:icp_parsing"));
  expect(await screen.findByText(/10–50/)).toBeInTheDocument();
});

it("shows a failed span's error", async () => {
  mockFetch({ "GET /api/runs/r2": FAILED_RUN_DETAIL });
  renderWithQuery(<RunDetail />, {
    route: "/workflow/runs/r2",
    path: "/workflow/runs/:runId",
  });
  expect(await screen.findByText(/503/)).toBeInTheDocument();
});
