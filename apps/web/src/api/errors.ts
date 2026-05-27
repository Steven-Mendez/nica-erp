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

export interface ProblemDetail {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  retry_after_seconds?: number;
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
