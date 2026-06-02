// TanStack Query bindings for the tenants endpoints. Query keys are
// namespaced under ["tenant", <id>, ...] so the queryClient.clear() in
// TenantSwitcher only invalidates caches once and survives a tenant swap
// without colliding keys.
//
// Every per-tenant query (`useTenantQuery`, `useMembersQuery`,
// `useInvitationsQuery`) additionally gates `enabled` on
// `tenantId === me.active_tenant`. The narrower gate (truthy id only)
// is not enough: between a `SwitchActiveTenant` and the in-flight
// /v1/me refetch there is a window where the SPA holds a stale
// tenantId — without this guard, that window can fire a request to
// the previous empresa and either leak its data into the cache or
// 403 noisily.

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
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
  type AcceptInvitationResult,
  type CreateInvitationInput,
  type CreateTenantInput,
  type Invitation,
  type ListMembersParams,
  type MembersPage,
  type MyTenants,
  type SwitchTenantInput,
  type Tenant,
  type TokenBundle,
  type UpdateMemberRoleInput,
  type UpdateTenantInput,
} from "./endpoints";
import { setTokens } from "@/api/tokenStore";
import { meQueryKey } from "@/api/queryKeys";
import { useActiveTenantId } from "@/api/useActiveTenantId";
import { setPickerConfirmed } from "@/lib/route-guard";

export const myTenantsKey = ["tenants", "me"] as const;
export const tenantKey = (id: string) => ["tenant", id] as const;
export const membersKey = (id: string) => ["tenant", id, "members"] as const;
// Each unique filter/page combination caches independently. The
// invalidation strategy in mutations targets the broader
// `membersKey(id)` prefix so every page cache refetches at once.
export const membersPageKey = (id: string, params: ListMembersParams) =>
  [...membersKey(id), params] as const;
export const invitationsKey = (id: string) => ["tenant", id, "invitations"] as const;

export const useMyTenantsQuery = (): UseQueryResult<MyTenants, Error> =>
  useQuery({ queryKey: myTenantsKey, queryFn: getMyTenants });

// All per-tenant queries gate on a truthy tenantId AND on `tenantId ===
// me.active_tenant`. Callers commonly source the id from
// `useMeQuery().data?.active_tenant`, which is `undefined` until
// `/v1/me` resolves — without the truthy check the query would hit
// `/v1/tenants//…` (note the double slash) and 404 every page refresh.
// The stricter `=== activeTenant` check additionally blocks the
// `SwitchActiveTenant` race: between the new JWT minting and the
// /v1/me refetch the caller may still hold a stale tenantId; firing
// `GET /v1/tenants/<stale>/members` against the new identity either
// leaks the old empresa's rows into the cache or 403s. Gating on the
// canonical active id is the simplest fix and falls back to "no
// request" while /v1/me is in flight.
export const useTenantQuery = (tenantId: string): UseQueryResult<Tenant, Error> => {
  const activeTenant = useActiveTenantId();
  return useQuery({
    queryKey: tenantKey(tenantId),
    queryFn: () => getTenant(tenantId),
    enabled: tenantId !== "" && tenantId === activeTenant,
  });
};

// `placeholderData: keepPreviousData` keeps the table populated while a
// refetch (e.g. switching pages, narrowing a filter) is in flight,
// instead of flashing the empty skeleton. It does *not* survive
// `queryClient.clear()` on tenant switch — that's intentional, we
// don't want to show stale rows from the wrong empresa.
export const useMembersQuery = (
  tenantId: string,
  params: ListMembersParams = {},
): UseQueryResult<MembersPage, Error> => {
  const activeTenant = useActiveTenantId();
  return useQuery({
    queryKey: membersPageKey(tenantId, params),
    queryFn: () => listMembers(tenantId, params),
    enabled: tenantId !== "" && tenantId === activeTenant,
    placeholderData: keepPreviousData,
  });
};

