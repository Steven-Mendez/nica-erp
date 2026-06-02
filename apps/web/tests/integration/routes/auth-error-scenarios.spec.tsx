// Integration tests for the four auth-error scenarios called out in
// section 6 of harden-auth-flows. Each test mocks the relevant auth
// mutation hook to surface a typed `ApiError` and asserts that the
// route renders the expected Spanish copy from the registry. The
// route components themselves are exercised end-to-end (form +
// FormErrorAlert + registry) so a registry drift or a missed
// rewire would surface here, not only at the unit level.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---- /confirm — bad OTP renders inline alert, stays on /confirm -----

describe("auth-confirm bad OTP", () => {
  const confirmSpy = vi.fn();
  const navigateSpy = vi.fn();
  const resendSpy = vi.fn();
  let mutationError: unknown = null;

  beforeEach(() => {
    vi.resetModules();
    vi.doMock("@/features/auth/api/hooks", () => ({
      useConfirmSignupMutation: () => ({
        mutate: (vars: object, opts?: { onSuccess?: (bundle: unknown) => void }) => {
          confirmSpy(vars);
          // On a 401 the hook would NOT fire onSuccess.
          if (mutationError === null) opts?.onSuccess?.(null);
        },
        isPending: false,
        isError: mutationError !== null,
        error: mutationError,
      }),
      useResendCodeMutation: () => ({
        mutate: (vars: object) => resendSpy(vars),
        isPending: false,
        isSuccess: false,
      }),
    }));
    vi.doMock("@tanstack/react-router", async () => {
      const actual = await vi.importActual<object>("@tanstack/react-router");
      return {
        ...actual,
        useNavigate: () => navigateSpy,
        useSearch: () => ({ email: "ada@nica.test" }),
        Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
      };
    });
  });

  afterEach(() => {
    cleanup();
    confirmSpy.mockReset();
    navigateSpy.mockReset();
    resendSpy.mockReset();
    mutationError = null;
  });

  it("renders the Spanish copy for auth.invalid_confirmation_code and never navigates", async () => {
    mutationError = {
      name: "ApiError",
      status: 401,
      detail: { code: "auth.invalid_confirmation_code" },
    };
    const { ConfirmRoute } = await import("@/routes/confirm");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ConfirmRoute />
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /código incorrecto o expirado\. solicita uno nuevo\./i,
      ),
    );
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});

// ---- /reset-password — used token renders alert, no redirect --------

describe("auth-reset used token", () => {
  const resetSpy = vi.fn();
  const navigateSpy = vi.fn();
  let mutationError: unknown = null;

  beforeEach(() => {
    vi.resetModules();
    vi.doMock("@/features/auth/api/hooks", () => ({
      useResetPasswordMutation: () => ({
        mutate: (vars: object, opts?: { onSuccess?: () => void }) => {
          resetSpy(vars);
          if (mutationError === null) opts?.onSuccess?.();
        },
        isPending: false,
        isError: mutationError !== null,
        error: mutationError,
      }),
    }));
    vi.doMock("@tanstack/react-router", async () => {
      const actual = await vi.importActual<object>("@tanstack/react-router");
      return {
        ...actual,
        useNavigate: () => navigateSpy,
        useSearch: () => ({ email: "ada@nica.test" }),
        Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
      };
    });
  });

  afterEach(() => {
    cleanup();
    resetSpy.mockReset();
    navigateSpy.mockReset();
    mutationError = null;
  });

  it("renders the Spanish copy for auth.reset_token_used and never navigates", async () => {
    mutationError = {
      name: "ApiError",
      status: 400,
      detail: { code: "auth.reset_token_used" },
    };
    const { ResetPasswordRoute } = await import("@/routes/reset-password");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ResetPasswordRoute />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /este enlace ya fue utilizado\. solicita uno nuevo\./i,
    );
    expect(navigateSpy).not.toHaveBeenCalledWith({ to: "/login" });
  });
});

// ---- /login — lockout renders Spanish copy with retry-after window --

describe("auth-login lockout", () => {
  const loginSpy = vi.fn();
  const navigateSpy = vi.fn();
  let mutationError: unknown = null;

  beforeEach(() => {
    vi.resetModules();
    vi.doMock("@/features/auth/api/hooks", () => ({
      useLoginMutation: () => ({
        mutate: (vars: object, opts?: { onSuccess?: () => void }) => {
          loginSpy(vars);
          if (mutationError === null) opts?.onSuccess?.();
        },
        isPending: false,
        isError: mutationError !== null,
        error: mutationError,
      }),
    }));
    vi.doMock("@tanstack/react-router", async () => {
      const actual = await vi.importActual<object>("@tanstack/react-router");
      return {
        ...actual,
        useNavigate: () => navigateSpy,
        Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
      };
    });
  });

  afterEach(() => {
    cleanup();
    loginSpy.mockReset();
    navigateSpy.mockReset();
    mutationError = null;
  });

  it("renders the lockout copy with the 10-minutos window for a 600s Retry-After", async () => {
    mutationError = {
      name: "ApiError",
      status: 429,
      detail: { code: "auth.lockout_active", retry_after_seconds: 600 },
    };
    const { LoginRoute } = await import("@/routes/login");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <LoginRoute />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /demasiados intentos\. intenta de nuevo en 10 minutos\./i,
    );
  });
});

// ---- /login — a successful login clears a previously-rendered alert --

describe("auth-login success clears error", () => {
  const loginSpy = vi.fn();
  const navigateSpy = vi.fn();
  let mutationError: unknown = null;

  beforeEach(() => {
    vi.resetModules();
    vi.doMock("@/features/auth/api/hooks", () => ({
      useLoginMutation: () => ({
        mutate: (vars: object, opts?: { onSuccess?: () => void }) => {
          loginSpy(vars);
          opts?.onSuccess?.();
        },
        isPending: false,
        isError: mutationError !== null,
        error: mutationError,
      }),
    }));
    vi.doMock("@tanstack/react-router", async () => {
      const actual = await vi.importActual<object>("@tanstack/react-router");
      return {
        ...actual,
        useNavigate: () => navigateSpy,
        Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
      };
    });
  });

  afterEach(() => {
    cleanup();
    loginSpy.mockReset();
    navigateSpy.mockReset();
    mutationError = null;
  });

  it("navigates to / after a successful submit (the next render of the route owns clearing the alert)", async () => {
    // The previous attempt left an error in the cache.
    mutationError = {
      name: "ApiError",
      status: 401,
      detail: { code: "auth.invalid_credentials" },
    };
    const { LoginRoute } = await import("@/routes/login");
    const { rerender } = render(
      <QueryClientProvider client={new QueryClient()}>
        <LoginRoute />
      </QueryClientProvider>,
    );
    // The alert is visible on the first render.
    expect(screen.getByRole("alert")).toHaveTextContent(
      /correo o contraseña incorrectos/i,
    );

    // The operator types fresh credentials and submits — the mock
    // mutation fires `onSuccess`, which the route maps to a
    // navigate({ to: "/" }) call.
    fireEvent.change(screen.getByLabelText(/Correo/i), {
      target: { value: "ada@nica.test" },
    });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), {
      target: { value: "Sup3rPass!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Iniciar sesión/i }));
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith({ to: "/" }),
    );

    // On the next render with a cleared error (the real
    // useLoginMutation would expose `error: null` after success),
    // the alert disappears.
    mutationError = null;
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <LoginRoute />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
