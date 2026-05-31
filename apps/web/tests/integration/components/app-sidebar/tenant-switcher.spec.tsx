// apps/web/tests/integration/components/app-sidebar/tenant-switcher.spec.tsx
//
// Direct coverage for TenantSwitcher: the broader AppSidebar spec only
// exercises the single-tenant happy path. This spec adds loading / error /
// empty branches, asserts the multi-tenant <select> renders both options
// with role suffix, and verifies handleChange dispatches the switch
// mutation with the cached refresh token + invalidates the router on
// success.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";
import { TenantSwitcher } from "@/components/app-sidebar/tenant-switcher";
import { SidebarProvider } from "@/components/app-sidebar/sidebar-context";

const {
  useMyTenantsQueryMock,
  useMeQueryMock,
  useSwitchTenantMutationMock,
  getRefreshTokenMock,
  routerInvalidateMock,
} = vi.hoisted(() => ({
  useMyTenantsQueryMock: vi.fn(),
  useMeQueryMock: vi.fn(),
  useSwitchTenantMutationMock: vi.fn(),
  getRefreshTokenMock: vi.fn(),
  routerInvalidateMock: vi.fn(),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useMyTenantsQuery: useMyTenantsQueryMock,
  useSwitchTenantMutation: useSwitchTenantMutationMock,
}));

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: useMeQueryMock,
}));

vi.mock("@/api/tokenStore", () => ({
  getRefreshToken: getRefreshTokenMock,
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
  getRefreshTokenMock.mockReset();
  routerInvalidateMock.mockReset();
  routerInvalidateMock.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

describe("TenantSwitcher", () => {
  it("renders a Skeleton while tenants are loading", () => {
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([], { isLoading: true, data: undefined }),
    );
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(vi.fn()),
    );

    const { container } = renderSwitcher();
    // Skeleton is the only thing rendered; the select label is absent.
    expect(screen.queryByLabelText("Empresa activa")).not.toBeInTheDocument();
    expect(container.querySelector('[data-slot="skeleton"]')).not.toBeNull();
  });

  it("renders nothing when the tenants query errors", () => {
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([], { isError: true, data: undefined }),
    );
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(vi.fn()),
    );

    const { container } = renderSwitcher();
    // First child of the SidebarProvider wrapper has no switcher inside.
    expect(screen.queryByLabelText("Empresa activa")).not.toBeInTheDocument();
    expect(container.querySelector("select")).toBeNull();
  });

  it("renders the empty-state link to /tenants/new when items is empty", () => {
    useMyTenantsQueryMock.mockReturnValue(tenantsResult([]));
    useMeQueryMock.mockReturnValue(meResult(null));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(vi.fn()),
    );

    renderSwitcher();
    const link = screen.getByTitle("Sin empresa activa");
    expect(link).toHaveAttribute("href", "/tenants/new");
    expect(screen.getByText("Sin empresa activa")).toBeInTheDocument();
  });

  it("renders one option per tenant with the role suffix and the active one selected", () => {
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(vi.fn()),
    );

    renderSwitcher();
    const select = screen.getByLabelText("Empresa activa") as HTMLSelectElement;
    expect(select.value).toBe(TENANT_A);
    expect(screen.getByRole("option", { name: "Acme · owner" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Beta · accountant" }),
    ).toBeInTheDocument();
    // Role line under the select reflects the active tenant.
    expect(screen.getByText("owner")).toBeInTheDocument();
  });

  it("dispatches switchMut.mutate with refresh token and calls router.invalidate on success", () => {
    const mutate = vi.fn();
    getRefreshTokenMock.mockReturnValue("rt-cached");
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(mutate),
    );

    renderSwitcher();
    fireEvent.change(screen.getByLabelText("Empresa activa"), {
      target: { value: TENANT_B },
    });

    expect(mutate).toHaveBeenCalledTimes(1);
    const call = mutate.mock.calls[0];
    if (call === undefined) throw new Error("mutate was not called");
    const [vars, options] = call as [
      { tenantId: string; input: { refresh_token: string } },
      { onSuccess?: () => void },
    ];
    expect(vars).toEqual({
      tenantId: TENANT_B,
      input: { refresh_token: "rt-cached" },
    });
    // Simulate the mutation succeeding — router.invalidate must fire.
    options.onSuccess?.();
    expect(routerInvalidateMock).toHaveBeenCalledTimes(1);
  });

  it("is a no-op when the user re-selects the already-active tenant", () => {
    const mutate = vi.fn();
    getRefreshTokenMock.mockReturnValue("rt-cached");
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(mutate),
    );

    renderSwitcher();
    fireEvent.change(screen.getByLabelText("Empresa activa"), {
      target: { value: TENANT_A },
    });

    expect(mutate).not.toHaveBeenCalled();
  });

  it("is a no-op when there is no refresh token in store", () => {
    const mutate = vi.fn();
    getRefreshTokenMock.mockReturnValue(null);
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(mutate),
    );

    renderSwitcher();
    fireEvent.change(screen.getByLabelText("Empresa activa"), {
      target: { value: TENANT_B },
    });

    expect(mutate).not.toHaveBeenCalled();
  });

  it("disables the select and shows 'Cambiando...' while the mutation is pending", () => {
    useMyTenantsQueryMock.mockReturnValue(
      tenantsResult([
        { tenant_id: TENANT_A, name: "Acme", role: "owner" },
        { tenant_id: TENANT_B, name: "Beta", role: "accountant" },
      ]),
    );
    useMeQueryMock.mockReturnValue(meResult(TENANT_A));
    useSwitchTenantMutationMock.mockReturnValue(
      switchMutationResult(vi.fn(), true),
    );

    renderSwitcher();
    expect(screen.getByLabelText("Empresa activa")).toBeDisabled();
    expect(screen.getByText("Cambiando...")).toBeInTheDocument();
  });
});
