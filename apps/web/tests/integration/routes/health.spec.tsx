// apps/web/tests/unit/routes/health.test.tsx
// Unit test for HealthRoute: mocks useHealthz with a happy-path payload and
// asserts the Card renders the ok badge plus the version / git_sha /
// alembic_revision cells.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HealthRoute } from "@/routes/health";

vi.mock("@/api/healthz", () => ({
  useHealthz: () => ({
    data: {
      status: "ok",
      version: "0.1.0",
      git_sha: "abcdef0",
      db: "ok",
      alembic_revision: "0002_identity",
    },
    isLoading: false,
    isError: false,
  }),
}));

describe("HealthRoute", () => {
  it("renders the ok badge and the Alembic revision", () => {
    render(<HealthRoute />);
    expect(screen.getAllByText("ok").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("0002_identity")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("abcdef0")).toBeInTheDocument();
  });
});
