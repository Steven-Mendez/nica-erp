// Typed wrappers for /v1/tenants/* and /v1/invitations/*,
// sourced from the generated OpenAPI types.

import { api } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type CreateTenantInput = Schemas["CreateTenantRequest"];
export type UpdateTenantInput = Schemas["UpdateTenantRequest"];
export type Tenant = Schemas["TenantResponse"];
export type MyTenants = Schemas["MyTenantsResponse"];
export type Member = Schemas["MemberResponse"];
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

export const listMembers = async (tenantId: string): Promise<Member[]> => {
  const result = await api.GET("/v1/tenants/{tenant_id}/members", {
    params: { path: { tenant_id: tenantId } },
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

export const acceptInvitation = async (token: string): Promise<AcceptInvitationResult> => {
  // Per ADR-0031 the token travels in the request body so it never
  // appears in access logs / Referer headers / browser history.
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
