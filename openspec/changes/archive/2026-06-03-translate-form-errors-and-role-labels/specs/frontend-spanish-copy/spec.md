## ADDED Requirements

### Requirement: All role-code values rendered in user-facing UI use the Spanish label map

The SPA SHALL render every member or invitation role code through a
single shared label map (`roleLabel(role)`) that returns the Spanish
display label. Components SHALL NOT render the raw English role
string in any user-visible position, including (but not limited to)
the empresa-list cards, the workspace switcher in the sidebar, the
members table, the invitations table, the invite dialog, and any
future surface that displays a member or invitee role.

#### Scenario: Empresa list cards show Spanish role labels

- **GIVEN** an authenticated user with one or more empresas where
  the user's role on each is `owner`
- **WHEN** the user opens `/tenants`
- **THEN** the role text rendered under each empresa card SHALL be
  `Propietario`
- **AND** the raw string `owner` SHALL NOT appear anywhere in the
  rendered output

#### Scenario: Members table renders Spanish labels

- **GIVEN** a tenant with members whose backend-issued roles span
  `owner / admin / accountant / salesperson / viewer`
- **WHEN** the user opens `/empresa/users`
- **THEN** the Rol column SHALL render
  `Propietario / Administrador / Contador / Vendedor / Visualizador`
  respectively

### Requirement: Form-field error messages are Spanish across every SPA form

The SPA SHALL render every form-field validation message in Spanish.
A global zod error map SHALL be registered at bootstrap so that the
default messages (`Required`, `Invalid`, etc.) are translated
(`Obligatorio`, `Valor inválido`, etc.). Schemas MAY override per-field
copy.

#### Scenario: Empty step-3 submit on the empresa wizard renders Spanish

- **GIVEN** the user is on `/tenants/new` step 3 with all fields blank
- **WHEN** the user clicks Continuar
- **THEN** the field error rendered next to `Número` SHALL be in
  Spanish (e.g. `Obligatorio`)
- **AND** no English string (`Required`, `Invalid`, etc.) SHALL appear
  in the page DOM
