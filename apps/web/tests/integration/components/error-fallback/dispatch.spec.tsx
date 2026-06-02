// Integration tests for the route-error dispatch helper in section 5
// of harden-tenant-isolation-and-errors. The dispatch helper picks the
// right fallback card per error category — these tests exercise each
// category, plus the no-fetch invariant and the auth-aware recovery
// link routing.

import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ZodError } from "zod";

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: vi.fn().mockReturnValue("access-token"),
}));

import { getAccessToken } from "@/api/tokenStore";
import { dispatchRouteError } from "@/components/error-fallback/dispatch";
import { RouteNotFoundCard } from "@/components/error-fallback/route-not-found-card";
import { server } from "@/../tests/integration/msw/server";
import { renderWithProviders } from "@/../tests/integration/_support/renderRoute";
import { http } from "@/../tests/integration/msw/handlers";
import { Outlet, RouterProvider, createMemoryHistory, createRouter, createRoute, createRootRoute } from "@tanstack/react-router";

// Reusable ApiError stub — the real classes (declared per-slice) are
// recognised by name + numeric status, so this duck-typed stand-in is
// sufficient for the dispatch tests.
class FakeApiError extends Error {
  public readonly status: number;
  constructor(status: number) {
    super(`fake ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

describe("dispatchRouteError", () => {
  it("renders RouteForbiddenCard for ApiError(403)", () => {
    renderWithProviders(<>{dispatchRouteError(new FakeApiError(403))}</>);
    expect(screen.getByRole("alert")).toHaveTextContent(/no tienes permiso/i);
  });

  it("renders RouteNotFoundCard for ApiError(404)", () => {
    renderWithProviders(<>{dispatchRouteError(new FakeApiError(404))}</>);
    expect(screen.getByRole("alert")).toHaveTextContent(/no encontramos esa página/i);
  });

  it("renders RouteSchemaErrorCard for a ZodError", () => {
    const zodError = new ZodError([
      { code: "invalid_type", path: ["x"], message: "Expected string", expected: "string", received: "number" } as never,
    ]);
    renderWithProviders(<>{dispatchRouteError(zodError)}</>);
    expect(screen.getByRole("alert")).toHaveTextContent(/respuesta inesperada del servidor/i);
  });

  it("renders RouteRuntimeErrorCard for a plain Error", () => {
    renderWithProviders(<>{dispatchRouteError(new Error("boom"))}</>);
    expect(screen.getByRole("alert")).toHaveTextContent(/ocurrió un error inesperado/i);
  });

  it("does not issue a /v1/me fetch when a fallback renders", async () => {
    let meHits = 0;
    server.use(
      http.get("/v1/me", ({ response }) => {
        meHits += 1;
        return response(200).json({
          id: "u-1",
          email: "ada@nica.test",
          display_name: "Ada",
          locale: "es-NI",
          timezone: "America/Managua",
          preferences: {},
          active_tenant: null,
          role: null,
          permissions: [],
        });
      }),
    );
    renderWithProviders(<>{dispatchRouteError(new FakeApiError(403))}</>);
    // Give MSW a beat — if a fetch was queued it would land within a tick.
    await new Promise((r) => setTimeout(r, 30));
    expect(meHits).toBe(0);
  });
});

describe("RecoveryLink routing", () => {
  it("routes to /login when there is no access token", () => {
    vi.mocked(getAccessToken).mockReturnValueOnce(null);
    renderWithProviders(<RouteNotFoundCard />);
    const alert = screen.getByRole("alert");
    const link = within(alert).getByRole("link");
    expect(link).toHaveAttribute("href", "/login");
  });

  it("routes to /dashboard when an access token is present", () => {
    vi.mocked(getAccessToken).mockReturnValueOnce("access-token");
    renderWithProviders(<RouteNotFoundCard />);
    const alert = screen.getByRole("alert");
    const link = within(alert).getByRole("link");
    expect(link).toHaveAttribute("href", "/dashboard");
  });
});

// Smoke test for the notFoundComponent contract: when the router
// resolves a non-existent URL it must render RouteNotFoundCard inside
// the bare-shell wrapper. Verified here against an isolated router
// instance so we don't have to mount the full app tree.
describe("notFound routing", () => {
  it("renders RouteNotFoundCard for an unknown URL", async () => {
    const root = createRootRoute({
      component: () => <Outlet />,
      notFoundComponent: () => <RouteNotFoundCard />,
    });
    const known = createRoute({
      getParentRoute: () => root,
      path: "/known",
      component: () => <div>known</div>,
    });
    const tree = root.addChildren([known]);
    const router = createRouter({
      routeTree: tree,
      history: createMemoryHistory({ initialEntries: ["/missing"] }),
    });
    renderWithProviders(<RouterProvider router={router} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.getByRole("alert")).toHaveTextContent(/no encontramos esa página/i);
  });
});
