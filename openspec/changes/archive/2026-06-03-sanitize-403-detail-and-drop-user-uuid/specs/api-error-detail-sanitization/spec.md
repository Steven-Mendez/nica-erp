## ADDED Requirements

### Requirement: 403 envelopes use generic Spanish detail with no internal claim path or tenant id

The API SHALL render 403 response detail fields in generic Spanish
that does not reference internal claim paths, table names, or tenant
UUIDs. The specific codes covered are:

- `tenant.required` → detail `Acceso denegado: empresa no
  seleccionada.`
- `missing-permission` → detail `Acceso denegado: faltan permisos.`,
  with the `missing` field omitted when the list is empty
- `tenant.not_member` → detail `Acceso denegado.`, with no tenant id
  in the detail string

#### Scenario: tenant.required envelope no longer leaks claim path

- **GIVEN** an authenticated user with no `custom:active_tenant`
  claim set
- **WHEN** the user calls `GET /v1/tenants/<some-id>`
- **THEN** the API SHALL respond 403 with `code:"tenant.required"`
  and `detail:"Acceso denegado: empresa no seleccionada."`
- **AND** the detail string SHALL NOT include the substring
  `custom:active_tenant` or `JWT`

#### Scenario: missing-permission envelope omits empty missing list

- **GIVEN** a user whose authorization is denied with no specific
  permission identified
- **WHEN** the user calls a route protected by the missing-permission
  guard
- **THEN** the response body SHALL be 403 with `code:"missing-permission"`,
  `detail:"Acceso denegado: faltan permisos."`
- **AND** the body SHALL NOT include a `missing` field

### Requirement: Members table does not render user UUIDs

The `/empresa/users` members table SHALL NOT render any member's
`user_id` UUID as visible text. The UUID MAY remain available in row
data for the actions menu and other interactions, but it SHALL NOT
appear as a cell value, tooltip, or aria-label.

#### Scenario: Desktop members table omits UUIDs

- **GIVEN** an empresa with two members
- **WHEN** the user opens `/empresa/users` on a desktop viewport
- **THEN** the rendered table cells SHALL NOT include any string
  matching the UUID regex `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`
