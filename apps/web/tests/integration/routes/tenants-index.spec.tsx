// Behaviour test for /tenants — the empresa picker forced on every
// fresh session by the route guard.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TenantsIndexRoute } from "@/routes/tenants/index";
import { PICKER_FLAG_KEY } from "@/lib/route-guard";

const switchSpy = vi.fn();
const navigateSpy = vi.fn();
let memberships: Array<{
  tenant_id: string;
  name: string;
  role: string;
  status: string;
  joined_at: string;
}> = [];

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({
    data: { items: memberships },
    isLoading: false,
    isError: false,
  }),
  useInvitationsQuery: () => ({ data: undefined, isLoading: true }),
  useSwitchTenantMutation: () => ({
    mutate: (
      vars: { tenantId: string },
      opts?: { onSuccess?: () => void; onError?: (e: Error) => void },
    ) => {
      switchSpy(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => navigateSpy,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: () => null,
}));

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantsIndexRoute />
    </QueryClientProvider>,
  );
}

const baseMembership = (over: { tenant_id: string; name: string; role?: string }) => ({
  status: "active",
  joined_at: "2026-01-01T00:00:00Z",
  role: "owner",
  ...over,
});

describe("TenantsIndexRoute (picker)", () => {
  beforeEach(() => {
    switchSpy.mockReset();
    navigateSpy.mockReset();
    memberships = [];
  });
  afterEach(() => {
    cleanup();
  });

  it("renders the title, search input, and 'Nueva empresa' button", () => {
    memberships = [baseMembership({ tenant_id: "t-1", name: "Acme S.A." })];
    renderRoute();
    expect(screen.getByRole("heading", { name: "Tus empresas" })).toBeInTheDocument();
    expect(screen.getByLabelText("Buscar una empresa")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Nueva empresa/i })).toBeInTheDocument();
  });

  it("filters cards by the search query", () => {
    memberships = [
      baseMembership({ tenant_id: "t-1", name: "Acme S.A." }),
      baseMembership({ tenant_id: "t-2", name: "Acme Logistics" }),
      baseMembership({ tenant_id: "t-3", name: "Beta Corp" }),
    ];
    renderRoute();
    // All three render initially.
    expect(screen.getByRole("button", { name: /Seleccionar Acme S\.A\./ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Seleccionar Acme Logistics/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Seleccionar Beta Corp/ })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Buscar una empresa"), { target: { value: "acme" } });

    expect(screen.getByRole("button", { name: /Seleccionar Acme S\.A\./ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Seleccionar Acme Logistics/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Seleccionar Beta Corp/ })).toBeNull();
  });

  it("activating a card calls switch, sets the picker flag, and navigates to /dashboard", async () => {
    memberships = [baseMembership({ tenant_id: "t-1", name: "Acme S.A." })];
    renderRoute();
    fireEvent.click(screen.getByRole("button", { name: /Seleccionar Acme S\.A\./ }));
    await waitFor(() => expect(switchSpy).toHaveBeenCalled());
    expect(switchSpy.mock.calls.at(-1)?.[0]).toEqual({
      tenantId: "t-1",
      input: {},
    });
    expect(window.sessionStorage.getItem(PICKER_FLAG_KEY)).toBe("1");
    expect(navigateSpy).toHaveBeenCalledWith({ to: "/dashboard" });
  });

  it("renders the empty-state Alert when memberships is empty", () => {
    memberships = [];
    renderRoute();
    expect(screen.getByText(/Aún no tienes empresas/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Crear empresa/i })).toBeInTheDocument();
  });
});
