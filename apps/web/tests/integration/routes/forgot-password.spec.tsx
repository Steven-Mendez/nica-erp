// Smoke + behaviour test for /forgot-password. Covers Zod email
// validation, valid submit firing useForgotPasswordMutation, and the
// success alert when the mutation isSuccess.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const forgotSpy = vi.fn();
let isSuccess = false;

vi.mock("@/features/auth/api/hooks", () => ({
  useForgotPasswordMutation: () => ({
    mutate: (vars: { email: string }, opts?: { onSuccess?: () => void }) => {
      forgotSpy(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isSuccess,
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

import { ForgotPasswordRoute } from "@/routes/forgot-password";

function renderForgot() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ForgotPasswordRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  forgotSpy.mockReset();
  isSuccess = false;
});

describe("ForgotPasswordRoute", () => {
  beforeEach(() => {
    forgotSpy.mockReset();
  });

  it("blocks submission when the email is invalid", async () => {
    renderForgot();
    fireEvent.change(screen.getByLabelText(/Correo/i), {
      target: { value: "not-an-email" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Enviar código/i }));
    await waitFor(() => expect(forgotSpy).not.toHaveBeenCalled());
  });

  it("submits with the email when valid", async () => {
    renderForgot();
    fireEvent.change(screen.getByLabelText(/Correo/i), {
      target: { value: "ada@nica.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Enviar código/i }));
    await waitFor(() => expect(forgotSpy).toHaveBeenCalledTimes(1));
    expect(forgotSpy).toHaveBeenCalledWith({ email: "ada@nica.test" });
  });

  it("renders the enumeration-resistant success alert when mutation isSuccess", () => {
    isSuccess = true;
    renderForgot();
    expect(
      screen.getByText(/Si el correo está registrado, te enviamos un código/i),
    ).toBeInTheDocument();
  });
});
