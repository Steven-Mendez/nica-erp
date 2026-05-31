// Unit tests for MembersTable. Covers loading skeleton, error alert,
// the owner-row no-actions guarantee, Spanish role labels, search-box
// global filter, and the empty-state copy.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Member } from "@/features/tenants/api/endpoints";

vi.mock("@/features/tenants/api/hooks", () => ({
  useRemoveMemberMutation: () => ({ mutate: vi.fn(), isPending: false }),
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
    expect(screen.getByText("Propietario")).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();
    expect(screen.getByText("Lector")).toBeInTheDocument();
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
    // trusts the API to send back only matching ones.
    expect(screen.getByText("ada@nica.test")).toBeInTheDocument();
    expect(screen.getByText("bob@nica.test")).toBeInTheDocument();
  });

  it("shows the empty-state copy when there are no members", () => {
    renderTable({ data: [] });
    expect(screen.getByText(/Sin miembros para mostrar/i)).toBeInTheDocument();
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
