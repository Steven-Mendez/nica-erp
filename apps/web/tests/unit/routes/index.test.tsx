// apps/web/tests/unit/routes/index.test.tsx
// Unit test for IndexRoute: mocks useHealthz with a happy-path payload and asserts
// the Card renders the ok badge plus the version/git_sha/alembic_revision cells.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IndexRoute } from "@/routes/index";

vi.mock("@/api/healthz", () => ({
  useHealthz: () => ({
    data: {
      status: "ok",
      version: "0.1.0",
      git_sha: "abcdef0",
      db: "ok",
      alembic_revision: "0001_shared_kernel",
    },
    isLoading: false,
    isError: false,
  }),
}));

describe("IndexRoute", () => {
  it("renders the ok badge and the Alembic revision", () => {
    render(<IndexRoute />);
    expect(screen.getAllByText("ok").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("0001_shared_kernel")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("abcdef0")).toBeInTheDocument();
  });
});
