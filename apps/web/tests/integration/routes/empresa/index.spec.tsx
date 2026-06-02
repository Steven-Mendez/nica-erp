// Smoke test for /empresa — Vista general. Covers the populated
// path (no banner, four sections) and the soft-creation path
// (Pendiente badges + soft-creation banner).
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EmpresaIndexRoute } from "@/routes/empresa/index";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

let tenantPayload:
  | {
      id: string;
      name: string;
      ruc: string | null;
      regime: "general" | "cuota_fija" | "pequeno_contribuyente" | null;
      municipality: string | null;
      authorization_dgi: { number: string; valid_from: string; valid_to: string } | null;
      fiscal_address: string | null;
      is_withholder: boolean;
      status: string;
      created_at: string;
      updated_at: string;
    }
  | undefined;

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({
    data: {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      preferences: {},
      active_tenant: tenantId,
      role: "owner",
      permissions: [],
    },
    isLoading: false,
  }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({ data: { items: [] }, isLoading: false }),
  useTenantQuery: () => ({ data: tenantPayload, isLoading: tenantPayload === undefined }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/empresa" }),
    useNavigate: () => () => undefined,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <EmpresaIndexRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  tenantPayload = undefined;
});

describe("EmpresaIndexRoute", () => {
  beforeEach(() => {
    tenantPayload = undefined;
  });

  it("renders the four sections and no soft-creation banner when fully populated", () => {
    tenantPayload = {
      id: tenantId,
      name: "Acme S.A.",
      ruc: "1234567890123A",
      regime: "general",
      municipality: "Managua",
      authorization_dgi: {
        number: "DGI-001",
        valid_from: "2026-01-01",
        valid_to: "2026-12-31",
      },
      fiscal_address: "Avenida Principal 123",
      is_withholder: true,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    renderRoute();
    expect(screen.getByRole("heading", { name: "Acme S.A." })).toBeInTheDocument();
    expect(screen.getByText("Identidad")).toBeInTheDocument();
    expect(screen.getByText("Régimen fiscal")).toBeInTheDocument();
    expect(screen.getByText("Autorización DGI")).toBeInTheDocument();
    expect(screen.getByText("Dirección")).toBeInTheDocument();
    expect(screen.getByText("1234567890123A")).toBeInTheDocument();
    expect(screen.getByText("Avenida Principal 123")).toBeInTheDocument();
    expect(screen.queryByText(/Completa los datos fiscales/)).toBeNull();
  });

  it("renders Pendiente badges and the soft-creation banner when fiscal fields are null", () => {
    tenantPayload = {
      id: tenantId,
      name: "Beta S.A.",
      ruc: null,
      regime: null,
      municipality: null,
      authorization_dgi: null,
      fiscal_address: null,
      is_withholder: false,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    renderRoute();
    expect(screen.getByText(/Completa los datos fiscales/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Completar ahora/i })).toHaveAttribute(
      "href",
      "/empresa/settings",
    );
    // At least one Pendiente badge (RUC, régimen, municipio, DGI, dirección).
    expect(screen.getAllByText("Pendiente").length).toBeGreaterThanOrEqual(3);
  });
});
