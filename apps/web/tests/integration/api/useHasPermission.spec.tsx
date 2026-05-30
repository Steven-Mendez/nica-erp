import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useHasPermission } from "@/api/useHasPermission";
import * as tokenStore from "@/api/tokenStore";
import { api } from "@/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useHasPermission", () => {
  it("returns false while unauthenticated (no access token)", () => {
    vi.spyOn(tokenStore, "getAccessToken").mockReturnValue(null);
    const { result } = renderHook(() => useHasPermission("members:invite"), { wrapper });
    expect(result.current).toBe(false);
  });

  it("returns true once /v1/me resolves with the requested permission", async () => {
    vi.spyOn(tokenStore, "getAccessToken").mockReturnValue("access-token");
    vi.spyOn(api, "GET").mockResolvedValue({
      data: {
        id: "u-1",
        email: "ada@nica.test",
        email_verified: true,
        display_name: "Ada",
        locale: "es-NI",
        timezone: "America/Managua",
        preferences: {},
        active_tenant: null,
        role: null,
        permissions: ["members:invite", "tenant:read"],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(() => useHasPermission("members:invite"), { wrapper });
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("returns false when the permission is absent from the resolved /v1/me payload", async () => {
    vi.spyOn(tokenStore, "getAccessToken").mockReturnValue("access-token");
    vi.spyOn(api, "GET").mockResolvedValue({
      data: {
        id: "u-1",
        email: "ada@nica.test",
        email_verified: true,
        display_name: "Ada",
        locale: "es-NI",
        timezone: "America/Managua",
        preferences: {},
        active_tenant: null,
        role: null,
        permissions: ["tenant:read"],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(() => useHasPermission("members:invite"), { wrapper });
    // Wait for any pending query to settle; expectation is stable false.
    await waitFor(() => expect(result.current).toBe(false));
  });
});
