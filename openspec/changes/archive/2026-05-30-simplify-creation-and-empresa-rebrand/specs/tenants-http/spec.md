## ADDED Requirements

### Requirement: `POST /v1/tenants` accepts only `name` as required

The `CreateTenantRequest` Pydantic model SHALL declare
`name` as the only required field. Every other field
(`ruc`, `regime`, `municipality`, `authorization_dgi`,
`fiscal_address`) SHALL be typed as `Optional[...]` with
`default=None`. The `is_withholder` field MUST keep its
existing `default=False` (a boolean's "not specified" state
is `False`, not None).

The endpoint MUST accept a body containing only `{"name":
"..."}` and respond with `201 Created` and a complete
`TenantResponse` whose fiscal fields are `null`. The
endpoint MUST also accept a body containing the full set of
fiscal fields and behave exactly as before.

#### Scenario: Minimal request creates a fiscally-incomplete tenant

- **WHEN** the client POSTs `{"name": "Mi Empresa"}` to
  `/v1/tenants` with a valid Bearer token
- **THEN** the response is `201 Created`, the
  `TenantResponse.ruc`, `.regime`, `.municipality`,
  `.authorization_dgi`, and `.fiscal_address` are all
  `null`, and `.is_withholder` is `false`

#### Scenario: Full request still works

- **WHEN** the client POSTs a complete payload with every
  fiscal field populated
- **THEN** the response is `201 Created` and the
  `TenantResponse` carries every field as before this
  change

### Requirement: `TenantResponse` exposes Optional fiscal fields

The `TenantResponse` Pydantic model SHALL declare `ruc`,
`regime`, `municipality`, `authorization_dgi`, and
`fiscal_address` as Optional fields. The OpenAPI schema
generated from this model MUST emit `nullable: true` (or
the equivalent `anyOf` with `{type: "null"}`) so the
TypeScript client codegen produces `field?: string | null`
shapes for downstream consumers.

#### Scenario: OpenAPI schema marks fiscal fields nullable

- **WHEN** the OpenAPI document is regenerated
- **THEN** every fiscal field on `TenantResponse` is marked
  nullable (or its TypeScript equivalent), and the
  `apps/web/src/api/schema.d.ts` regeneration produces
  `string | null` / `Schema | null` for those fields
