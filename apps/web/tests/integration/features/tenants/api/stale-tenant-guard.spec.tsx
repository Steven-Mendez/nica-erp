// Integration test for the stale-tenant guard in section 2 of
// harden-tenant-isolation-and-errors. When `me.active_tenant` changes
// mid-render, a per-tenant query that was mounted against the old id
// MUST NOT fire a request — the gate `tenantId === activeTenant`
// disables it the next render cycle. Without this guard,
// `GET /v1/tenants/<stale>/members` would either leak the prior
// empresa's data into the cache or 403 noisily.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/features/tenants/api/endpoints", async () => {
  const actual = await vi.importActual<object>("@/features/tenants/api/endpoints");
  return {
    ...actual,
    listMembers: vi.fn(),
  };
});

vi.mock("@/api/tokenStore", () => ({
  setTokens: vi.fn(),
  getAccessToken: vi.fn().mockReturnValue("access-token"),
}));

import { listMembers } from "@/features/tenants/api/endpoints";
import { useMembersQuery } from "@/features/tenants/api/hooks";
import { meQueryKey } from "@/api/queryKeys";

const TENANT_OLD = "00000000-0000-0000-0000-0000000000aa";
const TENANT_NEW = "00000000-0000-0000-0000-0000000000bb";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function seedMe(client: QueryClient, activeTenant: string | null): void {
  client.setQueryData(meQueryKey, {
    id: "u-1",
    email: "ada@nica.test",
    display_name: "Ada",
    locale: "es-NI",
    timezone: "America/Managua",
    preferences: {},
    active_tenant: activeTenant,
    role: activeTenant !== null ? "owner" : null,
    permissions: [],
  });
}

describe("stale-tenant guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not fire a request when me.active_tenant flips to a different id mid-render", async () => {
    vi.mocked(listMembers).mockResolvedValue({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    });

    const client = makeClient();
    // Start with the operator pointed at the NEW empresa, but render
    // useMembersQuery against the OLD one — simulating a component
    // that captured the old id before the SwitchActiveTenant resolved.
    seedMe(client, TENANT_NEW);

    const { result } = renderHook(() => useMembersQuery(TENANT_OLD), {
      wrapper: wrapper(client),
    });

    // Give TanStack Query a microtask + a beat to attempt any fetch.
    await new Promise((r) => setTimeout(r, 50));
    expect(vi.mocked(listMembers)).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
  });

  it("fires the request when tenantId matches the active id", async () => {
    vi.mocked(listMembers).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    });
    const client = makeClient();
    seedMe(client, TENANT_NEW);

    renderHook(() => useMembersQuery(TENANT_NEW), { wrapper: wrapper(client) });
    await waitFor(() => expect(vi.mocked(listMembers)).toHaveBeenCalledTimes(1));
  });

  it("stays disabled when me.active_tenant is null (operator still on the picker)", async () => {
    vi.mocked(listMembers).mockResolvedValue({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    } as Awaited<ReturnType<typeof listMembers>>);
    const client = makeClient();
    seedMe(client, null);

    renderHook(() => useMembersQuery(TENANT_OLD), { wrapper: wrapper(client) });
    await new Promise((r) => setTimeout(r, 50));
    expect(vi.mocked(listMembers)).not.toHaveBeenCalled();
  });
});
