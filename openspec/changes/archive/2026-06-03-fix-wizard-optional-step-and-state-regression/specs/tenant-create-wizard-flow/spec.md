## ADDED Requirements

### Requirement: The empresa-create wizard preserves prior steps' data across validation failures

The `/tenants/new` 4-step wizard SHALL preserve every prior step's
field values when the current step's validation fails. A validation
failure on step N SHALL leave the wizard on step N with field-level
errors set on the failing inputs, and the values entered on steps 1
through N-1 SHALL remain intact in the form state and re-render
identically when the user navigates Atrás.

#### Scenario: Step 2 validation failure does not regress to step 1

- **GIVEN** the operator has filled step 1 with `Nombre: "Empresa
  Auditoría Alfa"` and `RUC: "J0310000000010"` and advanced to step 2
- **WHEN** the operator clicks Continuar on step 2 with Régimen unset
- **THEN** the wizard SHALL remain on step 2
- **AND** the wizard SHALL render a Spanish field-level error
  next to the Régimen combobox
- **AND** clicking Atrás SHALL return to step 1 with the
  `Nombre` and `RUC` values preserved

### Requirement: Wizard step 3 (Autorización DGI) is genuinely optional unless any field is filled

The `/tenants/new` step 3 Autorización DGI section SHALL accept a
fully-blank submission and advance to step 4. If the operator fills
ANY of the three fields (`Número`, `Inicio de vigencia`, `Vencimiento`),
ALL three SHALL be required on submit (all-or-nothing). When the
section is left fully blank, the wizard SHALL NOT include
`authorization_dgi` in the create-empresa request body.

#### Scenario: Blank step 3 advances to step 4

- **GIVEN** the operator is on step 3 with all three fields blank
- **WHEN** the operator clicks Continuar
- **THEN** the wizard SHALL advance to step 4 with no error rendered

#### Scenario: Partial step 3 stays on step 3 with field errors

- **GIVEN** the operator is on step 3 with `Número` filled and the
  two date fields blank
- **WHEN** the operator clicks Continuar
- **THEN** the wizard SHALL remain on step 3
- **AND** SHALL render a Spanish field-level error on each blank date
  field referencing the all-or-nothing rule

#### Scenario: Blank step 3 omits authorization_dgi from the request

- **GIVEN** the wizard reaches step 4 with step 3 left fully blank
- **WHEN** the operator submits step 4
- **THEN** the captured `POST /v1/tenants` body SHALL NOT include an
  `authorization_dgi` key
