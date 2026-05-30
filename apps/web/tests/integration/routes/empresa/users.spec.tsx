// Smoke tests for /empresa/users — permission gating on the row
// actions menu, the owner-row guarantee, the `+ Invitar` button, and
// the pending-invitations tab.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EmpresaUsuariosRoute } from "@/routes/empresa/users";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

let permissions: string[] = [];
let members: Array<{ user_id: string; role: string }> = [];
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
  // Route-level hooks.
  useMembersQuery: () => ({ data: members, isLoading: false, isError: false }),
  useInvitationsQuery: () => ({ data: invitations, isLoading: false }),
  useInviteMemberMutation: () => ({ mutate: () => undefined, isPending: false }),
  useRemoveMemberMutation: () => ({ mutate: () => undefined, isPending: false }),
  useCancelInvitationMutation: () => ({ mutate: () => undefined, isPending: false }),
  useUpdateMemberRoleMutation: () => ({ mutate: () => undefined, isPending: false }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/empresa/users" }),
    useNavigate: () => () => undefined,
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
});

describe("EmpresaUsuariosRoute", () => {
  beforeEach(() => {
    permissions = [];
    members = [];
    invitations = [];
  });

  it("with members:update-role true, exposes a row actions menu for non-owner rows", () => {
    permissions = ["members:update-role"];
    members = [
      { user_id: "u-owner", role: "owner" },
      { user_id: "u-2", role: "viewer" },
    ];
    renderRoute();
    // Row-level actions menu trigger appears for the non-owner row.
    expect(screen.getByLabelText("Acciones de u-2")).toBeInTheDocument();
    // Owner row never gets the actions menu.
    expect(screen.queryByLabelText("Acciones de u-owner")).toBeNull();
  });

  it("without members:update-role and without members:remove, no actions menu is shown", () => {
    permissions = [];
    members = [{ user_id: "u-2", role: "viewer" }];
    renderRoute();
    expect(screen.queryByLabelText("Acciones de u-2")).toBeNull();
    // The role is still surfaced as a badge.
    expect(screen.getByText("Lector")).toBeInTheDocument();
  });

  it("owner row renders the role badge but never the actions menu", () => {
    permissions = ["members:update-role", "members:remove"];
    members = [{ user_id: "u-owner", role: "owner" }];
    renderRoute();
    expect(screen.getByText("Propietario")).toBeInTheDocument();
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
