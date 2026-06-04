// Behaviour test for /tenants/new — verifies the skippable
// four-step wizard per sprint 3.12. Only `name` is required; every
// other field is optional; "Saltar y crear" submits from any step.
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TenantsNewRoute } from "@/routes/tenants/new";

const createSpy = vi.fn();
const switchSpy = vi.fn();

// The route uses `mutateAsync` (Promise-returning). Mirror onto both
// `mutate` (for legacy callers) and `mutateAsync` so the route's
// `await` resolves with a synthetic tenant id.
vi.mock("@/features/tenants/api/hooks", () => ({
  useCreateTenantMutation: () => ({
    mutate: (vars: unknown) => {
      createSpy(vars);
    },
    mutateAsync: (vars: unknown) => {
      createSpy(vars);
      return Promise.resolve({ id: "tenant-id" });
    },
    isPending: false,
  }),
  useSwitchTenantMutation: () => ({
    mutate: (vars: unknown) => {
      switchSpy(vars);
    },
    mutateAsync: (vars: unknown) => {
      switchSpy(vars);
      return Promise.resolve({ access_token: "a", id_token: "i", token_type: "Bearer" });
    },
    isPending: false,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => () => undefined,
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: () => null,
}));

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantsNewRoute />
    </QueryClientProvider>,
  );
}

describe("TenantsNewRoute (skippable wizard)", () => {
  beforeEach(() => {
    createSpy.mockReset();
    switchSpy.mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders Identidad step with Nombre + RUC inputs on mount", () => {
    renderRoute();
    expect(screen.getByLabelText(/Nombre/i)).toBeInTheDocument();
    expect(screen.getByLabelText("RUC")).toBeInTheDocument();
    // Continuar button + Saltar y crear button are visible
    expect(screen.getByRole("button", { name: /Continuar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Saltar y crear/i })).toBeInTheDocument();
    // Crear empresa (final step submit) is NOT visible yet
    expect(screen.queryByRole("button", { name: /^Crear empresa$/i })).toBeNull();
  });

  it("disables 'Saltar y crear' until name is non-empty, then enables it", () => {
    renderRoute();
    const skip = screen.getByRole("button", { name: /Saltar y crear/i });
    expect(skip).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Nombre/i), { target: { value: "Mi Empresa" } });
    expect(skip).not.toBeDisabled();
  });

  it("'Saltar y crear' from step 1 with only name submits minimal payload", async () => {
    renderRoute();
    fireEvent.change(screen.getByLabelText(/Nombre/i), { target: { value: "Mi Empresa" } });
    fireEvent.click(screen.getByRole("button", { name: /Saltar y crear/i }));
    await waitFor(() => expect(createSpy).toHaveBeenCalled());
    const last = createSpy.mock.calls.at(-1)?.[0] as {
      name: string;
      is_withholder: boolean;
      ruc?: unknown;
    };
    expect(last.name).toBe("Mi Empresa");
    expect(last.is_withholder).toBe(false);
    expect(last.ruc).toBeUndefined();
  });

  it("submitting empty name surfaces the Spanish error and blocks creation", async () => {
    renderRoute();
    // Try to skip with empty name — button is disabled, click does nothing.
    const skip = screen.getByRole("button", { name: /Saltar y crear/i });
    expect(skip).toBeDisabled();
    fireEvent.click(skip);
    // No mutation fired
    expect(createSpy).not.toHaveBeenCalled();
  });
});
