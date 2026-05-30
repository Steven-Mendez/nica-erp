// Default MSW handlers typed against the committed OpenAPI schema.
// Per-spec overrides should use `server.use(http.<verb>(...))` so the
// `afterEach` reset restores this baseline between tests.
//
// `paths` is the named export from the auto-generated schema.d.ts;
// `openapi-msw` lifts it into a type-safe http factory so a renamed
// response field is a TypeScript error, not a silent green test.

import { createOpenApiHttp } from "openapi-msw";
import type { paths } from "@/api/schema";

export const http = createOpenApiHttp<paths>({ baseUrl: "http://localhost:8000" });

const ts = "2026-05-29T00:00:00Z";

const tokens = {
  access_token: "access.jwt",
  refresh_token: "refresh.jwt",
  id_token: "id.jwt",
  token_type: "Bearer" as const,
};

const tenantFixture = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Empresa Demo",
  ruc: "J0310000000000",
  regime: "general" as const,
  municipality: "Managua",
  authorization_dgi: null,
  fiscal_address: null,
  is_withholder: false,
  status: "active",
  created_at: ts,
  updated_at: ts,
};

export const handlers = [
  http.get("/healthz", ({ response }) =>
    response(200).json({
      status: "ok",
      version: "0.1.0",
      git_sha: "test",
      db: "ok",
      alembic_revision: "0004",
    }),
  ),

  // ---- Auth ---------------------------------------------------------
  http.post("/v1/auth/register", ({ response }) => response(201).json({})),
  http.post("/v1/auth/confirm-signup", ({ response }) => response(204).empty()),
  http.post("/v1/auth/resend-code", ({ response }) => response(204).empty()),
  http.post("/v1/auth/login", ({ response }) => response(200).json(tokens)),
  http.post("/v1/auth/refresh", ({ response }) => response(200).json(tokens)),
  http.post("/v1/auth/password/forgot", ({ response }) => response(200).json({})),
  http.post("/v1/auth/password/reset", ({ response }) => response(204).empty()),
  http.post("/v1/auth/change-password", ({ response }) => response(204).empty()),
  http.post("/v1/auth/logout", ({ response }) => response(204).empty()),

  // ---- Me ----------------------------------------------------------
  http.get("/v1/me", ({ response }) =>
    response(200).json({
      id: "11111111-1111-1111-1111-111111111111",
      email: "demo@nica-erp.test",
      display_name: "Demo Operador",
      locale: "es-NI",
      timezone: "America/Managua",
      preferences: {},
      active_tenant: null,
      role: null,
      permissions: [],
    }),
  ),
  http.patch("/v1/me", async ({ request, response }) => {
    const body = await request.json();
    return response(200).json({
      id: "11111111-1111-1111-1111-111111111111",
      email: "demo@nica-erp.test",
      display_name: body.display_name ?? "Demo Operador",
      locale: body.locale ?? "es-NI",
      timezone: body.timezone ?? "America/Managua",
      preferences: body.preferences ?? {},
      active_tenant: null,
      role: null,
      permissions: [],
    });
  }),

  // ---- Tenants -----------------------------------------------------
  http.get("/v1/tenants/me", ({ response }) => response(200).json({ items: [] })),
  http.post("/v1/tenants", async ({ request, response }) => {
    const body = await request.json();
    return response(201).json({
      ...tenantFixture,
      name: body.name,
      ruc: body.ruc ?? null,
      regime: body.regime ?? null,
      municipality: body.municipality ?? null,
      authorization_dgi: body.authorization_dgi ?? null,
      fiscal_address: body.fiscal_address ?? null,
      is_withholder: body.is_withholder,
    });
  }),
  http.get("/v1/tenants/{tenant_id}", ({ params, response }) =>
    response(200).json({ ...tenantFixture, id: params.tenant_id }),
  ),
  http.patch("/v1/tenants/{tenant_id}", async ({ params, request, response }) => {
    const body = await request.json();
    return response(200).json({
      ...tenantFixture,
      id: params.tenant_id,
      name: body.name ?? tenantFixture.name,
      regime: body.regime ?? tenantFixture.regime,
      municipality: body.municipality ?? tenantFixture.municipality,
      authorization_dgi: body.authorization_dgi ?? tenantFixture.authorization_dgi,
      fiscal_address: body.fiscal_address ?? tenantFixture.fiscal_address,
      is_withholder: body.is_withholder ?? tenantFixture.is_withholder,
    });
  }),
  http.post("/v1/tenants/{tenant_id}/switch", ({ response }) => response(200).json(tokens)),

  // ---- Members + invitations --------------------------------------
  http.get("/v1/tenants/{tenant_id}/members", ({ response }) => response(200).json([])),
  http.patch("/v1/tenants/{tenant_id}/members/{user_id}", ({ response }) => response(204).empty()),
  http.delete("/v1/tenants/{tenant_id}/members/{user_id}", ({ response }) => response(204).empty()),
  http.get("/v1/tenants/{tenant_id}/invitations", ({ response }) => response(200).json([])),
  http.post("/v1/tenants/{tenant_id}/invitations", async ({ params, request, response }) => {
    const body = await request.json();
    return response(201).json({
      id: "33333333-3333-3333-3333-333333333333",
      tenant_id: params.tenant_id,
      email: body.email,
      proposed_role: body.proposed_role,
      status: "pending",
      expires_at: ts,
      created_at: ts,
    });
  }),
  http.delete("/v1/tenants/{tenant_id}/invitations/{invitation_id}", ({ response }) =>
    response(204).empty(),
  ),
  http.get("/v1/invitations/{token}/preview", ({ response }) =>
    response(200).json({
      email: "invitee@nica-erp.test",
      organization_name: "Empresa Demo",
      role: "admin",
    }),
  ),
  http.post("/v1/invitations/accept", ({ response }) =>
    response(200).json({
      tenant_id: "22222222-2222-2222-2222-222222222222",
      role: "admin",
    }),
  ),
];
