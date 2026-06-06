// apps/web/src/api/errors.ts
//
// RFC-7807 problem-details mapper. Single entry point so every feature
// surfaces backend errors the same way.
//
// The backend ships codes like `auth.invalid_credentials`,
// `auth.token_expired`, `auth.lockout_active`, `auth.signup_email_not_confirmed`,
// `validation.request_invalid`, `validation.password_policy`, `email.send_failed`,
// `user.not_found`. The mapper maps each to a user-facing message plus an
// outcome (toast | form | redirect | silent) so the route only has to render
// the message; the navigation / toast wiring is centralised here.
//
// `messageForProblem` is the inline-display sibling: it turns a parsed
// `ProblemDetail` into the user-facing Spanish copy used by
// `<FormErrorAlert>` and direct callers. It NEVER renders the raw
// English code — unknown codes fall through to a generic copy.

export interface ProblemDetail {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  retry_after_seconds?: number;
  scope?: "identifier" | "ip" | "none";
  errors?: Array<{ pointer: string; message: string }>;
}

export type ProblemOutcome =
  | { kind: "toast"; message: string }
  | { kind: "form"; fieldErrors: Record<string, string> }
  | { kind: "redirect"; to: "/login" }
  | { kind: "silent"; reason: string };

const MESSAGES: Record<string, string> = {
  "auth.invalid_credentials": "Email or password is incorrect.",
  "auth.token_expired": "Your session expired. Please sign in again.",
  "auth.signup_email_not_confirmed": "Confirm your email before signing in.",
  "auth.lockout_active": "Too many attempts. Try again later.",
  "validation.request_invalid": "Some fields are invalid. Please review.",
  "validation.password_policy": "Password does not meet the policy.",
  "email.send_failed": "We couldn't send the email. Please try again.",
  "user.not_found": "We couldn't find that account.",
};

const isProblemDetail = (value: unknown): value is ProblemDetail => {
  return (
    typeof value === "object" &&
    value !== null &&
    ("code" in value || "title" in value || "detail" in value)
  );
};

/**
 * Parse a fetch failure (the body the server returned with
 * `Content-Type: application/problem+json`) and decide the SPA outcome.
 *
 * Pass either a raw caught error (with `.detail` carrying the parsed body),
 * or the parsed body directly.
 */
export const mapProblemDetails = (input: unknown): ProblemOutcome => {
  const detail = extractDetail(input);

  if (!isProblemDetail(detail)) {
    return { kind: "toast", message: "Unexpected error. Please try again." };
  }

  const code = detail.code;

  if (code === "auth.invalid_credentials" || code === "auth.token_expired") {
    return detail.status === 401 && code === "auth.token_expired"
      ? { kind: "redirect", to: "/login" }
      : { kind: "toast", message: MESSAGES[code] ?? "Authentication failed." };
  }

  if (code === "validation.request_invalid" && Array.isArray(detail.errors)) {
    const fieldErrors: Record<string, string> = {};
    for (const issue of detail.errors) {
      // pointer is JSON Pointer ("/email", "/password"). The field name is the
      // last non-empty segment.
      const segments = issue.pointer.split("/").filter((s) => s.length > 0);
      const field = segments[segments.length - 1];
      if (field !== undefined && fieldErrors[field] === undefined) {
        fieldErrors[field] = issue.message;
      }
    }
    return { kind: "form", fieldErrors };
  }

  if (code !== undefined && MESSAGES[code] !== undefined) {
    return { kind: "toast", message: MESSAGES[code] };
  }

  return {
    kind: "toast",
    message: detail.detail ?? detail.title ?? "Unexpected error.",
  };
};

const extractDetail = (input: unknown): unknown => {
  if (input === null || input === undefined) return null;
  if (typeof input === "object" && "detail" in input) {
    return (input as { detail: unknown }).detail ?? input;
  }
  return input;
};

// ---------------------------------------------------------------------
// Inline-display registry (Spanish copy).
// ---------------------------------------------------------------------

const GENERIC_FALLBACK = "Ocurrió un error. Intenta de nuevo.";

/**
 * Render the lockout copy with the `Retry-After` window rounded up to
 * the nearest minute (with a 1-minute floor). 600s → "10 minutos",
 * 125s → "3 minutos", anything < 60s → "1 minuto".
 */
