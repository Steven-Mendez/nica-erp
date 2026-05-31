// apps/web/tests/unit/features/tenants/api/endpoints.test.ts
//
// Pins every tenants/invitations endpoint's URL, params, and body wiring,
// plus the shared ApiError / expectData / expectVoid helpers. Integration
// tests for the hooks only ever drive the happy path of a subset.

import { beforeEach, describe, expect, it, vi } from "vitest";

const { postMock, getMock, patchMock, deleteMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  api: {
    POST: postMock,
    GET: getMock,
    PATCH: patchMock,
    DELETE: deleteMock,
  },
}));

import {
  acceptInvitation,
  ApiError,
  cancelInvitation,
  createTenant,
  getMyTenants,
  getTenant,
  inviteMember,
  listInvitations,
  listMembers,
  previewInvitation,
  removeMember,
  switchTenant,
  updateMemberRole,
  updateTenant,
} from "@/features/tenants/api/endpoints";

const TENANT_ID = "t-1";
const USER_ID = "u-1";
const INVITATION_ID = "inv-1";

const ok = <T>(data: T, status = 200) => ({
  data,
  response: { status } as Response,
});

const fail = (status: number, errorBody: unknown) => ({
  error: errorBody,
  response: { status } as Response,
});

const undef = (status: number) => ({
  data: undefined,
  response: { status } as Response,
});

const tenant = {
  tenant_id: TENANT_ID,
  name: "Mi Empresa",
  ruc: null,
  regime: "general",
  municipality: "Managua",
  fiscal_address: null,
  is_withholder: false,
  authorization_dgi: null,
};

beforeEach(() => {
  postMock.mockReset();
  getMock.mockReset();
  patchMock.mockReset();
  deleteMock.mockReset();
});

describe("ApiError", () => {
  it("formats message and exposes status + detail", () => {
    const err = new ApiError("POST /v1/tenants", 422, {
      code: "validation.request_invalid",
    });
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ApiError");
    expect(err.message).toBe("POST /v1/tenants failed: 422");
    expect(err.status).toBe(422);
    expect(err.detail).toEqual({ code: "validation.request_invalid" });
  });
});

describe("tenant endpoints — happy paths", () => {
  it("createTenant POSTs /v1/tenants with the body", async () => {
    postMock.mockResolvedValueOnce(ok(tenant, 201));
    await expect(createTenant({ name: "Mi Empresa", is_withholder: false })).resolves.toEqual(
      tenant,
    );
    expect(postMock).toHaveBeenCalledWith("/v1/tenants", {
      body: { name: "Mi Empresa", is_withholder: false },
    });
  });

  it("getMyTenants GETs /v1/tenants/me", async () => {
    const payload = { tenants: [tenant], active_tenant_id: TENANT_ID };
    getMock.mockResolvedValueOnce(ok(payload));
    await expect(getMyTenants()).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith("/v1/tenants/me", {});
  });

  it("getTenant GETs /v1/tenants/{tenant_id}", async () => {
    getMock.mockResolvedValueOnce(ok(tenant));
    await expect(getTenant(TENANT_ID)).resolves.toEqual(tenant);
    expect(getMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}", {
      params: { path: { tenant_id: TENANT_ID } },
    });
  });

  it("updateTenant PATCHes /v1/tenants/{tenant_id} with body", async () => {
    patchMock.mockResolvedValueOnce(ok({ ...tenant, name: "Otro" }));
    await expect(updateTenant(TENANT_ID, { name: "Otro" })).resolves.toMatchObject({
      name: "Otro",
    });
    expect(patchMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}", {
      params: { path: { tenant_id: TENANT_ID } },
      body: { name: "Otro" },
    });
  });

  it("switchTenant POSTs /v1/tenants/{tenant_id}/switch with refresh token", async () => {
    const bundle = {
      access_token: "at",
      refresh_token: "rt",
      id_token: "it",
      token_type: "Bearer",
      expires_in: 3600,
    };
    postMock.mockResolvedValueOnce(ok(bundle));
    await expect(switchTenant(TENANT_ID, { refresh_token: "rt-in" })).resolves.toEqual(bundle);
    expect(postMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/switch", {
      params: { path: { tenant_id: TENANT_ID } },
      body: { refresh_token: "rt-in" },
    });
  });
});

describe("member endpoints", () => {
  it("listMembers GETs the paginated members envelope with no params by default", async () => {
    const page = {
      items: [{ user_id: USER_ID, email: "a@b.test", role: "admin" as const }],
      total: 1,
      limit: 25,
      offset: 0,
    };
    getMock.mockResolvedValueOnce(ok(page));
    await expect(listMembers(TENANT_ID)).resolves.toEqual(page);
    expect(getMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/members", {
      params: { path: { tenant_id: TENANT_ID }, query: {} },
    });
  });

  it("listMembers forwards only the params the caller set", async () => {
    const page = { items: [], total: 0, limit: 10, offset: 20 };
    getMock.mockResolvedValueOnce(ok(page));
    await listMembers(TENANT_ID, {
      limit: 10,
      offset: 20,
      q: "ada",
      roles: ["admin"],
      sort: "display_name",
      dir: "desc",
    });
    expect(getMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/members", {
      params: {
        path: { tenant_id: TENANT_ID },
        query: {
          limit: 10,
          offset: 20,
          q: "ada",
          roles: ["admin"],
          sort: "display_name",
          dir: "desc",
        },
      },
    });
  });

  it("updateMemberRole PATCHes a single member", async () => {
    patchMock.mockResolvedValueOnce(ok({}, 204));
    await expect(
      updateMemberRole(TENANT_ID, USER_ID, { role: "accountant" }),
    ).resolves.toBeUndefined();
    expect(patchMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/members/{user_id}", {
      params: { path: { tenant_id: TENANT_ID, user_id: USER_ID } },
      body: { role: "accountant" },
    });
  });

  it("removeMember DELETEs a single member", async () => {
    deleteMock.mockResolvedValueOnce(ok({}, 204));
    await expect(removeMember(TENANT_ID, USER_ID)).resolves.toBeUndefined();
    expect(deleteMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/members/{user_id}", {
      params: { path: { tenant_id: TENANT_ID, user_id: USER_ID } },
    });
  });
});

