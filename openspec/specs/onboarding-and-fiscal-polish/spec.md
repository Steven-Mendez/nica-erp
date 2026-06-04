# onboarding-and-fiscal-polish Specification

## Purpose
TBD - created by archiving change tidy-onboarding-and-fiscal-defaults. Update Purpose after archive.
## Requirements
### Requirement: First-run defaults match the Nicaraguan SMB context

The first-run surfaces SHALL default to choices that match the
Nicaraguan SMB context:

- `/welcome` timezone picker SHALL default to `America/Managua` and
  SHALL group `America/Managua`, `America/Tegucigalpa`,
  `America/El_Salvador`, `America/Guatemala`, `America/Mexico_City`
  under a `Comunes (Centroamérica)` header at the top of the list.
- `/welcome` timezone picker SHALL expose a search input that
  filters by both IANA name and Spanish-friendly label.
- `/onboarding` H1 SHALL read `Crea tu primera empresa` (not
  `Bienvenido a Nica ERP`).
- `/empresa/settings` Departamento combobox SHALL default to
  `Managua`; the Municipio input SHALL be visually disabled with
  helper text `Elige un departamento primero.` until Departamento is
  set.

#### Scenario: Welcome timezone defaults to Managua

- **GIVEN** a freshly-confirmed operator on `/welcome`
- **WHEN** the timezone combobox renders
- **THEN** the selected option SHALL be `America/Managua`

#### Scenario: Onboarding heading is Crea tu primera empresa

- **GIVEN** an authenticated operator with zero empresas
- **WHEN** the SPA mounts `/onboarding`
- **THEN** the H1 SHALL read `Crea tu primera empresa`

#### Scenario: Settings Municipio shows a hint until Departamento is set

- **GIVEN** an authenticated owner on `/empresa/settings` with no
  Departamento selected
- **WHEN** the form renders
- **THEN** the Municipio input SHALL be visually disabled
- **AND** the helper text SHALL read `Elige un departamento primero.`

### Requirement: Header overlays are mutually exclusive

The AppShell SHALL ensure that only one header overlay (Theme picker
OR Account menu) is open at a time. Opening either SHALL close the
other if it was open.

#### Scenario: Opening the Account menu closes the Theme dialog

- **GIVEN** the Theme dialog is open
- **WHEN** the operator clicks the Account menu button
- **THEN** the Theme dialog SHALL close
- **AND** the Account menu SHALL open

### Requirement: Tenant-name validation rejects angle brackets explicitly

The tenant-name validator SHALL reject names containing `<` or `>`
with `422 invalid_tenant_name` and Spanish detail copy
`El nombre no puede contener "<" o ">"`. The API SHALL NOT silently
strip these characters from the submitted name.

#### Scenario: Angle brackets in tenant name return 422

- **GIVEN** an authenticated owner calling `POST /v1/tenants`
- **WHEN** the request body is
  `{"name":"<img src=x onerror=alert(1)>","ruc":"0011111111111A"}`
- **THEN** the API SHALL respond `422 invalid_tenant_name`
- **AND** SHALL NOT persist a tenant row

### Requirement: Auth email templates lead with Spanish primary content

Every auth email template (signup-confirmation, resend-confirmation, forgot-password) SHALL render Spanish copy in the primary (top) block and English copy in a shorter secondary block below. The subject SHALL follow the pattern `nica-erp: <spanish copy> / <english copy>`.

#### Scenario: Signup confirmation email leads with Spanish

- **GIVEN** a fresh signup for `owner1@audit.test`
- **WHEN** the email is rendered
- **THEN** the first non-blank line of the body SHALL be Spanish
- **AND** the Spanish block SHALL contain the verification code on
  its own line
- **AND** a secondary English block SHALL appear below the Spanish
  block with the same code