export const formatLockoutMinutes = (retryAfterSeconds: number | undefined): string => {
  const seconds = retryAfterSeconds && retryAfterSeconds > 0 ? retryAfterSeconds : 60;
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  return minutes === 1 ? "1 minuto" : `${minutes} minutos`;
};

const SPANISH_BY_CODE: Record<string, (p: ProblemDetail) => string> = {
  "auth.invalid_credentials": () => "Correo o contraseña incorrectos.",
  "auth.lockout_active": (p) =>
    `Demasiados intentos. Intenta de nuevo en ${formatLockoutMinutes(p.retry_after_seconds)}.`,
  "auth.invalid_confirmation_code": () => "Código incorrecto o expirado. Solicita uno nuevo.",
  "auth.signup_email_not_confirmed": () => "Confirma tu correo antes de iniciar sesión.",
  "auth.token_expired": () => "Tu sesión expiró. Inicia sesión de nuevo.",
  "auth.reset_token_used": () => "Este enlace ya fue utilizado. Solicita uno nuevo.",
  "auth.reset_token_expired": () => "El enlace expiró. Solicita uno nuevo.",
  "auth.resend_throttled": () => "Espera unos segundos antes de pedir otro código.",
  "auth.rate_limited": (p) => {
    const n = p.retry_after_seconds;
    if (typeof n === "number" && n > 0) {
      return `Demasiados intentos. Intenta de nuevo en ${n} segundos.`;
    }
    return "Demasiados intentos. Espera unos segundos antes de reintentar.";
  },
  "auth.weak_password": () =>
    "La contraseña no cumple la política: 12+ caracteres con mayúscula, minúscula, dígito y símbolo.",
  // Tenants — invitation conflicts. The backend does not emit this
  // exact code today (the invite-member use case writes a new
  // invitation row on every call); the entry is forward-compatible
  // so an MSW-mocked 409 in the integration test, and an eventual
  // backend handler, both hit the same Spanish copy.
  "tenants.invitation_duplicate_pending": () => "Esta persona ya tiene una invitación pendiente.",
  "invitation.identity_mismatch": () =>
    "Esta invitación es para otra persona. Cierra sesión y entra con el correo invitado.",
  "invitation.expired": () =>
    "Esta invitación expiró. Pide a quien te invitó que envíe una nueva.",
  "invitation.already_accepted": () =>
    "Esta invitación ya fue aceptada. Inicia sesión para continuar.",
  "invitation.cancelled": () =>
    "Esta invitación fue cancelada. Pide a quien te invitó que envíe una nueva.",
  "invitation.invalid": () => "Este enlace de invitación no es válido.",
  "invitation.not_found": () =>
    "No encontramos esta invitación. Verifica el enlace con quien te invitó.",
};

/**
 * Translate an `ApiError`'s parsed problem body (or anything shaped
 * like a `ProblemDetail`) into the user-facing Spanish copy used by
 * `<FormErrorAlert>`. Anything not recognised falls through to the
 * generic copy; the raw backend code is never surfaced to the user.
 */
export const messageForProblem = (input: unknown): string => {
  const detail = extractDetail(input);
  if (!isProblemDetail(detail)) {
    return GENERIC_FALLBACK;
  }
  if (detail.code !== undefined) {
    const formatter = SPANISH_BY_CODE[detail.code];
    if (formatter !== undefined) {
      return formatter(detail);
    }
  }
  return GENERIC_FALLBACK;
};

/**
 * Auth codes the registry recognises. Used by the unit test that
 * asserts every code emitted by the auth router has a Spanish
 * entry. Tenant + other-context codes also live in
 * ``SPANISH_BY_CODE`` but are listed separately so a registry
 * change in one context does not silently extend the auth catalog.
 */
export const KNOWN_AUTH_PROBLEM_CODES: readonly string[] = Object.freeze([
  "auth.invalid_credentials",
  "auth.lockout_active",
  "auth.invalid_confirmation_code",
  "auth.signup_email_not_confirmed",
  "auth.token_expired",
  "auth.reset_token_used",
  "auth.reset_token_expired",
  "auth.resend_throttled",
  "auth.rate_limited",
]);
