import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IcpStudio } from "../../pages/IcpStudio";
import { EXAMPLE_ICP_WITH_INFERRED_SIZE, PARSED, VAGUE_ICP, VERSION } from "../../test/fixtures";
import { mockFetch, renderWithQuery } from "../../test/utils";

async function interpret(text: string) {
  await userEvent.type(screen.getByLabelText("Describe your ideal customers"), text);
  await userEvent.click(screen.getByRole("button", { name: "Interpret" }));
}

it("interprets a prompt and highlights inferred fields", async () => {
  mockFetch({
    "GET /api/icps": [],
    "POST /api/icp/parse": { draft: EXAMPLE_ICP_WITH_INFERRED_SIZE, run_id: "r1", working_memory: [] },
  });
  renderWithQuery(<IcpStudio />);
  await interpret("US manufacturers");
  expect(await screen.findAllByText("Inferred")).not.toHaveLength(0);
});

it("editing a field marks it as stated and saves", async () => {
  const calls = mockFetch({
    "GET /api/icps": [],
    "POST /api/icp/parse": PARSED,
    "POST /api/icps": { ...VERSION, version: 1 },
  });
  renderWithQuery(<IcpStudio />);
  await interpret("US manufacturers");
  const max = await screen.findByLabelText("Employees max");
  await userEvent.clear(max);
  await userEvent.type(max, "50");
  await userEvent.click(screen.getByRole("button", { name: "Save version" }));
  expect(await screen.findByText("Saved as v1")).toBeInTheDocument();
  const structured = calls.body("POST /api/icps").structured as { employee_range: unknown };
  expect(structured.employee_range).toEqual({ value: { min: 5, max: 50 }, origin: "stated" });
});

it("renders empty sections as editable", async () => {
  mockFetch({ "GET /api/icps": [], "POST /api/icp/parse": { draft: VAGUE_ICP, run_id: "r", working_memory: [] } });
  renderWithQuery(<IcpStudio />);
  await interpret("find some companies");
  expect((await screen.findAllByText("None yet")).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: "Add" }).length).toBeGreaterThan(0);
});

it("shows model-unavailable error", async () => {
  mockFetch({
    "GET /api/icps": [],
    "POST /api/icp/parse": {
      status: 502,
      body: {
        error: {
          code: "model_unavailable",
          message: "The AI models are unavailable right now. Please try again.",
          details: {},
        },
      },
    },
  });
  renderWithQuery(<IcpStudio />);
  await interpret("x");
  expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
