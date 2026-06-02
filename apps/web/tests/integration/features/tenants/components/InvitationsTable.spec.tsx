// Unit tests for InvitationsTable. Covers the loading skeleton,
// empty-state alert, pending-only row filter, and the Cancelar
// affordance gated by `canCancel`.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Invitation } from "@/features/tenants/api/endpoints";

type CancelArgs = { invitationId: string };
type ResendArgs = { invitationId: string };
let cancelCalls: CancelArgs[] = [];
let cancelIsError = false;
let resendCalls: ResendArgs[] = [];
let resendIsError = false;
let resendIsSuccess = false;

vi.mock("@/features/tenants/api/hooks", () => ({
  useCancelInvitationMutation: () => ({
    mutate: (args: CancelArgs) => {
      cancelCalls.push(args);
    },
    isPending: false,
    isError: cancelIsError,
  }),
  useResendInvitationMutation: () => ({
    mutate: (args: ResendArgs) => {
      resendCalls.push(args);
    },
    isPending: false,
    isError: resendIsError,
    isSuccess: resendIsSuccess,
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
  cancelIsError = false;
  resendCalls = [];
  resendIsError = false;
  resendIsSuccess = false;
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

  it("opens the destructive confirm dialog when Cancelar is clicked; fires mutation only after confirmation", async () => {
    renderTable({
      data: [makeInvitation({ id: "i-1", email: "x@y.com" })],
      canCancel: true,
    });
    const cancelBtn = screen.getByRole("button", { name: "Cancelar" });
    fireEvent.click(cancelBtn);
    // Dialog opens — no mutation yet.
    expect(cancelCalls).toEqual([]);
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/cancelar la invitación enviada a x@y\.com/i);
    // Confirm fires the mutation exactly once.
    fireEvent.click(screen.getByRole("button", { name: /Sí, cancelar/i }));
    expect(cancelCalls).toEqual([{ invitationId: "i-1" }]);
  });

  it("hides the Cancelar button when canCancel is false", () => {
    renderTable({
      data: [makeInvitation()],
      canCancel: false,
    });
    expect(screen.queryByRole("button", { name: /Cancelar/i })).toBeNull();
  });

  it("renders the Spanish rollback alert when the cancel mutation errors", () => {
    cancelIsError = true;
    renderTable({ data: [makeInvitation()] });
    expect(screen.getByText(/No se pudo cancelar la invitación\./i)).toBeInTheDocument();
  });

  it("fires the resend mutation when the Reenviar button is clicked", () => {
    renderTable({ data: [makeInvitation({ id: "i-1" })] });
    const resend = screen.getByRole("button", { name: /Reenviar/i });
    fireEvent.click(resend);
    expect(resendCalls).toEqual([{ invitationId: "i-1" }]);
  });

  it("surfaces the success copy when the resend mutation succeeds", () => {
    resendIsSuccess = true;
    renderTable({ data: [makeInvitation()] });
    expect(screen.getByText(/Invitación reenviada con un nuevo enlace\./i)).toBeInTheDocument();
  });

  it("surfaces the error copy when the resend mutation fails", () => {
    resendIsError = true;
    renderTable({ data: [makeInvitation()] });
    expect(screen.getByText(/No se pudo reenviar la invitación\./i)).toBeInTheDocument();
  });
});
