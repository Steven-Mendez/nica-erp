// Smoke test for AppSidebar — verifies the workspace nav set, the
// removal of the legacy Tenants entry, the Empresa parent with sub-menu,
// active-state propagation, and section persistence key.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppSidebar } from "@/components/app-sidebar/app-sidebar";
import {
  SidebarProvider,
  sidebarSectionStorageKey,
} from "@/components/app-sidebar/sidebar-context";

let mockPathname = "/dashboard";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: mockPathname }),
    useNavigate: () => () => undefined,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({
    data: {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      preferences: {},
      active_tenant: "00000000-0000-0000-0000-0000000000aa",
      role: "owner",
      permissions: ["members:read", "tenant:write"],
    },
    isLoading: false,
    isError: false,
  }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

// AppSidebar's EmpresaSection gates "Usuarios" / "Configuración" sub-
// menu entries via `useHasPermission`. That hook uses `useQuery({
// queryKey: meQueryKey })`; seed the cache with the same permissions
// the useMeQuery mock returns so the gates pass in this test.
vi.mock("@/api/useHasPermission", () => ({
  useHasPermission: (code: string) => ["members:read", "tenant:write"].includes(code),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({
    data: {
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Acme",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

function renderSidebar(pathname: string) {
  mockPathname = pathname;
  // AppSidebar's EmpresaSection uses useHasPermission → useQuery; wrap
  // with a fresh QueryClientProvider so the hook doesn't throw.
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("AppSidebar", () => {
  it("renders the five flat entries plus the Empresa parent (no Tenants)", () => {
    renderSidebar("/dashboard");
    for (const label of ["Resumen", "Ventas", "Inventario", "Reportes", "Configuración"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // Empresa replaces the legacy Tenants entry.
    expect(screen.getByText("Empresa")).toBeInTheDocument();
    expect(screen.queryByText("Tenants")).toBeNull();
    expect(screen.queryByText("Empresas")).toBeNull();
  });

  it("Empresa parent toggle flips localStorage", () => {
    const storageKey = sidebarSectionStorageKey("empresa");
    renderSidebar("/dashboard");
    // Initial state writes 0 (parent not active for /dashboard).
    expect(window.localStorage.getItem(storageKey)).toBe("0");
    fireEvent.click(screen.getByText("Empresa"));
    expect(window.localStorage.getItem(storageKey)).toBe("1");
  });

  it("on /empresa/users both the parent and the child show as active", () => {
    renderSidebar("/empresa/users");
    const parentBtn = screen.getByTitle("Empresa");
    expect(parentBtn.getAttribute("data-active")).toBe("true");
    // The sub-menu auto-expands when the section default is active.
    // SidebarMenuSubButton wraps the label in a span and carries
    // data-active on its outer span.
    const usuariosLabel = screen.getByText("Usuarios");
    expect(usuariosLabel.parentElement?.getAttribute("data-active")).toBe("true");
  });
});
