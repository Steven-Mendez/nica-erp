// Smoke test for /account — wrapped in IdentityLayout (no sidebar)
// per sprint 3.14. Asserts the three identity cards render, the
// dashboard chrome is gone, and `← Volver` reads the sessionStorage
// last-app-route.
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountRoute } from "@/routes/account";

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: () => "access-token",
  getRefreshToken: () => "refresh-token",
}));

const tenantId = "00000000-0000-0000-0000-0000000000aa";
const me = {
  id: "u-1",
  email: "ada@nica.test",
  display_name: "Ada Lovelace",
  locale: "es-NI",
  timezone: "America/Managua",
  preferences: {},
  active_tenant: tenantId,
  role: "owner",
  permissions: ["members:invite", "tenant:read", "sales:create"],
};

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({ data: me, isLoading: false, isError: false }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({
    data: {
      items: [
        {
          tenant_id: tenantId,
          name: "Acme S.A.",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    },
    isLoading: false,
  }),
  useTenantQuery: () => ({ data: undefined, isLoading: false }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

const navigateSpy = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/account" }),
    useNavigate: () => navigateSpy,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AccountRoute />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  navigateSpy.mockReset();
});

afterEach(() => {
  // sessionStorage is cleared by tests/setup.ts beforeEach.
});

describe("AccountRoute (IdentityLayout)", () => {
  it("renders the three identity cards", () => {
    renderRoute();
    expect(screen.getByText("Perfil")).toBeInTheDocument();
    // The TenantSwitcher in IdentityLayout also renders an sr-only
    // "Empresa activa" label, so match on the card title via getAllByText.
    expect(screen.getAllByText("Empresa activa").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Permisos")).toBeInTheDocument();
    expect(screen.getByText(me.id)).toBeInTheDocument();
    expect(screen.getByText("Acme S.A.")).toBeInTheDocument();
    for (const perm of me.permissions) {
      expect(screen.getByText(perm)).toBeInTheDocument();
    }
  });

  it("renders no sidebar root (AppShell has been replaced by IdentityLayout)", () => {
    renderRoute();
    // The AppSidebar root has data-sidebar="root"; IdentityLayout does not.
    expect(document.querySelector('[data-sidebar="root"]')).toBeNull();
  });

  it("clicking ← Volver reads sessionStorage and navigates to /dashboard when unset", () => {
    renderRoute();
    const back = screen.getByTestId("identity-back-link");
    back.click();
    expect(navigateSpy).toHaveBeenCalledWith({ to: "/dashboard" });
  });

  it("clicking ← Volver navigates to the stored last-app-route", () => {
    window.sessionStorage.setItem("nica-erp:last-app-route", "/sales");
    renderRoute();
    const back = screen.getByTestId("identity-back-link");
    back.click();
    expect(navigateSpy).toHaveBeenCalledWith({ to: "/sales" });
  });
});
