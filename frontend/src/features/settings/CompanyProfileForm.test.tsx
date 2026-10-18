import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithQuery } from "../../test/utils";
import { CompanyProfileForm } from "./CompanyProfileForm";

const WS = {
  id: "w",
  name: "My company",
  website: null,
  description: null,
  value_props: [],
  offering_type: "sales_call",
};

it("shows empty profile form", async () => {
  mockFetch({ "GET /api/workspace": WS });
  renderWithQuery(<CompanyProfileForm />);
  expect(await screen.findByLabelText("Company name")).toHaveValue(
    "My company",
  );
  expect(screen.getByLabelText("What you sell")).toHaveValue("");
});

it("saves proof points one per line", async () => {
  const calls = mockFetch({
    "GET /api/workspace": WS,
    "PUT /api/workspace": WS,
  });
  renderWithQuery(<CompanyProfileForm />);
  await userEvent.type(
    await screen.findByLabelText("Proof points"),
    "Fast payback{enter}Made in USA",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved")).toBeInTheDocument();
  expect(calls.body("PUT /api/workspace").value_props).toEqual([
    "Fast payback",
    "Made in USA",
  ]);
});
