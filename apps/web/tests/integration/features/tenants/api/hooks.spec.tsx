// Unit tests for the tenants TanStack Query hooks. Stubs
// `./endpoints` so each hook is exercised in isolation; the focus
// is on the side-effect logic (queryClient.invalidate / setQueryData,
// setTokens on switch, setPickerConfirmed flag flip).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/features/tenants/api/endpoints", async () => {
  const actual = await vi.importActual<object>("@/features/tenants/api/endpoints");
  return {
    ...actual,
    getMyTenants: vi.fn(),
    getTenant: vi.fn(),
    listMembers: vi.fn(),
    listInvitations: vi.fn(),
    createTenant: vi.fn(),
    updateTenant: vi.fn(),
    inviteMember: vi.fn(),
    cancelInvitation: vi.fn(),
    removeMember: vi.fn(),
    updateMemberRole: vi.fn(),
    acceptInvitation: vi.fn(),
    switchTenant: vi.fn(),
  };
});

vi.mock("@/api/tokenStore", () => ({
  setTokens: vi.fn(),
}));

import {
  acceptInvitation,
  cancelInvitation,
  createTenant,
  getMyTenants,
  getTenant,
  inviteMember,
  listInvitations,
  listMembers,
  removeMember,
  switchTenant,
  updateMemberRole,
  updateTenant,
} from "@/features/tenants/api/endpoints";
import {
  invitationsKey,
  membersKey,
  myTenantsKey,
  tenantKey,
  useAcceptInvitationMutation,
  useCancelInvitationMutation,
  useCreateTenantMutation,
  useInviteMemberMutation,
  useInvitationsQuery,
  useMembersQuery,
  useMyTenantsQuery,
  useRemoveMemberMutation,
  useSwitchTenantMutation,
  useTenantQuery,
  useUpdateMemberRoleMutation,
  useUpdateTenantMutation,
} from "@/features/tenants/api/hooks";
import { setTokens } from "@/api/tokenStore";
import { PICKER_FLAG_KEY } from "@/lib/route-guard";

const tenantId = "00000000-0000-0000-0000-0000000000aa";

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

afterEach(() => {
  vi.clearAllMocks();
});

describe("query key shape", () => {
  it("namespaces per-tenant keys by tenantId", () => {
    expect(myTenantsKey).toEqual(["tenants", "me"]);
    expect(tenantKey(tenantId)).toEqual(["tenant", tenantId]);
    expect(membersKey(tenantId)).toEqual(["tenant", tenantId, "members"]);
    expect(invitationsKey(tenantId)).toEqual(["tenant", tenantId, "invitations"]);
  });
});

describe("queries", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useMyTenantsQuery calls getMyTenants and resolves with the payload", async () => {
    const payload = { items: [] };
    vi.mocked(getMyTenants).mockResolvedValueOnce(payload);
    const client = makeClient();
    const { result } = renderHook(() => useMyTenantsQuery(), { wrapper: wrapper(client) });
    await waitFor(() => expect(result.current.data).toEqual(payload));
  });

  it("useTenantQuery passes the tenantId to getTenant", async () => {
    vi.mocked(getTenant).mockResolvedValueOnce({ id: tenantId } as Awaited<
      ReturnType<typeof getTenant>
    >);
    const client = makeClient();
    const { result } = renderHook(() => useTenantQuery(tenantId), { wrapper: wrapper(client) });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(vi.mocked(getTenant).mock.calls[0]).toEqual([tenantId]);
  });

  it("useMembersQuery scopes to tenantId and forwards params", async () => {
    vi.mocked(listMembers).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    });
    const client = makeClient();
    const params = { limit: 10, offset: 0, q: "ada" } as const;
    renderHook(() => useMembersQuery(tenantId, params), { wrapper: wrapper(client) });
    await waitFor(() => expect(vi.mocked(listMembers).mock.calls.length).toBe(1));
    expect(vi.mocked(listMembers).mock.calls[0]).toEqual([tenantId, params]);
  });

  it("useInvitationsQuery scopes to tenantId", async () => {
    vi.mocked(listInvitations).mockResolvedValueOnce([]);
    const client = makeClient();
    renderHook(() => useInvitationsQuery(tenantId), { wrapper: wrapper(client) });
    await waitFor(() => expect(vi.mocked(listInvitations).mock.calls.length).toBe(1));
    expect(vi.mocked(listInvitations).mock.calls[0]).toEqual([tenantId]);
  });
});

describe("mutations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useCreateTenantMutation invalidates myTenantsKey on success", async () => {
    vi.mocked(createTenant).mockResolvedValueOnce({ id: tenantId } as Awaited<
      ReturnType<typeof createTenant>
    >);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateTenantMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ name: "Acme", is_withholder: false });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: myTenantsKey });
  });

  it("useUpdateTenantMutation invalidates tenantKey on success", async () => {
    vi.mocked(updateTenant).mockResolvedValueOnce({ id: tenantId } as Awaited<
      ReturnType<typeof updateTenant>
    >);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useUpdateTenantMutation(tenantId), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ name: "Acme 2" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: tenantKey(tenantId) });
  });

  it("useInviteMemberMutation invalidates invitationsKey on success", async () => {
    vi.mocked(inviteMember).mockResolvedValueOnce({} as Awaited<ReturnType<typeof inviteMember>>);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useInviteMemberMutation(tenantId), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ email: "x@y.com", proposed_role: "viewer" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: invitationsKey(tenantId) });
  });

  it("useCancelInvitationMutation invalidates invitationsKey on success", async () => {
    vi.mocked(cancelInvitation).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCancelInvitationMutation(tenantId), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ invitationId: "i-1" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: invitationsKey(tenantId) });
  });

  it("useRemoveMemberMutation invalidates membersKey on success", async () => {
    vi.mocked(removeMember).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useRemoveMemberMutation(tenantId), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ userId: "u-1" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: membersKey(tenantId) });
  });

  it("useUpdateMemberRoleMutation invalidates membersKey on success", async () => {
    vi.mocked(updateMemberRole).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useUpdateMemberRoleMutation(tenantId), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ userId: "u-1", role: "viewer" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: membersKey(tenantId) });
  });

  it("useAcceptInvitationMutation invalidates myTenantsKey on success", async () => {
    vi.mocked(acceptInvitation).mockResolvedValueOnce(
      {} as Awaited<ReturnType<typeof acceptInvitation>>,
    );
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useAcceptInvitationMutation(), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync("token-1");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: myTenantsKey });
  });

  it("useSwitchTenantMutation sets tokens, flips the picker flag, and clears the cache", async () => {
    vi.mocked(switchTenant).mockResolvedValueOnce({
      access_token: "a",
      refresh_token: "r",
      id_token: "i",
    } as Awaited<ReturnType<typeof switchTenant>>);
    const client = makeClient();
    const clearSpy = vi.spyOn(client, "clear");
    window.sessionStorage.removeItem(PICKER_FLAG_KEY);
    const { result } = renderHook(() => useSwitchTenantMutation(), {
      wrapper: wrapper(client),
    });
    await result.current.mutateAsync({ tenantId, input: { refresh_token: "r-in" } });
    expect(setTokens).toHaveBeenCalledWith({ access: "a", refresh: "r", id: "i" });
    expect(window.sessionStorage.getItem(PICKER_FLAG_KEY)).toBe("1");
    expect(clearSpy).toHaveBeenCalled();
  });
});
