// TanStack Query bindings for the tenants endpoints. Query keys are
// namespaced under ["tenant", <id>, ...] so the queryClient.clear() in
// TenantSwitcher only invalidates caches once and survives a tenant swap
// without colliding keys.

import {
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
  type Member,
  type MyTenants,
  type SwitchTenantInput,
  type Tenant,
  type TokenBundle,
  type UpdateMemberRoleInput,
  type UpdateTenantInput,
} from "./endpoints";
import { setTokens } from "@/api/tokenStore";
import { meQueryKey } from "@/api/queryKeys";
import { setPickerConfirmed } from "@/lib/route-guard";

export const myTenantsKey = ["tenants", "me"] as const;
export const tenantKey = (id: string) => ["tenant", id] as const;
export const membersKey = (id: string) => ["tenant", id, "members"] as const;
export const invitationsKey = (id: string) => ["tenant", id, "invitations"] as const;

export const useMyTenantsQuery = (): UseQueryResult<MyTenants, Error> =>
  useQuery({ queryKey: myTenantsKey, queryFn: getMyTenants });

export const useTenantQuery = (tenantId: string): UseQueryResult<Tenant, Error> =>
  useQuery({ queryKey: tenantKey(tenantId), queryFn: () => getTenant(tenantId) });

export const useMembersQuery = (tenantId: string): UseQueryResult<Member[], Error> =>
  useQuery({ queryKey: membersKey(tenantId), queryFn: () => listMembers(tenantId) });

export const useInvitationsQuery = (tenantId: string): UseQueryResult<Invitation[], Error> =>
  useQuery({
    queryKey: invitationsKey(tenantId),
    queryFn: () => listInvitations(tenantId),
  });

export const useCreateTenantMutation = (): UseMutationResult<Tenant, Error, CreateTenantInput> => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTenant,
    onSuccess: () => {
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
    mutationFn: acceptInvitation,
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
