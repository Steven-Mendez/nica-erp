// Integration test for the cross-operator no-leak contract in section 1
// of harden-tenant-isolation-and-errors: when operator A logs out and
// operator B subsequently mounts the members hook against the same
// QueryClient, the rendered membership data MUST come from B's MSW
// response — never from A's leftover cache.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";

import { server } from "@/../tests/integration/msw/server";

vi.mock("@/features/auth/api/endpoints", () => ({
  login: vi.fn(),
  refresh: vi.fn(),
  register: vi.fn(),
  confirmSignup: vi.fn(),
  resendCode: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
  patchMe: vi.fn(),
  getMe: vi.fn(),
}));

vi.mock("@/api/tokenStore", () => ({
  setTokens: vi.fn(),
  clear: vi.fn(),
  getAccessToken: vi.fn().mockReturnValue("access-token"),
}));

import { useLogoutMutation } from "@/features/auth/api/hooks";
import { useMembersQuery, membersPageKey } from "@/features/tenants/api/hooks";
import { meQueryKey } from "@/api/queryKeys";

const TENANT_A = "11111111-1111-1111-1111-1111111111aa";
const TENANT_B = "22222222-2222-2222-2222-2222222222bb";

const operatorAMembers = {
  items: [
    {
      id: "u-a1",
      email: "alice@a.test",
      display_name: "Alice (A)",
      role: "owner",
      status: "active",
      created_at: "2026-05-29T00:00:00Z",
    },
  ],
  total: 1,
};

const operatorBMembers = {
  items: [
    {
      id: "u-b1",
      email: "bob@b.test",
      display_name: "Bob (B)",
      role: "owner",
      status: "active",
      created_at: "2026-05-29T00:00:00Z",
    },
  ],
  total: 1,
};

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

describe("cross-operator cache isolation on logout", () => {
  it("operator B's render after A's logout never sees A's member rows", async () => {
    const client = makeClient();

    // ---- Operator A is in the cache ahead of logout ----
    client.setQueryData(membersPageKey(TENANT_A, {}), operatorAMembers);
    expect(client.getQueryData(membersPageKey(TENANT_A, {}))).toEqual(operatorAMembers);

    // ---- A logs out: qc.clear() must wipe A's cached members ----
    const { result: logoutHook } = renderHook(() => useLogoutMutation(), {
      wrapper: wrapper(client),
    });
    await logoutHook.current.mutateAsync();
    expect(client.getQueryData(membersPageKey(TENANT_A, {}))).toBeUndefined();

    // ---- B logs in and renders the members hook against the same client ----
    server.use(
      http.get(`http://localhost:8000/v1/tenants/${TENANT_B}/members`, () =>
        HttpResponse.json(operatorBMembers),
      ),
      // Defensive: if anything still tries to fetch A's tenant on this
      // client, the test will fail loudly rather than silently 404.
      http.get(`http://localhost:8000/v1/tenants/${TENANT_A}/members`, () => {
        throw new Error("A's tenant must not be fetched after logout");
      }),
    );

    // Seed /v1/me cache so the stale-tenant guard
    // (`tenantId === me.active_tenant`) lets the query fire under B.
    client.setQueryData(meQueryKey, {
      id: "u-b1",
      email: "bob@b.test",
      display_name: "Bob",
      locale: "es-NI",
      timezone: "America/Managua",
      preferences: {},
      active_tenant: TENANT_B,
      role: "owner",
      permissions: [],
    });

    const { result: membersHook } = renderHook(() => useMembersQuery(TENANT_B), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(membersHook.current.data).toEqual(operatorBMembers));

    // ---- B's render shows only B's rows, never A's stale data ----
    const rendered = membersHook.current.data?.items.map((m) => m.email) ?? [];
    expect(rendered).toEqual(["bob@b.test"]);
    expect(rendered).not.toContain("alice@a.test");
  });
});
