import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { vi } from "vitest";

type MockReply = unknown | { status: number; body: unknown };

function isStatusReply(
  reply: unknown,
): reply is { status: number; body: unknown } {
  return (
    typeof reply === "object" &&
    reply !== null &&
    "status" in reply &&
    "body" in reply &&
    typeof (reply as { status: unknown }).status === "number" &&
    Object.keys(reply).length === 2
  );
}

/** Route `fetch` calls by "METHOD /path" to JSON replies; records request bodies. */
export function mockFetch(routes: Record<string, MockReply>) {
  const bodies: Record<string, unknown[]> = {};
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const raw =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    const url = new URL(raw, "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const withQuery = `${method} ${url.pathname}${url.search}`;
    const key = withQuery in routes ? withQuery : `${method} ${url.pathname}`;
    if (typeof init?.body === "string")
      (bodies[key] ??= []).push(JSON.parse(init.body));
    if (!(key in routes)) {
      const error = {
        error: {
          code: "not_found",
          message: `no mock for ${key}`,
          details: {},
        },
      };
      return new Response(JSON.stringify(error), { status: 404 });
    }
    const reply = routes[key];
    const [status, body] = isStatusReply(reply)
      ? [reply.status, reply.body]
      : [200, reply];
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return {
    fn,
    body: (key: string) => bodies[key]?.at(-1) as Record<string, unknown>,
  };
}

export function renderWithQuery(
  ui: ReactElement,
  { route = "/", path }: { route?: string; path?: string } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        {path ? (
          <Routes>
            <Route path={path} element={ui} />
          </Routes>
        ) : (
          ui
        )}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}
