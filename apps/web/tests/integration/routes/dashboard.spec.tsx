// Smoke test for /dashboard — asserts the four KPI slots, the chart slot,
// and the activity (table) slot all render under the AppShell chrome.
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { DashboardRoute } from "@/routes/dashboard";

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({
    data: {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      locale: "es-NI",
      timezone: "America/Managua",
      preferences: {},
      active_tenant: null,
      role: null,
      permissions: [],
    },
    isLoading: false,
  }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({ data: { items: [] }, isLoading: false }),
  useTenantQuery: () => ({ data: undefined, isLoading: false }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/dashboard" }),
    useNavigate: () => () => undefined,
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DashboardRoute />
    </QueryClientProvider>,
  );
}

describe("DashboardRoute", () => {
  it("renders four KPI cards + chart + activity slots", () => {
    renderRoute();
    expect(screen.getAllByTestId("kpi-card")).toHaveLength(4);
    expect(screen.getByTestId("chart-card")).toBeInTheDocument();
    expect(screen.getByTestId("table-card")).toBeInTheDocument();
  });

  it("renders the section heading", () => {
    renderRoute();
    expect(screen.getByRole("heading", { name: "Resumen" })).toBeInTheDocument();
  });
});
