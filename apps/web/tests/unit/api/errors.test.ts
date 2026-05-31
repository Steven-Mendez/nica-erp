// apps/web/tests/unit/api/errors.test.ts
//
// Exhaustive coverage of the RFC-7807 problem-details mapper: every known
// `code` branch, the validation form-error path, and the fallbacks.

import { describe, expect, it } from "vitest";
import { mapProblemDetails, type ProblemDetail } from "@/api/errors";

const problem = (overrides: Partial<ProblemDetail>): ProblemDetail => ({
  ...overrides,
});

describe("mapProblemDetails", () => {
  describe("invalid / empty input", () => {
    it("returns generic toast when input is null", () => {
      expect(mapProblemDetails(null)).toEqual({
        kind: "toast",
        message: "Unexpected error. Please try again.",
      });
    });

    it("returns generic toast when input is undefined", () => {
      expect(mapProblemDetails(undefined)).toEqual({
        kind: "toast",
        message: "Unexpected error. Please try again.",
      });
    });

    it("returns generic toast when input has no problem-detail shape", () => {
      expect(mapProblemDetails({ foo: "bar" })).toEqual({
        kind: "toast",
        message: "Unexpected error. Please try again.",
      });
    });

    it("returns generic toast for primitive input", () => {
      expect(mapProblemDetails("boom")).toEqual({
        kind: "toast",
        message: "Unexpected error. Please try again.",
      });
    });
  });

  describe("auth.invalid_credentials", () => {
    it("returns the canonical toast message", () => {
      expect(
        mapProblemDetails(problem({ code: "auth.invalid_credentials" })),
      ).toEqual({
        kind: "toast",
        message: "Email or password is incorrect.",
      });
    });

    it("does not redirect even on 401", () => {
      const out = mapProblemDetails(
        problem({ code: "auth.invalid_credentials", status: 401 }),
      );
      expect(out.kind).toBe("toast");
    });
  });

  describe("auth.token_expired", () => {
    it("redirects to /login when status is 401", () => {
      expect(
        mapProblemDetails(
          problem({ code: "auth.token_expired", status: 401 }),
        ),
      ).toEqual({ kind: "redirect", to: "/login" });
    });

    it("falls back to toast when status is not 401", () => {
      expect(
        mapProblemDetails(
          problem({ code: "auth.token_expired", status: 403 }),
        ),
      ).toEqual({
        kind: "toast",
        message: "Your session expired. Please sign in again.",
      });
    });

    it("falls back to toast when status is missing", () => {
      expect(
        mapProblemDetails(problem({ code: "auth.token_expired" })),
      ).toEqual({
        kind: "toast",
        message: "Your session expired. Please sign in again.",
      });
    });
  });

  describe("known toast codes", () => {
    it.each([
      ["auth.lockout_active", "Too many attempts. Try again later."],
      [
        "auth.signup_email_not_confirmed",
        "Confirm your email before signing in.",
      ],
      ["validation.password_policy", "Password does not meet the policy."],
      ["email.send_failed", "We couldn't send the email. Please try again."],
      ["user.not_found", "We couldn't find that account."],
    ])("maps %s to its canonical toast", (code, message) => {
      expect(mapProblemDetails(problem({ code }))).toEqual({
        kind: "toast",
        message,
      });
    });
  });

  describe("validation.request_invalid", () => {
    it("returns form fieldErrors keyed by the last JSON-pointer segment", () => {
      expect(
        mapProblemDetails(
          problem({
            code: "validation.request_invalid",
            errors: [
              { pointer: "/email", message: "Required." },
              { pointer: "/password", message: "Too short." },
            ],
          }),
        ),
      ).toEqual({
        kind: "form",
        fieldErrors: { email: "Required.", password: "Too short." },
      });
    });

    it("keeps the first message when a pointer appears twice", () => {
      const out = mapProblemDetails(
        problem({
          code: "validation.request_invalid",
          errors: [
            { pointer: "/email", message: "first" },
            { pointer: "/email", message: "second" },
          ],
        }),
      );
      expect(out).toEqual({ kind: "form", fieldErrors: { email: "first" } });
    });

    it("handles nested pointers by taking the last segment", () => {
      expect(
        mapProblemDetails(
          problem({
            code: "validation.request_invalid",
            errors: [{ pointer: "/address/street", message: "Required." }],
          }),
        ),
      ).toEqual({
        kind: "form",
        fieldErrors: { street: "Required." },
      });
    });

    it("skips pointers with no usable segment", () => {
      expect(
        mapProblemDetails(
          problem({
            code: "validation.request_invalid",
            errors: [{ pointer: "/", message: "ignored" }],
          }),
        ),
      ).toEqual({ kind: "form", fieldErrors: {} });
    });

    it("falls back to toast when errors[] is missing", () => {
      expect(
        mapProblemDetails(problem({ code: "validation.request_invalid" })),
      ).toEqual({
        kind: "toast",
        message: "Some fields are invalid. Please review.",
      });
    });

    it("falls back to toast when errors is not an array", () => {
      expect(
        mapProblemDetails(
          problem({
            code: "validation.request_invalid",
            // @ts-expect-error: deliberate shape violation for the fallback path
            errors: { not: "an array" },
          }),
        ),
      ).toEqual({
        kind: "toast",
        message: "Some fields are invalid. Please review.",
      });
    });
  });

  describe("unknown codes", () => {
    it("uses detail when present on a wrapped (caught-error) input", () => {
      // extractDetail unwraps `input.detail` first, so the detail field has
      // to live on the inner ProblemDetail, not the outer object.
      expect(
        mapProblemDetails({
          detail: problem({
            code: "something.weird",
            detail: "Custom message.",
          }),
        }),
      ).toEqual({ kind: "toast", message: "Custom message." });
    });

    it("falls back to title when detail is missing", () => {
      expect(
        mapProblemDetails(
          problem({ code: "something.weird", title: "Weird thing happened" }),
        ),
      ).toEqual({ kind: "toast", message: "Weird thing happened" });
    });

    it("falls back to the generic 'Unexpected error.' when neither is set", () => {
      expect(
        mapProblemDetails(problem({ code: "something.weird" })),
      ).toEqual({ kind: "toast", message: "Unexpected error." });
    });
  });

  describe("wrapped input (caught error with .detail carrying the body)", () => {
    it("unwraps a caught error whose .detail is the problem body", () => {
      const caught = {
        detail: problem({
          code: "auth.invalid_credentials",
          status: 401,
        }),
      };
      expect(mapProblemDetails(caught)).toEqual({
        kind: "toast",
        message: "Email or password is incorrect.",
      });
    });

    it("uses the object itself when .detail is null", () => {
      const caught = { detail: null, code: "auth.lockout_active" };
      expect(mapProblemDetails(caught)).toEqual({
        kind: "toast",
        message: "Too many attempts. Try again later.",
      });
    });
  });

  describe("problem with only title or only detail (no code)", () => {
    it("uses detail when no code is present (wrapped)", () => {
      // Same unwrap quirk as above: pass the body through `.detail` so
      // extractDetail surfaces the inner ProblemDetail.
      expect(
        mapProblemDetails({ detail: { detail: "I am alone." } }),
      ).toEqual({ kind: "toast", message: "I am alone." });
    });

    it("uses title when neither code nor detail are present", () => {
      expect(mapProblemDetails({ title: "Just a title" })).toEqual({
        kind: "toast",
        message: "Just a title",
      });
    });
  });
});
