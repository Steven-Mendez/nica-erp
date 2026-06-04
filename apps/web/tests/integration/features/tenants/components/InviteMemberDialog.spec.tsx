// Unit tests for InviteMemberDialog. Exercises the shadcn-driven form:
// trigger opens the Dialog, Zod validation surfaces the Spanish email
// error, valid submit hits useInviteMemberMutation with the form values,
// and a mutation error renders inside the destructive Alert.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type MutateArgs = {
  values: { email: string; proposed_role: string };
  handlers: { onSuccess?: () => void; onError?: (err: Error) => void };
};

let mutateCalls: MutateArgs[] = [];
let mutateImpl: (args: MutateArgs) => void = ({ handlers }) => {
  handlers.onSuccess?.();
};
let isPending = false;
let mutationError: unknown = null;

vi.mock("@/features/tenants/api/hooks", () => ({
  useInviteMemberMutation: () => ({
    mutate: (values: MutateArgs["values"], handlers: MutateArgs["handlers"] = {}) => {
      const args = { values, handlers };
      mutateCalls.push(args);
      mutateImpl(args);
    },
    // The component now uses `mutateAsync` (returns a Promise). Mirror
    // it onto the same recording so existing assertions continue to
    // work; errors are surfaced via promise rejection.
    mutateAsync: (values: MutateArgs["values"], handlers: MutateArgs["handlers"] = {}) => {
      const args = { values, handlers };
      mutateCalls.push(args);
      mutateImpl(args);
      if (mutationError !== null) {
        return Promise.reject(mutationError);
      }
      return Promise.resolve(undefined);
    },
    isPending,
    error: mutationError,
    reset: () => {
      mutationError = null;
    },
  }),
}));

import { InviteMemberDialog } from "@/features/tenants/components/InviteMemberDialog";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

function renderDialog() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <InviteMemberDialog tenantId={tenantId} />
    </QueryClientProvider>,
  );
}

function openDialog() {
  const trigger = screen.getByRole("button", { name: /\+ Invitar/i });
  fireEvent.click(trigger);
}

afterEach(() => {
  cleanup();
  mutateCalls = [];
  mutateImpl = ({ handlers }) => handlers.onSuccess?.();
  isPending = false;
  mutationError = null;
});

describe("InviteMemberDialog", () => {
  beforeEach(() => {
    mutateCalls = [];
    isPending = false;
  });

  it("opens the dialog when the trigger is clicked", () => {
    renderDialog();
    expect(screen.queryByRole("dialog")).toBeNull();
    openDialog();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Invitar miembro/i })).toBeInTheDocument();
  });

  it("surfaces the Zod email error in Spanish and blocks submission", async () => {
    renderDialog();
    openDialog();

    const email = screen.getByLabelText(/Correo/i);
    fireEvent.change(email, { target: { value: "not-an-email" } });

    const submit = screen.getByRole("button", { name: /Enviar invitación/i });
    await act(async () => {
      fireEvent.click(submit);
    });

    expect(await screen.findByText(/Ingresa un correo válido/i)).toBeInTheDocument();
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(mutateCalls).toHaveLength(0);
  });

  it("submits the form values via the mutation and closes the dialog on success", async () => {
    renderDialog();
    openDialog();

    const email = screen.getByLabelText(/Correo/i);
    fireEvent.change(email, { target: { value: "ada@nica.test" } });

    const submit = screen.getByRole("button", { name: /Enviar invitación/i });
    await act(async () => {
      fireEvent.click(submit);
    });

    await waitFor(() => expect(mutateCalls).toHaveLength(1));
    expect(mutateCalls[0]?.values).toEqual({
      email: "ada@nica.test",
      proposed_role: "accountant",
    });

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("renders the FormErrorAlert with the registry copy on a 409 duplicate-pending error", async () => {
    // The mutation's `error` is what drives <FormErrorAlert> now; the
    // mock surfaces an ApiError-shaped value that maps to the
    // duplicate-pending registry entry.
    mutationError = {
      name: "ApiError",
      status: 409,
      detail: { code: "tenants.invitation_duplicate_pending" },
    };
    mutateImpl = () => undefined; // suppress onSuccess close on submit
    renderDialog();
    openDialog();

    expect(
      await screen.findByText(/esta persona ya tiene una invitación pendiente\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows 'Enviando…' and disables the submit while pending", () => {
    isPending = true;
    renderDialog();
    openDialog();
    const submit = screen.getByRole("button", { name: /Enviando…/i });
    expect(submit).toBeDisabled();
  });
});
