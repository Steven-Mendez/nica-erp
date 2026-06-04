// Typed wrappers for /v1/tenants/* and /v1/invitations/*,
// sourced from the generated OpenAPI types.

import { api } from "@/api/client";
import type { components, paths } from "@/api/schema";

type Schemas = components["schemas"];
type ListMembersQuery = NonNullable<
  paths["/v1/tenants/{tenant_id}/members"]["get"]["parameters"]["query"]
>;

export type CreateTenantInput = Schemas["CreateTenantRequest"];
export type UpdateTenantInput = Schemas["UpdateTenantRequest"];
export type Tenant = Schemas["TenantResponse"];
export type MyTenants = Schemas["MyTenantsResponse"];
export type Member = Schemas["MemberResponse"];
export type MembersPage = Schemas["MembersPageResponse"];
export type MemberRole = Member["role"];
export type MemberStatus = Member["status"];
export type ListMembersSort = "joined_at" | "display_name" | "email" | "role";
export type ListMembersDir = "asc" | "desc";

export interface ListMembersParams {
  q?: string;
  roles?: MemberRole[];
  statuses?: MemberStatus[];
  sort?: ListMembersSort;
  dir?: ListMembersDir;
  limit?: number;
  offset?: number;
}
export type Invitation = Schemas["InvitationResponse"];
export type CreateInvitationInput = Schemas["CreateInvitationRequest"];
export type UpdateMemberRoleInput = Schemas["UpdateMemberRoleRequest"];
export type SwitchTenantInput = Schemas["SwitchTenantRequest"];
export type TokenBundle = Schemas["SwitchTokenResponse"];
export type AcceptInvitationResult = Schemas["AcceptInvitationResponse"];

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(label: string, status: number, detail: unknown) {
    super(`${label} failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const expectData = <T>(
  label: string,
  result: { data?: T; error?: unknown; response: Response },
): T => {
  if (result.error !== undefined) {
    throw new ApiError(label, result.response.status, result.error);
  }
  if (result.data === undefined) {
    throw new ApiError(label, result.response.status, null);
  }
  return result.data;
};

const expectVoid = (label: string, result: { error?: unknown; response: Response }): void => {
  if (result.error !== undefined) {
    throw new ApiError(label, result.response.status, result.error);
  }
};

export const createTenant = async (body: CreateTenantInput): Promise<Tenant> => {
  const result = await api.POST("/v1/tenants", { body });
  return expectData("POST /v1/tenants", result);
};

export const getMyTenants = async (): Promise<MyTenants> => {
  const result = await api.GET("/v1/tenants/me", {});
  return expectData("GET /v1/tenants/me", result);
};

export const getTenant = async (tenantId: string): Promise<Tenant> => {
  const result = await api.GET("/v1/tenants/{tenant_id}", {
    params: { path: { tenant_id: tenantId } },
  });
  return expectData(`GET /v1/tenants/${tenantId}`, result);
};

export const updateTenant = async (tenantId: string, body: UpdateTenantInput): Promise<Tenant> => {
  const result = await api.PATCH("/v1/tenants/{tenant_id}", {
    params: { path: { tenant_id: tenantId } },
    body,
  });
  return expectData(`PATCH /v1/tenants/${tenantId}`, result);
};

export const switchTenant = async (
  tenantId: string,
  body: SwitchTenantInput,
): Promise<TokenBundle> => {
  const result = await api.POST("/v1/tenants/{tenant_id}/switch", {
    params: { path: { tenant_id: tenantId } },
    body,
  });
  return expectData(`POST /v1/tenants/${tenantId}/switch`, result);
};

export const listMembers = async (
  tenantId: string,
  params: ListMembersParams = {},
): Promise<MembersPage> => {
  // The schema's query type uses `exactOptionalPropertyTypes`, so we
  // can't pass `undefined`; only include keys the caller actually set.
  const query: ListMembersQuery = {};
  if (params.limit !== undefined) query.limit = params.limit;
  if (params.offset !== undefined) query.offset = params.offset;
  if (params.q !== undefined) query.q = params.q;
  if (params.roles !== undefined) query.roles = params.roles;
  if (params.statuses !== undefined) query.statuses = params.statuses;
  if (params.sort !== undefined) query.sort = params.sort;
  if (params.dir !== undefined) query.dir = params.dir;
  const result = await api.GET("/v1/tenants/{tenant_id}/members", {
    params: { path: { tenant_id: tenantId }, query },
  });
  return expectData(`GET /v1/tenants/${tenantId}/members`, result);
};

export const updateMemberRole = async (
  tenantId: string,
  userId: string,
  body: UpdateMemberRoleInput,
): Promise<void> => {
  const result = await api.PATCH("/v1/tenants/{tenant_id}/members/{user_id}", {
    params: { path: { tenant_id: tenantId, user_id: userId } },
    body,
  });
  expectVoid(`PATCH /v1/tenants/${tenantId}/members/${userId}`, result);
};

export const removeMember = async (tenantId: string, userId: string): Promise<void> => {
  const result = await api.DELETE("/v1/tenants/{tenant_id}/members/{user_id}", {
    params: { path: { tenant_id: tenantId, user_id: userId } },
  });
  expectVoid(`DELETE /v1/tenants/${tenantId}/members/${userId}`, result);
};

export const listInvitations = async (tenantId: string): Promise<Invitation[]> => {
  const result = await api.GET("/v1/tenants/{tenant_id}/invitations", {
    params: { path: { tenant_id: tenantId } },
  });
  return expectData(`GET /v1/tenants/${tenantId}/invitations`, result);
};

export const inviteMember = async (
  tenantId: string,
  body: CreateInvitationInput,
): Promise<Invitation> => {
  const result = await api.POST("/v1/tenants/{tenant_id}/invitations", {
    params: { path: { tenant_id: tenantId } },
    body,
  });
  return expectData(`POST /v1/tenants/${tenantId}/invitations`, result);
};

export const cancelInvitation = async (tenantId: string, invitationId: string): Promise<void> => {
  const result = await api.DELETE("/v1/tenants/{tenant_id}/invitations/{invitation_id}", {
    params: { path: { tenant_id: tenantId, invitation_id: invitationId } },
  });
  expectVoid(`DELETE /v1/tenants/${tenantId}/invitations/${invitationId}`, result);
};

// `POST /v1/tenants/{id}/invitations/{invitation_id}/resend` is not in
// the OpenAPI schema yet — it landed in this change without a schema
// regen (regen requires a running backend, which the operator is the
// canonical source of). Calling it through the untyped escape hatch on
// `api` keeps the runtime path identical while the schema catches up.
export const resendInvitation = async (
  tenantId: string,
  invitationId: string,
): Promise<Invitation> => {
  const path = `/v1/tenants/${encodeURIComponent(tenantId)}/invitations/${encodeURIComponent(invitationId)}/resend`;
  // openapi-fetch exposes `client.POST(path, init)`; passing the path
  // as a string with a cast lets us reuse `fetchWithAuth` + the JSON
  // parsing without forking a manual fetch helper.
  const result = await (
    api as unknown as {
      POST: (
        url: string,
        init?: Record<string, unknown>,
      ) => Promise<{ data?: Invitation; error?: unknown; response: Response }>;
    }
  ).POST(path);
  return expectData(`POST ${path}`, result);
};

export const acceptInvitation = async (token: string): Promise<AcceptInvitationResult> => {
  // The token travels in the request body so it never appears in
  // access logs / Referer headers / browser history. The refresh
  // token rides in the `nica_erp_rt` httpOnly cookie shipped via
  // `credentials: include`; the server uses it to rotate the
  // caller's session when this is their first membership and returns
  // a non-null `tokens` field in that case.
  const result = await api.POST("/v1/invitations/accept", {
    body: { token },
  });
  return expectData("POST /v1/invitations/accept", result);
};

export type InvitationPreview = Schemas["InvitationPreviewResponse"];

export const previewInvitation = async (token: string): Promise<InvitationPreview> => {
  const result = await api.GET("/v1/invitations/{token}/preview", {
    params: { path: { token } },
  });
  return expectData(`GET /v1/invitations/${token}/preview`, result);
};
