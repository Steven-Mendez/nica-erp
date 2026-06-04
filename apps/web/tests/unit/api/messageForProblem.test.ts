// Unit tests for the auth problem-code Spanish copy registry and the
// lockout-Retry-After templating utility. The registry is exercised
// scenario-by-scenario per the frontend-auth-error-feedback spec.

import { describe, expect, it } from "vitest";
import {
  formatLockoutMinutes,
  KNOWN_AUTH_PROBLEM_CODES,
  messageForProblem,
  type ProblemDetail,
} from "@/api/errors";

const problem = (overrides: Partial<ProblemDetail>): ProblemDetail => ({
  ...overrides,
});

describe("formatLockoutMinutes", () => {
  it("rounds 600 seconds up to 10 minutos", () => {
    expect(formatLockoutMinutes(600)).toBe("10 minutos");
  });

  it("rounds 125 seconds up to 3 minutos", () => {
    expect(formatLockoutMinutes(125)).toBe("3 minutos");
  });

  it("floors at 1 minuto for under-60-second windows", () => {
    expect(formatLockoutMinutes(30)).toBe("1 minuto");
  });

  it("treats undefined retry-after as 1 minuto", () => {
    expect(formatLockoutMinutes(undefined)).toBe("1 minuto");
  });

  it("treats zero or negative retry-after as 1 minuto", () => {
    expect(formatLockoutMinutes(0)).toBe("1 minuto");
    expect(formatLockoutMinutes(-30)).toBe("1 minuto");
  });

  it("pluralises 2 minutos correctly", () => {
    expect(formatLockoutMinutes(90)).toBe("2 minutos");
  });
});

describe("messageForProblem", () => {
  it("renders auth.invalid_credentials in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.invalid_credentials" }))).toBe(
      "Correo o contraseña incorrectos.",
    );
  });

  it("renders auth.invalid_confirmation_code in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.invalid_confirmation_code" }))).toBe(
      "Código incorrecto o expirado. Solicita uno nuevo.",
    );
  });

  it("renders auth.signup_email_not_confirmed in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.signup_email_not_confirmed" }))).toBe(
      "Confirma tu correo antes de iniciar sesión.",
    );
  });

  it("renders auth.token_expired in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.token_expired" }))).toBe(
      "Tu sesión expiró. Inicia sesión de nuevo.",
    );
  });

  it("renders auth.reset_token_used in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.reset_token_used" }))).toBe(
      "Este enlace ya fue utilizado. Solicita uno nuevo.",
    );
  });

  it("renders auth.reset_token_expired in Spanish", () => {
    expect(messageForProblem(problem({ code: "auth.reset_token_expired" }))).toBe(
      "El enlace expiró. Solicita uno nuevo.",
    );
  });

  it("renders auth.resend_throttled in Spanish", () => {
    expect(
      messageForProblem(
        problem({ code: "auth.resend_throttled", status: 429, retry_after_seconds: 30 }),
      ),
    ).toBe("Espera unos segundos antes de pedir otro código.");
  });

  it("renders auth.rate_limited with the retry seconds interpolated", () => {
    expect(
      messageForProblem(
        problem({ code: "auth.rate_limited", status: 429, retry_after_seconds: 12 }),
      ),
    ).toBe("Demasiados intentos. Intenta de nuevo en 12 segundos.");
  });

  it("falls back to a generic auth.rate_limited copy when retry_after_seconds is missing", () => {
    expect(messageForProblem(problem({ code: "auth.rate_limited", status: 429 }))).toBe(
      "Demasiados intentos. Espera unos segundos antes de reintentar.",
    );
  });

  it("formats auth.lockout_active with the retry window in minutos", () => {
    expect(
      messageForProblem(problem({ code: "auth.lockout_active", retry_after_seconds: 600 })),
    ).toBe("Demasiados intentos. Intenta de nuevo en 10 minutos.");
  });

  it("rounds 125-second lockout window up to 3 minutos", () => {
    expect(
      messageForProblem(problem({ code: "auth.lockout_active", retry_after_seconds: 125 })),
    ).toBe("Demasiados intentos. Intenta de nuevo en 3 minutos.");
  });

  it("falls back to the generic Spanish copy for unknown codes", () => {
    expect(messageForProblem(problem({ code: "totally.made.up" }))).toBe(
      "Ocurrió un error. Intenta de nuevo.",
    );
  });

  it("falls back to the generic copy for non-problem inputs", () => {
    expect(messageForProblem(null)).toBe("Ocurrió un error. Intenta de nuevo.");
    expect(messageForProblem(undefined)).toBe("Ocurrió un error. Intenta de nuevo.");
    expect(messageForProblem({ foo: "bar" })).toBe("Ocurrió un error. Intenta de nuevo.");
  });

  it("unwraps an ApiError-shaped { detail: ProblemDetail } envelope", () => {
    expect(
      messageForProblem({
        name: "ApiError",
        status: 401,
        detail: { code: "auth.invalid_credentials" } satisfies ProblemDetail,
      }),
    ).toBe("Correo o contraseña incorrectos.");
  });
});

describe("KNOWN_AUTH_PROBLEM_CODES", () => {
  it("contains the codes documented in the spec", () => {
    expect(new Set(KNOWN_AUTH_PROBLEM_CODES)).toEqual(
      new Set([
        "auth.invalid_credentials",
        "auth.lockout_active",
        "auth.invalid_confirmation_code",
        "auth.signup_email_not_confirmed",
        "auth.token_expired",
        "auth.reset_token_used",
        "auth.reset_token_expired",
        "auth.resend_throttled",
        "auth.rate_limited",
      ]),
    );
  });
});
