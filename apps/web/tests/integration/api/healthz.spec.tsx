// apps/web/tests/integration/api/healthz.spec.tsx
//
// Covers `fetchHealthz` (adapter contract) and `useHealthz` (TanStack hook
// wiring). Lives under tests/integration/ because the hook test imports
// `@tanstack/react-query`, which the unit-layer layout gate forbids.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock("@/api/client", () => ({
  api: { GET: getMock },
}));

import { fetchHealthz, useHealthz, type HealthzResponse } from "@/api/healthz";

describe("fetchHealthz", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("returns the typed response when the call succeeds", async () => {
    const data: HealthzResponse = {
      status: "ok",
      version: "0.1.0",
      git_sha: "abc1234",
      db: "ok",
      alembic_revision: "head",
    };
    getMock.mockResolvedValueOnce({
      data,
      response: { status: 200 } as Response,
    });

    await expect(fetchHealthz()).resolves.toEqual(data);
    expect(getMock).toHaveBeenCalledWith("/healthz", {});
  });

  it("throws with the response status when data is undefined", async () => {
    getMock.mockResolvedValueOnce({
      data: undefined,
      response: { status: 503 } as Response,
    });

    await expect(fetchHealthz()).rejects.toThrow("/healthz failed: 503");
  });

  it("propagates a null alembic_revision unchanged", async () => {
    const data: HealthzResponse = {
      status: "ok",
      version: "dev",
      git_sha: "dev",
      db: "ok",
      alembic_revision: null,
    };
    getMock.mockResolvedValueOnce({
      data,
      response: { status: 200 } as Response,
    });

    await expect(fetchHealthz()).resolves.toMatchObject({
      alembic_revision: null,
    });
  });
});

describe("useHealthz", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("wires the TanStack query to fetchHealthz", async () => {
    const data: HealthzResponse = {
      status: "ok",
      version: "1.2.3",
      git_sha: "deadbee",
      db: "ok",
      alembic_revision: "head",
    };
    getMock.mockResolvedValueOnce({
      data,
      response: { status: 200 } as Response,
    });

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useHealthz(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(data);
    expect(getMock).toHaveBeenCalledTimes(1);
  });
});
