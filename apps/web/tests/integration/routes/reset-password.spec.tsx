// Smoke + behaviour test for /reset-password. Covers Zod validation,
// preselected email from search params, valid submit firing
// useResetPasswordMutation, and the destructive Alert on error.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resetSpy = vi.fn();
let isError = false;

vi.mock("@/features/auth/api/hooks", () => ({
  useResetPasswordMutation: () => ({
    mutate: (
      vars: { email: string; code: string; new_password: string },
      opts?: { onSuccess?: () => void },
    ) => {
      resetSpy(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isError,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => () => undefined,
    useSearch: () => ({ email: "ada@nica.test" }),
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

import { ResetPasswordRoute } from "@/routes/reset-password";

function renderReset() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ResetPasswordRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  resetSpy.mockReset();
  isError = false;
});

describe("ResetPasswordRoute", () => {
  beforeEach(() => {
    resetSpy.mockReset();
  });

  it("preselects the email from search params", () => {
    renderReset();
    expect(screen.getByLabelText(/Correo/i)).toHaveValue("ada@nica.test");
  });

  it("blocks submission when the code or password is missing", async () => {
    renderReset();
    fireEvent.click(screen.getByRole("button", { name: /Restablecer contraseña/i }));
    await waitFor(() => expect(resetSpy).not.toHaveBeenCalled());
  });

  it("submits all three fields when valid", async () => {
    renderReset();
    fireEvent.change(screen.getByLabelText(/Código de recuperación/i), {
      target: { value: "123456" },
    });
    fireEvent.change(screen.getByLabelText(/Nueva contraseña/i), {
      target: { value: "N3wP4ss!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Restablecer contraseña/i }));
    await waitFor(() => expect(resetSpy).toHaveBeenCalledTimes(1));
    expect(resetSpy).toHaveBeenCalledWith({
      email: "ada@nica.test",
      code: "123456",
      new_password: "N3wP4ss!2026",
    });
  });

  it("renders the destructive Alert when the mutation isError is true", () => {
    isError = true;
    renderReset();
    expect(screen.getByText(/No se pudo restablecer la contraseña/i)).toBeInTheDocument();
  });
});
