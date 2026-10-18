import { afterEach, expect, it, vi } from "vitest";
import { apiFetch } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("throws ApiError with the server's code", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "model_unavailable", message: "down", details: {} },
        }),
        {
          status: 502,
        },
      ),
    ),
  );
  await expect(
    apiFetch("/icp/parse", { method: "POST" }),
  ).rejects.toMatchObject({
    code: "model_unavailable",
    status: 502,
  });
});
