// Smoke + behaviour test for /login. Verifies the form renders,
// Zod blocks an empty submit, valid credentials hit useLoginMutation,
// and the destructive Alert surfaces when the mutation errors.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const loginSpy = vi.fn();
let isError = false;
let isPending = false;
let mutationError: unknown = null;

vi.mock("@/features/auth/api/hooks", () => ({
  useLoginMutation: () => ({
    mutate: (vars: { email: string; password: string }, opts?: { onSuccess?: () => void }) => {
      loginSpy(vars);
      opts?.onSuccess?.();
    },
    isPending,
    isError,
    error: mutationError,
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

import { LoginRoute } from "@/routes/login";

function renderLogin() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <LoginRoute />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  loginSpy.mockReset();
  isError = false;
  isPending = false;
  mutationError = null;
});

describe("LoginRoute", () => {
  beforeEach(() => {
    loginSpy.mockReset();
  });

  it("renders the email and password fields", () => {
    renderLogin();
    expect(screen.getByLabelText(/Correo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contraseña/i)).toBeInTheDocument();
  });

  it("blocks empty submit via Zod and never fires the mutation", async () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: /Iniciar sesión/i }));
    await waitFor(() => expect(loginSpy).not.toHaveBeenCalled());
  });

  it("calls useLoginMutation with email and password on a valid submit", async () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText(/Correo/i), {
      target: { value: "ada@nica.test" },
    });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), {
      target: { value: "Sup3rPass!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Iniciar sesión/i }));
    await waitFor(() => expect(loginSpy).toHaveBeenCalledTimes(1));
    expect(loginSpy).toHaveBeenCalledWith({
      email: "ada@nica.test",
      password: "Sup3rPass!2026",
    });
  });

  it("renders the FormErrorAlert with Spanish copy when the mutation errors", () => {
    isError = true;
    mutationError = {
      name: "ApiError",
      status: 401,
      detail: { code: "auth.invalid_credentials" },
    };
    renderLogin();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /correo o contraseña incorrectos/i,
    );
  });

  it("renders the lockout copy with the retry window for a 429 lockout", () => {
    isError = true;
    mutationError = {
      name: "ApiError",
      status: 429,
      detail: { code: "auth.lockout_active", retry_after_seconds: 600 },
    };
    renderLogin();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /demasiados intentos\. intenta de nuevo en 10 minutos/i,
    );
  });
});
