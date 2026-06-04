// Smoke tests for /empresa/users — permission gating on the row
// actions menu, the owner-row guarantee, the `+ Invitar` button, and
// the pending-invitations tab.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EmpresaUsuariosRoute } from "@/routes/empresa/users";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

let permissions: string[] = [];
let members: Array<{ user_id: string; role: string; display_name?: string; email?: string }> = [];
let invitations: Array<{
  id: string;
  email: string;
  proposed_role: string;
  status: string;
}> = [];

vi.mock("@/api/useHasPermission", () => ({
  useHasPermission: (perm: string) => permissions.includes(perm),
}));

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({
    data: {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      preferences: {},
      active_tenant: tenantId,
      role: "owner",
      permissions,
    },
    isLoading: false,
    isError: false,
  }),
  useLogoutMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  // Sidebar's TenantSwitcher consumes these — stub.
  useMyTenantsQuery: () => ({ data: { items: [] }, isLoading: false, isError: false }),
  useSwitchTenantMutation: () => ({ mutate: () => undefined, isPending: false }),
  // Route-level hooks. The members hook now returns the paginated
  // envelope; the test seeds an `items` array via `members`.
  useMembersQuery: () => ({
    data: { items: members, total: members.length, limit: 25, offset: 0 },
    isLoading: false,
    isError: false,
  }),
  useInvitationsQuery: () => ({ data: invitations, isLoading: false }),
  useInviteMemberMutation: () => ({
    mutate: () => undefined,
    isPending: false,
    error: null,
    reset: () => undefined,
  }),
  useRemoveMemberMutation: () => ({ mutate: () => undefined, isPending: false }),
  useCancelInvitationMutation: () => ({ mutate: () => undefined, isPending: false }),
  useResendInvitationMutation: () => ({
    mutate: () => undefined,
    isPending: false,
    isError: false,
    isSuccess: false,
  }),
  useUpdateMemberRoleMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

// Reactive search-state stand-in. `useSearch` subscribes via
// `useSyncExternalStore` so consumers re-render when `useNavigate`
// updates the value. Tests can pre-seed via `setSearchState(...)` and
// assert what the route wrote with `currentSearch`.
let currentSearch: Record<string, unknown> = {};
const navigateCalls: Array<{ search: unknown; replace: boolean | undefined }> = [];
const searchSubscribers = new Set<() => void>();

function setSearchState(next: Record<string, unknown>): void {
  currentSearch = next;
  for (const fn of searchSubscribers) fn();
}

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  const { useSyncExternalStore } = await import("react");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/empresa/users" }),
    useSearch: () =>
      useSyncExternalStore(
        (cb) => {
          searchSubscribers.add(cb);
          return () => searchSubscribers.delete(cb);
        },
        () => currentSearch,
      ),
    useNavigate: () => (opts: { search?: unknown; replace?: boolean } | undefined) => {
      if (opts === undefined) return undefined;
      navigateCalls.push({ search: opts.search, replace: opts.replace });
      if (typeof opts.search === "function") {
        setSearchState(
          (opts.search as (prev: Record<string, unknown>) => Record<string, unknown>)(
            currentSearch,
          ),
        );
      } else if (opts.search !== undefined) {
        setSearchState(opts.search as Record<string, unknown>);
      }
      return undefined;
    },
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

function renderRoute() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <EmpresaUsuariosRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  permissions = [];
  members = [];
  invitations = [];
  setSearchState({});
  navigateCalls.length = 0;
});