export const useInvitationsQuery = (tenantId: string): UseQueryResult<Invitation[], Error> => {
  const activeTenant = useActiveTenantId();
  return useQuery({
    queryKey: invitationsKey(tenantId),
    queryFn: () => listInvitations(tenantId),
    enabled: tenantId !== "" && tenantId === activeTenant,
    placeholderData: keepPreviousData,
  });
};

export const useCreateTenantMutation = (): UseMutationResult<Tenant, Error, CreateTenantInput> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTenant,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: myTenantsKey });
    },
  });
};

// Empresa-scoped update keyed on the operator's active tenant.
// The fiscal-settings editor uses this hook so it doesn't have to
// reach for the active id at every callsite. The hook reads
// `me.active_tenant` synchronously from the QueryClient cache via
// `useActiveTenantId` (the shared hook also used by the per-tenant
// queries' stale-id guard) and short-circuits if there's no active
// empresa — that state is a route-guard bug, not a save bug.
export const useUpdateActiveTenantMutation = (): UseMutationResult<
  Tenant,
  Error,
  UpdateTenantInput
> => {
  const qc = useQueryClient();
  const activeId = useActiveTenantId();
  return useMutation({
    mutationFn: async (body: UpdateTenantInput) => {
      if (activeId === null || activeId === "") {
        throw new Error("No hay empresa activa. Vuelve a /tenants.");
      }
      return updateTenant(activeId, body);
    },
    onSuccess: (tenant) => {
      if (activeId !== null && activeId !== "") {
        qc.setQueryData(tenantKey(activeId), tenant);
      }
      void qc.invalidateQueries({ queryKey: myTenantsKey });
    },
  });
};

export const useUpdateTenantMutation = (
  tenantId: string,
): UseMutationResult<Tenant, Error, UpdateTenantInput> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateTenantInput) => updateTenant(tenantId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: tenantKey(tenantId) });
    },
  });
};

export const useInviteMemberMutation = (
  tenantId: string,
): UseMutationResult<Invitation, Error, CreateInvitationInput> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateInvitationInput) => inviteMember(tenantId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: invitationsKey(tenantId) });
    },
  });
};

export const useRemoveMemberMutation = (
  tenantId: string,
): UseMutationResult<void, Error, { userId: string }> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId }) => removeMember(tenantId, userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: membersKey(tenantId) });
    },
  });
};

export const useUpdateMemberRoleMutation = (
  tenantId: string,
): UseMutationResult<void, Error, { userId: string; role: UpdateMemberRoleInput["role"] }> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }) => updateMemberRole(tenantId, userId, { role }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: membersKey(tenantId) });
    },
  });
};

export const useCancelInvitationMutation = (
  tenantId: string,
): UseMutationResult<void, Error, { invitationId: string }> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ invitationId }) => cancelInvitation(tenantId, invitationId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: invitationsKey(tenantId) });
    },
  });
};

export const useAcceptInvitationMutation = (): UseMutationResult<
  AcceptInvitationResult,
  Error,
  string
> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => acceptInvitation(token),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: myTenantsKey });
    },
  });
};

export const useSwitchTenantMutation = (): UseMutationResult<
  TokenBundle,
  Error,
  { tenantId: string; input: SwitchTenantInput }
> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tenantId, input }) => switchTenant(tenantId, input),
    onSuccess: (bundle) => {
      setTokens({
        access: bundle.access_token,
        refresh: bundle.refresh_token,
        id: bundle.id_token,
      });
      // The successful switch is the canonical "operator picked an
      // empresa" signal; flip the picker-confirmed flag so the route
      // guard stops bouncing them back to /tenants.
      setPickerConfirmed();
      // Tenant swap invalidates everything: query keys are namespaced per
      // tenant but the safer reset wipes the in-flight caches in one shot.
      qc.clear();
      void qc.invalidateQueries({ queryKey: meQueryKey });
    },
  });
};
