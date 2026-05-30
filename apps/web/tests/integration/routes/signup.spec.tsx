// Smoke + behaviour test for /signup. Covers Zod password-mismatch
// blocking submit, the show/hide password toggle, valid submit firing
// useRegisterMutation, and the destructive Alert on mutation error.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const registerSpy = vi.fn();
let isError = false;

vi.mock("@/features/auth/api/hooks", () => ({
  useRegisterMutation: () => ({
    mutate: (vars: { email: string; password: string }, opts?: { onSuccess?: () => void }) => {
      registerSpy(vars);
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
    useSearch: () => ({ email: undefined }),
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

import { SignupRoute } from "@/routes/signup";

function renderSignup() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SignupRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  registerSpy.mockReset();
  isError = false;
});

describe("SignupRoute", () => {
  beforeEach(() => {
    registerSpy.mockReset();
  });

  it("renders email, password and confirm fields", () => {
    renderSignup();
    expect(screen.getByLabelText(/^Correo$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Contraseña$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Confirmar contraseña/i)).toBeInTheDocument();
  });

  it("toggles the password visibility when the eye button is clicked", () => {
    renderSignup();
    const passwordInput = screen.getByLabelText(/^Contraseña$/i) as HTMLInputElement;
    expect(passwordInput.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: /Mostrar contraseña/i }));
    expect(passwordInput.type).toBe("text");
    fireEvent.click(screen.getByRole("button", { name: /Ocultar contraseña/i }));
    expect(passwordInput.type).toBe("password");
  });

  it("blocks submission when passwords do not match", async () => {
    renderSignup();
    fireEvent.change(screen.getByLabelText(/^Correo$/i), {
      target: { value: "ada@nica.test" },
    });
    fireEvent.change(screen.getByLabelText(/^Contraseña$/i), {
      target: { value: "Sup3rPass!2026" },
    });
    fireEvent.change(screen.getByLabelText(/Confirmar contraseña/i), {
      target: { value: "different" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear cuenta/i }));
    await waitFor(() => expect(registerSpy).not.toHaveBeenCalled());
  });

  it("submits email + password (without confirm) when valid", async () => {
    renderSignup();
    fireEvent.change(screen.getByLabelText(/^Correo$/i), {
      target: { value: "ada@nica.test" },
    });
    fireEvent.change(screen.getByLabelText(/^Contraseña$/i), {
      target: { value: "Sup3rPass!2026" },
    });
    fireEvent.change(screen.getByLabelText(/Confirmar contraseña/i), {
      target: { value: "Sup3rPass!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear cuenta/i }));
    await waitFor(() => expect(registerSpy).toHaveBeenCalledTimes(1));
    expect(registerSpy).toHaveBeenCalledWith({
      email: "ada@nica.test",
      password: "Sup3rPass!2026",
    });
  });

  it("renders the destructive Alert when the mutation isError is true", () => {
    isError = true;
    renderSignup();
    expect(screen.getByText(/No se pudo crear la cuenta/i)).toBeInTheDocument();
  });
});
