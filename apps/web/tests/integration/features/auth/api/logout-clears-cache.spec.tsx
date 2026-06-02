// Integration test for the contract in section 1 of
// harden-tenant-isolation-and-errors: after `useLogoutMutation` settles
// the entire QueryClient cache MUST be empty — not just the `["auth",
// "me"]` key. A leaked `["tenant", …]` entry is the bug we're guarding
// against: it lets the next operator on the same browser see the
// previous operator's members table for one render before MSW refetches.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
import { tenantKey, membersKey, invitationsKey } from "@/features/tenants/api/hooks";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

describe("useLogoutMutation cache eviction", () => {
  it("leaves no cached tenant-scoped keys behind", async () => {
    const client = makeClient();
    const tenantId = "t-a";
    client.setQueryData(tenantKey(tenantId), { id: tenantId, name: "A" });
    client.setQueryData(membersKey(tenantId), {
      items: [{ id: "u-1", email: "alice@a.test" }],
      total: 1,
    });
    client.setQueryData(invitationsKey(tenantId), [{ id: "i-1", email: "bob@a.test" }]);
    expect(client.getQueryCache().getAll().length).toBeGreaterThan(0);

    const { result } = renderHook(() => useLogoutMutation(), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync();

    const remaining = client.getQueryCache().getAll();
    const tenantScoped = remaining.filter(
      (q) => Array.isArray(q.queryKey) && q.queryKey[0] === "tenant",
    );
    expect(tenantScoped).toHaveLength(0);
    expect(client.getQueryData(tenantKey(tenantId))).toBeUndefined();
    expect(client.getQueryData(membersKey(tenantId))).toBeUndefined();
    expect(client.getQueryData(invitationsKey(tenantId))).toBeUndefined();
  });
});