describe("EmpresaUsuariosRoute", () => {
  beforeEach(() => {
    permissions = [];
    members = [];
    invitations = [];
    setSearchState({});
    navigateCalls.length = 0;
  });

  it("with members:update-role true, exposes a row actions menu for non-owner rows", () => {
    permissions = ["members:update-role"];
    // The actions menu's aria-label now reads from display_name (or
    // email as fallback) — never the UUID (audit F-030: no UUIDs
    // surfaced under names).
    members = [
      { user_id: "u-owner", role: "owner", display_name: "Ada Owner" },
      { user_id: "u-2", role: "viewer", display_name: "Bea Viewer" },
    ];
    renderRoute();
    // Row-level actions menu trigger appears for the non-owner row.
    expect(screen.getByLabelText("Acciones de Bea Viewer")).toBeInTheDocument();
    // Owner row never gets the actions menu.
    expect(screen.queryByLabelText("Acciones de Ada Owner")).toBeNull();
  });

  it("without members:update-role and without members:remove, no actions menu is shown", () => {
    permissions = [];
    members = [{ user_id: "u-2", role: "viewer" }];
    renderRoute();
    expect(screen.queryByLabelText("Acciones de u-2")).toBeNull();
    // The role is still surfaced as a badge. The MembersTable renders
    // both a desktop <table> branch and a mobile <Card> branch
    // (CSS-toggled by viewport) so each Spanish role label appears
    // twice in the DOM under jsdom (where no media query applies).
    expect(screen.getAllByText("Visualizador").length).toBeGreaterThanOrEqual(1);
  });

  it("owner row renders the role badge but never the actions menu", () => {
    permissions = ["members:update-role", "members:remove"];
    members = [{ user_id: "u-owner", role: "owner" }];
    renderRoute();
    expect(screen.getAllByText("Propietario").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByLabelText("Acciones de u-owner")).toBeNull();
    expect(screen.queryByRole("menuitem", { name: /Remover/i })).toBeNull();
  });

  it("hides the + Invitar button when members:invite is false; shows + opens when true", () => {
    permissions = [];
    members = [];
    const { rerender } = renderRoute();
    expect(screen.queryByRole("button", { name: /\+ Invitar/i })).toBeNull();

    permissions = ["members:invite"];
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <EmpresaUsuariosRoute />
      </QueryClientProvider>,
    );
    const inviteBtn = screen.getByRole("button", { name: /\+ Invitar/i });
    expect(inviteBtn).toBeInTheDocument();
    fireEvent.click(inviteBtn);
    expect(screen.getByText(/Invitar miembro/i)).toBeInTheDocument();
  });

  it("seeds the global filter input from the URL `q` search param", () => {
    permissions = [];
    members = [
      { user_id: "u-1", role: "viewer" },
      { user_id: "u-2", role: "admin" },
    ];
    setSearchState({ q: "viewer" });
    renderRoute();
    const search = screen.getByPlaceholderText(/Buscar miembro/i) as HTMLInputElement;
    expect(search.value).toBe("viewer");
  });

  it("pushes the active tab to URL search params and survives back to default", async () => {
    permissions = ["members:invite"];
    invitations = [{ id: "i-1", email: "x@y.com", proposed_role: "viewer", status: "pending" }];
    renderRoute();
    const invitationsTab = screen.getByRole("tab", { name: /Invitaciones/i });
    await act(async () => {
      fireEvent.mouseDown(invitationsTab);
      fireEvent.click(invitationsTab);
    });
    expect(currentSearch).toEqual({ tab: "invitations" });

    const membersTab = screen.getByRole("tab", { name: /Miembros/i });
    await act(async () => {
      fireEvent.mouseDown(membersTab);
      fireEvent.click(membersTab);
    });
    // Default tab collapses away — never persisted as `tab=members`.
    expect(currentSearch).toEqual({});
  });

  it("renders pending invitations with a Cancelar button under the Invitaciones tab", async () => {
    permissions = ["members:invite"];
    invitations = [
      { id: "i-1", email: "x@y.com", proposed_role: "viewer", status: "pending" },
      { id: "i-2", email: "z@w.com", proposed_role: "admin", status: "accepted" },
    ];
    renderRoute();
    // Radix Tabs requires pointerdown before click to activate via mouse,
    // and unmounts inactive content by default.
    const invitationsTab = screen.getByRole("tab", { name: /Invitaciones/i });
    await act(async () => {
      fireEvent.mouseDown(invitationsTab);
      fireEvent.click(invitationsTab);
    });
    expect(await screen.findByText("x@y.com")).toBeInTheDocument();
    expect(screen.queryByText("z@w.com")).toBeNull();
    expect(screen.getByRole("button", { name: /Cancelar/i })).toBeInTheDocument();
  });
});