describe("invitation endpoints", () => {
  it("listInvitations GETs the invitations collection", async () => {
    getMock.mockResolvedValueOnce(ok([]));
    await expect(listInvitations(TENANT_ID)).resolves.toEqual([]);
    expect(getMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/invitations", {
      params: { path: { tenant_id: TENANT_ID } },
    });
  });

  it("inviteMember POSTs an invitation", async () => {
    const invitation = {
      invitation_id: INVITATION_ID,
      email: "c@d.test",
      proposed_role: "accountant" as const,
      status: "pending" as const,
      created_at: "2026-01-01T00:00:00Z",
      expires_at: "2026-01-08T00:00:00Z",
    };
    postMock.mockResolvedValueOnce(ok(invitation, 201));
    await expect(
      inviteMember(TENANT_ID, {
        email: "c@d.test",
        proposed_role: "accountant",
      }),
    ).resolves.toEqual(invitation);
    expect(postMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/invitations", {
      params: { path: { tenant_id: TENANT_ID } },
      body: { email: "c@d.test", proposed_role: "accountant" },
    });
  });

  it("cancelInvitation DELETEs a single invitation", async () => {
    deleteMock.mockResolvedValueOnce(ok({}, 204));
    await expect(cancelInvitation(TENANT_ID, INVITATION_ID)).resolves.toBeUndefined();
    expect(deleteMock).toHaveBeenCalledWith("/v1/tenants/{tenant_id}/invitations/{invitation_id}", {
      params: {
        path: { tenant_id: TENANT_ID, invitation_id: INVITATION_ID },
      },
    });
  });

  it("acceptInvitation POSTs the token in the body (ADR-0031)", async () => {
    const result = {
      tenant_id: TENANT_ID,
      tokens: {
        access_token: "at",
        refresh_token: "rt",
        id_token: "it",
        token_type: "Bearer",
        expires_in: 3600,
      },
    };
    postMock.mockResolvedValueOnce(ok(result));
    await expect(acceptInvitation("opaque-token")).resolves.toEqual(result);
    expect(postMock).toHaveBeenCalledWith("/v1/invitations/accept", {
      body: { token: "opaque-token" },
    });
  });

  it("previewInvitation GETs the preview endpoint with token in path", async () => {
    const preview = {
      tenant_name: "Mi Empresa",
      email: "c@d.test",
      proposed_role: "accountant" as const,
      expires_at: "2026-01-08T00:00:00Z",
    };
    getMock.mockResolvedValueOnce(ok(preview));
    await expect(previewInvitation("opaque-token")).resolves.toEqual(preview);
    expect(getMock).toHaveBeenCalledWith("/v1/invitations/{token}/preview", {
      params: { path: { token: "opaque-token" } },
    });
  });
});

describe("expectData / expectVoid error branches", () => {
  it("expectData throws ApiError when the call returns an error body", async () => {
    postMock.mockResolvedValueOnce(fail(422, { code: "validation.request_invalid" }));
    await expect(createTenant({ name: "", is_withholder: false })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: { code: "validation.request_invalid" },
      message: "POST /v1/tenants failed: 422",
    });
  });

  it("expectData throws ApiError(detail=null) when data is undefined", async () => {
    getMock.mockResolvedValueOnce(undef(404));
    await expect(getTenant(TENANT_ID)).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: null,
      message: `GET /v1/tenants/${TENANT_ID} failed: 404`,
    });
  });

  it("expectVoid throws ApiError when the call returns an error body", async () => {
    deleteMock.mockResolvedValueOnce(fail(403, { code: "rbac.forbidden" }));
    await expect(removeMember(TENANT_ID, USER_ID)).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      detail: { code: "rbac.forbidden" },
    });
  });

  it("expectVoid resolves with no error even if data is undefined", async () => {
    patchMock.mockResolvedValueOnce(undef(204));
    await expect(updateMemberRole(TENANT_ID, USER_ID, { role: "viewer" })).resolves.toBeUndefined();
  });

  it("interpolates the path id into the error label", async () => {
    deleteMock.mockResolvedValueOnce(fail(404, { code: "not_found" }));
    await expect(cancelInvitation(TENANT_ID, INVITATION_ID)).rejects.toMatchObject({
      message: `DELETE /v1/tenants/${TENANT_ID}/invitations/${INVITATION_ID} failed: 404`,
    });
  });
});
