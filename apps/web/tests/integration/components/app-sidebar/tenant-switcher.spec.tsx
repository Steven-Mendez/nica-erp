// apps/web/tests/integration/components/app-sidebar/tenant-switcher.spec.tsx
//
// Direct coverage for TenantSwitcher: the broader AppSidebar spec only
// exercises the single-tenant happy path. This spec adds loading / error /
// empty branches, asserts the multi-tenant <select> renders both options
// with role suffix, and verifies handleChange dispatches the switch
// mutation (the refresh token rides in the httpOnly nica_erp_rt cookie,
// not as a body field) + invalidates the router on success.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { TenantSwitcher } from "@/components/app-sidebar/tenant-switcher";
import { SidebarProvider } from "@/components/app-sidebar/sidebar-context";

const { useMyTenantsQueryMock, useMeQueryMock, useSwitchTenantMutationMock, routerInvalidateMock } =
  vi.hoisted(() => ({
    useMyTenantsQueryMock: vi.fn(),
    useMeQueryMock: vi.fn(),
    useSwitchTenantMutationMock: vi.fn(),
    routerInvalidateMock: vi.fn(),
  }));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: useMyTenantsQueryMock,
  useSwitchTenantMutation: useSwitchTenantMutationMock,
}));

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: useMeQueryMock,
}));

vi.mock("@/router", () => ({
  router: { invalidate: routerInvalidateMock },
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    Link: ({
      children,
      to,
      ...props
    }: {
      children: React.ReactNode;
      to: string;
      [k: string]: unknown;
    }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  };
});

const TENANT_A = "00000000-0000-0000-0000-0000000000aa";
const TENANT_B = "00000000-0000-0000-0000-0000000000bb";

const tenantsResult = (
  items: Array<{ tenant_id: string; name: string; role: string }>,
  overrides: Partial<{
    isLoading: boolean;
    isError: boolean;
    data: unknown;
  }> = {},
) => ({
  data: { items },
  isLoading: false,
  isError: false,
  ...overrides,
});

const meResult = (activeTenant: string | null) => ({
  data: {
    id: "u-1",
    email: "ada@nica.test",
    display_name: "Ada",
    preferences: {},
    active_tenant: activeTenant,
    role: "owner",
    permissions: [],
  },
  isLoading: false,
  isError: false,
});

const switchMutationResult = (mutate: Mock, isPending = false) => ({
  mutate,
  isPending,
});

const renderSwitcher = () =>
  render(
    <SidebarProvider>
      <TenantSwitcher />
    </SidebarProvider>,
  );

beforeEach(() => {
  useMyTenantsQueryMock.mockReset();
  useMeQueryMock.mockReset();
  useSwitchTenantMutationMock.mockReset();
  routerInvalidateMock.mockReset();
  routerInvalidateMock.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

describe("TenantSwitcher", () => {
  it("renders a Skeleton while tenants are loading", () => {
    useMyTenantsQueryMock.mockReturnValue(tenantsResult([], { isLoading: true, data: undefined }));
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(vi.fn()));

    const { container } = renderSwitcher();
    // Skeleton is the only thing rendered; no menu trigger.
    expect(container.querySelector('[data-slot="skeleton"]')).not.toBeNull();
    expect(screen.queryByRole("button", { name: /Empresa/i })).toBeNull();
  });

  it("renders nothing when the tenants query errors", () => {
    useMyTenantsQueryMock.mockReturnValue(tenantsResult([], { isError: true, data: undefined }));
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(vi.fn()));

    const { container } = renderSwitcher();
    // No menu trigger when the tenants query errors.
    expect(container.querySelector('[role="button"]')).toBeNull();
  });

  it("renders the empty-state link to /tenants/new when items is empty", () => {
    useMyTenantsQueryMock.mockReturnValue(tenantsResult([]));
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(vi.fn()));

    renderSwitcher();
    const link = screen.getByTitle("Sin empresa activa");
    expect(link).toHaveAttribute("href", "/tenants/new");
    expect(screen.getByText("Sin empresa activa")).toBeInTheDocument();
  });

  it("renders the active tenant name + role in the trigger", () => {
    // The dropdown trigger surfaces the active tenant's name and role
    // line so the operator sees which empresa they're currently in.
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(vi.fn()));

    renderSwitcher();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    // The trigger renders the localised Spanish role label, not the
    // raw English role code (audit F-033).
    expect(screen.getByText("Propietario")).toBeInTheDocument();
  });

  it("dispatches switchMut.mutate with an empty body and calls router.invalidate on success", () => {
    // The refresh token rides exclusively in the httpOnly `nica_erp_rt`
    // cookie set by the API; the SPA passes an empty body and relies on
    // `credentials: "include"` on the openapi-fetch client.
    const mutate = vi.fn();
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(mutate));

    renderSwitcher();
    // Radix DropdownMenu opens on pointerDown; jsdom's `fireEvent.click`
    // alone doesn't trigger that, so we dispatch both events.
    const trigger = screen.getByRole("button", { name: /Acme/i });
    fireEvent.pointerDown(trigger, { button: 0 });
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("menuitem", { name: /Beta/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    const call = mutate.mock.calls[0];
    if (call === undefined) throw new Error("mutate was not called");
    const [vars, options] = call as [
      { tenantId: string; input: Record<string, never> },
      { onSuccess?: () => void },
    ];
    expect(vars).toEqual({
      tenantId: TENANT_B,
      input: {},
    });
    // Simulate the mutation succeeding — router.invalidate must fire.
    options.onSuccess?.();
    expect(routerInvalidateMock).toHaveBeenCalledTimes(1);
  });

  it("is a no-op when the user re-selects the already-active tenant", () => {
    const mutate = vi.fn();
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(switchMutationResult(mutate));

    renderSwitcher();
    const trigger = screen.getByRole("button", { name: /Acme/i });
    fireEvent.pointerDown(trigger, { button: 0 });
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("menuitem", { name: /Acme/i }));

    expect(mutate).not.toHaveBeenCalled();
  });
});
