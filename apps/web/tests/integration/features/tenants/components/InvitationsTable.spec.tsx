// Unit tests for InvitationsTable. Covers the loading skeleton,
// empty-state alert, pending-only row filter, and the Cancelar
// affordance gated by `canCancel`.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Invitation } from "@/features/tenants/api/endpoints";

type CancelArgs = { invitationId: string };
let cancelCalls: CancelArgs[] = [];

vi.mock("@/features/tenants/api/hooks", () => ({
  useCancelInvitationMutation: () => ({
    mutate: (args: CancelArgs) => {
      cancelCalls.push(args);
    },
    isPending: false,
  }),
}));

import { InvitationsTable } from "@/features/tenants/components/InvitationsTable";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

function makeInvitation(overrides: Partial<Invitation> = {}): Invitation {
  return {
    id: "i-1",
    tenant_id: tenantId,
    email: "ada@nica.test",
    proposed_role: "viewer",
    status: "pending",
    expires_at: "2030-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    cancelled_at: null,
    ...overrides,
  };
}

function renderTable(props: { data?: Invitation[]; isLoading?: boolean; canCancel?: boolean }) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <InvitationsTable
        tenantId={tenantId}
        data={props.data}
        isLoading={props.isLoading ?? false}
        canCancel={props.canCancel ?? true}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  cancelCalls = [];
});

describe("InvitationsTable", () => {
  beforeEach(() => {
    cancelCalls = [];
  });

  it("renders a Skeleton while loading", () => {
    const { container } = renderTable({ isLoading: true });
    // Skeleton has no role; assert the marker class.
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("shows the empty-state alert when there are no pending invitations", () => {
    renderTable({ data: [], isLoading: false });
    expect(screen.getByText(/No hay invitaciones pendientes/i)).toBeInTheDocument();
  });

  it("filters out non-pending rows from the table", () => {
    renderTable({
      data: [
        makeInvitation({ id: "i-pending", email: "x@y.com", status: "pending" }),
        makeInvitation({ id: "i-accepted", email: "z@w.com", status: "accepted" }),
      ],
    });
    expect(screen.getByText("x@y.com")).toBeInTheDocument();
    expect(screen.queryByText("z@w.com")).toBeNull();
  });

  it("renders the Cancelar button when canCancel is true and triggers the mutation", () => {
    renderTable({
      data: [makeInvitation({ id: "i-1", email: "x@y.com" })],
      canCancel: true,
    });
    const cancelBtn = screen.getByRole("button", { name: /Cancelar/i });
    fireEvent.click(cancelBtn);
    expect(cancelCalls).toEqual([{ invitationId: "i-1" }]);
  });

  it("hides the Cancelar button when canCancel is false", () => {
    renderTable({
      data: [makeInvitation()],
      canCancel: false,
    });
    expect(screen.queryByRole("button", { name: /Cancelar/i })).toBeNull();
  });
});
