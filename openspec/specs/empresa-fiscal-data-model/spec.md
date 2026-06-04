# empresa-fiscal-data-model Specification

## Purpose
TBD - created by archiving change unify-fiscal-data-model-wizard-and-settings. Update Purpose after archive.
## Requirements
### Requirement: Empresa fiscal data uses a single canonical shape across create and update

The empresa fiscal data SHALL share a single canonical model between
the create wizard (`/tenants/new`), the update editor
(`/empresa/settings`), the API request schemas, and the empresa-vista
read view. Specifically:

- `departamento` SHALL be one of the 17 values (15 departments + RAAN
  + RAAS) listed in alphabetical order with Spanish-canonical spelling.
- `municipality` SHALL be a free-text field (up to 80 chars), captured
  separately from `departamento` on both create and update surfaces.
- `ruc` SHALL be persisted in canonical form without dashes; both the
  wizard and the settings editor SHALL display the canonical
  placeholder `J03-100000-00010` and normalise user input by
  stripping non-alphanumerics and uppercasing.
- DGI authorisation date fields SHALL be labelled `Inicio de vigencia`
  and `Vencimiento` on every visible surface (wizard, settings,
  vista general).

#### Scenario: Wizard step 2 captures Departamento and Municipio separately

- **GIVEN** an operator on `/tenants/new` step 2
- **WHEN** the operator selects `Managua` from the Departamento
  combobox and types `Distrito V` into the Municipio input
- **AND** advances and submits the wizard
- **THEN** the captured `POST /v1/tenants` body SHALL include
  `departamento:"Managua"` and `municipality:"Distrito V"`
- **AND** the API response SHALL include the same two keys

#### Scenario: Settings editor exposes the same 17 Departamento options

- **GIVEN** an authenticated owner on `/empresa/settings`
- **WHEN** the Departamento combobox is opened
- **THEN** it SHALL list exactly 17 options (15 deps + RAAN + RAAS)
- **AND** the option list SHALL be identical to the wizard step 2's
  Departamento combobox

#### Scenario: Wizard prefills carry over into Settings

- **GIVEN** an operator who completed the wizard with
  `departamento:"Managua"` and `municipality:"Altamira"`
- **WHEN** the operator opens `/empresa/settings` immediately after
- **THEN** the Departamento combobox SHALL show `Managua` as selected
- **AND** the Municipio input SHALL contain `Altamira`

#### Scenario: RUC placeholder and normalisation are shared

- **GIVEN** the wizard step 1 RUC input
- **WHEN** the operator focuses the field
- **THEN** the placeholder SHALL read `J03-100000-00010`
- **WHEN** the operator types `j03-100000-00010` and submits
- **THEN** the submitted body SHALL contain `ruc:"J0310000000010"`
  (uppercase, no dashes)
- **AND** the same normalisation SHALL apply in the settings editor

#### Scenario: DGI date labels are unified

- **GIVEN** any surface that displays the DGI authorisation date pair
  (wizard step 3, settings editor, empresa vista)
- **WHEN** the surface renders
- **THEN** the labels SHALL be `Inicio de vigencia` and `Vencimiento`
- **AND** the older labels `Válido desde` / `Válido hasta` SHALL NOT
  appear anywhere in the SPA

