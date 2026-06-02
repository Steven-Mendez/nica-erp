// Unit tests for MembersTable. Covers loading skeleton, error alert,
// the owner-row no-actions guarantee, Spanish role labels, search-box
// global filter, and the empty-state copy.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Member } from "@/features/tenants/api/endpoints";

type RemoveArgs = { userId: string };
let removeCalls: RemoveArgs[] = [];
const removeMutate = vi.fn((args: RemoveArgs) => {
  removeCalls.push(args);
});

vi.mock("@/features/tenants/api/hooks", () => ({
  useRemoveMemberMutation: () => ({ mutate: removeMutate, isPending: false }),
  useUpdateMemberRoleMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { MembersTable } from "@/features/tenants/components/MembersTable";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    user_id: "u-1",
    tenant_id: tenantId,
    role: "viewer",
    status: "active",
    joined_at: "2026-01-01T00:00:00Z",
    removed_at: null,
    display_name: null,
    email: null,
    ...overrides,
  };
}

function renderTable(props: {
  data?: Member[];
  isLoading?: boolean;
  isError?: boolean;
  canUpdateRole?: boolean;
  canRemove?: boolean;
}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MembersTable
        tenantId={tenantId}
        data={props.data}
        isLoading={props.isLoading ?? false}
        isError={props.isError ?? false}
        canUpdateRole={props.canUpdateRole ?? false}
        canRemove={props.canRemove ?? false}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  removeCalls = [];
  removeMutate.mockClear();
});

describe("MembersTable", () => {
  beforeEach(() => {
    // no-op; hooks are stubbed.
  });

  it("renders a Skeleton while loading", () => {
    const { container } = renderTable({ isLoading: true });
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("shows the destructive alert when isError is true", () => {
    renderTable({ isError: true });
    expect(screen.getByText(/No se pudieron cargar los miembros/i)).toBeInTheDocument();
  });

  it("renders Spanish role badges", () => {
    renderTable({
      data: [
        makeMember({ user_id: "u-owner", role: "owner" }),
        makeMember({ user_id: "u-admin", role: "admin" }),
        makeMember({ user_id: "u-viewer", role: "viewer" }),
      ],
    });
    // The table renders both a desktop <table> branch and a mobile
    // card branch (CSS-toggled by viewport); both surface the role
    // badge text, so each Spanish label appears twice in the DOM
    // under jsdom (where no CSS media query is applied).
    expect(screen.getAllByText("Propietario").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Administrador").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Lector").length).toBeGreaterThanOrEqual(1);
  });

  it("never renders an actions menu on the owner row", () => {
    renderTable({
      data: [
        makeMember({ user_id: "u-owner", role: "owner" }),
        makeMember({ user_id: "u-2", role: "viewer" }),
      ],
      canUpdateRole: true,
      canRemove: true,
    });
    expect(screen.queryByLabelText("Acciones de u-owner")).toBeNull();
    expect(screen.getByLabelText("Acciones de u-2")).toBeInTheDocument();
  });

  it("hides actions when both canUpdateRole and canRemove are false", () => {
    renderTable({
      data: [makeMember({ user_id: "u-2", role: "viewer" })],
      canUpdateRole: false,
      canRemove: false,
    });
    expect(screen.queryByLabelText("Acciones de u-2")).toBeNull();
  });

  it("debounces the search box and forwards the value via onViewStateChange", async () => {
    // The table now runs in server-side mode (manualFiltering), so
    // typing into the search box no longer hides rows itself. Instead,
    // the debounced value reaches the route via `onViewStateChange`,
    // which writes it to the URL search params and triggers a refetch.
    // This test pins that contract.
    const captured: string[] = [];
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MembersTable
          tenantId={tenantId}
          data={[
            makeMember({ user_id: "u-1", email: "ada@nica.test", role: "viewer" }),
            makeMember({ user_id: "u-2", email: "bob@nica.test", role: "admin" }),
          ]}
          total={2}
          isLoading={false}
          isError={false}
          canUpdateRole={false}
          canRemove={false}
          viewState={{
            sorting: [],
            columnFilters: [],
            globalFilter: "",
            pagination: { pageIndex: 0, pageSize: 10 },
          }}
          onViewStateChange={(next) => captured.push(next.globalFilter)}
        />
      </QueryClientProvider>,
    );
    const search = screen.getByPlaceholderText(/Buscar miembro/i);
    fireEvent.change(search, { target: { value: "ada" } });
    await waitFor(() => {
      expect(captured).toContain("ada");
    });
    // Server-side mode means both rows remain visible — the table
    // trusts the API to send back only matching ones. Each email
    // appears in both the desktop table cell and the mobile card
    // body (CSS-toggled by viewport), so the test asserts on the
    // count rather than uniqueness.
    expect(screen.getAllByText("ada@nica.test").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("bob@nica.test").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the empty-state copy when there are no members", () => {
    renderTable({ data: [] });
    // Same dual-branch dance as the role-badge test: the empty
    // state copy is rendered once per layout branch.
    expect(screen.getAllByText(/Sin miembros para mostrar/i).length).toBeGreaterThanOrEqual(1);
  });

  it("opens the destructive dialog when Remover is selected; fires removeMember only after confirmation", async () => {
    renderTable({
      data: [makeMember({ user_id: "u-2", role: "viewer", display_name: "Ada" })],
      canRemove: true,
    });
    const trigger = screen.getByLabelText("Acciones de u-2");
    await act(async () => {
      fireEvent.pointerDown(trigger, { button: 0 });
      fireEvent.click(trigger);
    });
    const remover = await screen.findByRole("menuitem", { name: /Remover/i });
    await act(async () => {
      fireEvent.click(remover);
    });
    // Dialog opens — no mutation yet.
    expect(removeCalls).toEqual([]);
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/Remover a Ada de la empresa/i);
    // Confirm fires the mutation exactly once.
    fireEvent.click(screen.getByRole("button", { name: /Sí, remover/i }));
    expect(removeCalls).toEqual([{ userId: "u-2" }]);
  });

  it("renders both responsive branches with the documented class composition", () => {
    const { container } = renderTable({
      data: [makeMember({ user_id: "u-1", role: "viewer" })],
    });
    // Desktop branch: hidden on mobile, block on md+. Mobile branch:
    // visible on mobile, hidden on md+. jsdom does not apply the
    // Tailwind media queries, so the test asserts the class
    // composition — the only contract we can pin without a real
    // browser.
    const desktop = container.querySelector(".hidden.md\\:block");
    const mobile = container.querySelector(".md\\:hidden");
    expect(desktop).not.toBeNull();
    expect(mobile).not.toBeNull();
    expect(desktop?.querySelector("table")).not.toBeNull();
    expect(mobile?.querySelector("table")).toBeNull();
  });

  it("renders the result counter inside the toolbar", () => {
    renderTable({
      data: [
        makeMember({ user_id: "u-1", role: "viewer" }),
        makeMember({ user_id: "u-2", role: "admin" }),
      ],
    });
    // Toolbar caption is the only one that says "resultado(s)".
    const counter = screen.getByText(/resultado\(s\)/);
    expect(within(counter).getByText(/2 resultado\(s\)/)).toBeInTheDocument();
  });
});
