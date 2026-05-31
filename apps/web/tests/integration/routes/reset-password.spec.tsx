// Smoke + behaviour test for /reset-password. Covers Zod validation,
// preselected email from search params, valid submit firing
// useResetPasswordMutation, the destructive Alert on error, the pending
// state, the success-path navigation to /login, and per-field validation
// errors for code length + password policy.
//
// Note: the form has a single new-password input, so a literal "passwords
// no coinciden" branch does not exist here — the analogous failure mode
// (expired or replayed token from the backend) is covered via the
// destructive Alert path.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { resetSpy, navigateSpy, useResetMock } = vi.hoisted(() => ({
  resetSpy: vi.fn(),
  navigateSpy: vi.fn(),
  useResetMock: vi.fn(),
}));

vi.mock("@/features/auth/api/hooks", () => ({
  useResetPasswordMutation: useResetMock,
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => navigateSpy,
    useSearch: () => ({ email: "ada@nica.test" }),
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

import { ResetPasswordRoute } from "@/routes/reset-password";

interface MutationOverrides {
  outcome?: "success" | "noop";
  isPending?: boolean;
  isError?: boolean;
}

function installResetMutation(overrides: MutationOverrides = {}) {
  const { outcome = "success", isPending = false, isError = false } = overrides;
  useResetMock.mockReturnValue({
    mutate: (
      vars: { email: string; code: string; new_password: string },
      opts?: { onSuccess?: () => void },
    ) => {
      resetSpy(vars);
      if (outcome === "success") opts?.onSuccess?.();
    },
    isPending,
    isError,
  });
}

function renderReset() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ResetPasswordRoute />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  resetSpy.mockReset();
  navigateSpy.mockReset();
  useResetMock.mockReset();
  installResetMutation();
});

afterEach(() => {
  cleanup();
});

describe("ResetPasswordRoute", () => {
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

  it("navigates to /login on successful reset", async () => {
    renderReset();
    fireEvent.change(screen.getByLabelText(/Código de recuperación/i), {
      target: { value: "123456" },
    });
    fireEvent.change(screen.getByLabelText(/Nueva contraseña/i), {
      target: { value: "N3wP4ss!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Restablecer contraseña/i }));
    await waitFor(() => {
      expect(navigateSpy).toHaveBeenCalledWith({ to: "/login" });
    });
  });

  it("renders the destructive Alert when the mutation isError is true (e.g. expired token)", () => {
    installResetMutation({ isError: true, outcome: "noop" });
    renderReset();
    expect(screen.getByText(/No se pudo restablecer la contraseña/i)).toBeInTheDocument();
  });

  it("shows 'Restableciendo...' and disables the submit while the mutation is pending", () => {
    installResetMutation({ isPending: true, outcome: "noop" });
    renderReset();
    const button = screen.getByRole("button", {
      name: /Restableciendo|Restablecer contraseña/i,
    });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Restableciendo...");
  });

  it("flags a short recovery code with an inline field error", async () => {
    renderReset();
    fireEvent.change(screen.getByLabelText(/Código de recuperación/i), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText(/Nueva contraseña/i), {
      target: { value: "N3wP4ss!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Restablecer contraseña/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Código de recuperación/i)).toHaveAttribute(
        "aria-invalid",
        "true",
      );
    });
    expect(resetSpy).not.toHaveBeenCalled();
  });

  it("flags a weak password with an inline field error", async () => {
    renderReset();
    fireEvent.change(screen.getByLabelText(/Código de recuperación/i), {
      target: { value: "123456" },
    });
    fireEvent.change(screen.getByLabelText(/Nueva contraseña/i), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Restablecer contraseña/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Nueva contraseña/i)).toHaveAttribute("aria-invalid", "true");
    });
    expect(resetSpy).not.toHaveBeenCalled();
  });
});
