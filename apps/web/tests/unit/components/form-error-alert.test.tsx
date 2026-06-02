// Unit tests for the FormErrorAlert component. The component is
// intentionally thin (no state, no fetch) so these tests run in the
// unit lane against the registry only — no MSW or QueryClient setup.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FormErrorAlert } from "@/components/form/form-error-alert";

describe("FormErrorAlert", () => {
  it("renders nothing when error is null", () => {
    const { container } = render(<FormErrorAlert error={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when error is undefined", () => {
    const { container } = render(<FormErrorAlert error={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the Spanish copy from the registry for an ApiError envelope", () => {
    render(
      <FormErrorAlert
        error={{
          name: "ApiError",
          status: 401,
          detail: { code: "auth.invalid_credentials" },
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos.");
  });

  it("renders the lockout copy with the retry window for 429 lockouts", () => {
    render(
      <FormErrorAlert
        error={{
          name: "ApiError",
          status: 429,
          detail: { code: "auth.lockout_active", retry_after_seconds: 600 },
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Demasiados intentos. Intenta de nuevo en 10 minutos.",
    );
  });

  it("falls back to the generic Spanish copy for unknown error shapes", () => {
    render(<FormErrorAlert error={new Error("network exploded")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ocurrió un error. Intenta de nuevo.");
  });

  it("is announced assertively to assistive tech", () => {
    render(
      <FormErrorAlert
        error={{ name: "ApiError", status: 401, detail: { code: "auth.token_expired" } }}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
  });
});
