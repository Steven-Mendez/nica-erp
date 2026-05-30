// Unit test for the auth two-column layout shell.
// AuthLayout is a pure render — no hooks, no I/O — so the unit lane owns it.

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AuthLayout } from "@/features/auth/components/AuthLayout";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

describe("AuthLayout", () => {
  it("renders children inside the centred column", () => {
    render(
      <AuthLayout>
        <p>contenido de prueba</p>
      </AuthLayout>,
    );
    expect(screen.getByText("contenido de prueba")).toBeInTheDocument();
  });

  it("renders the brand link pointing at the root", () => {
    render(
      <AuthLayout>
        <span>x</span>
      </AuthLayout>,
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/");
  });

  it("includes the Spanish-language brand blockquote", () => {
    render(
      <AuthLayout>
        <span>x</span>
      </AuthLayout>,
    );
    expect(screen.getByText(/Pequeñas y medianas empresas de Nicaragua/i)).toBeInTheDocument();
  });
});
