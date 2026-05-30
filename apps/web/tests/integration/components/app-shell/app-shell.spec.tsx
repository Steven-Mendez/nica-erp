// Smoke test for AppShell — verifies sidebar + header are present and
// `children` mount in the main column.
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/dashboard" }),
    useNavigate: () => () => undefined,
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({ data: undefined, isLoading: false }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: () => ({ data: { items: [] }, isLoading: false }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

afterEach(() => {
  window.localStorage.clear();
});

describe("AppShell", () => {
  it("renders the sidebar, the site header, and the children", () => {
    render(
      <AppShell>
        <div data-testid="shell-children">contenido</div>
      </AppShell>,
    );

    // Sidebar is present (the workspace nav group label is in the sidebar).
    expect(screen.getByText("Espacio de trabajo")).toBeInTheDocument();
    // Header is present — the breadcrumb / theme toggle live there.
    expect(screen.getByRole("button", { name: /Cambiar tema/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Ruta de navegación/i)).toBeInTheDocument();
    // Children mount.
    expect(screen.getByTestId("shell-children")).toHaveTextContent("contenido");
  });
});
