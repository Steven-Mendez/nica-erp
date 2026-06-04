## ADDED Requirements

### Requirement: Every user-triggered write surface presents a Spanish success toast

The SPA SHALL render a Sonner toast on every user-triggered write
that returns a 2xx response. The toast copy SHALL be Spanish and
SHALL include the affected entity's name when applicable. The
following surfaces SHALL emit toasts:

- Empresa creation → `Empresa "<name>" creada.`
- Empresa fiscal save → `Datos fiscales actualizados.`
- Send invitation → `Invitación enviada a <email>.`
- Accept invitation → `Te uniste a <organization_name>.`
- Remove member → `Miembro removido.`
- Cancel invitation → `Invitación cancelada.`

#### Scenario: Empresa creation success toast

- **GIVEN** an authenticated owner completes the empresa-create
  wizard or clicks `Saltar y crear`
- **WHEN** the `POST /v1/tenants` returns 201 with body
  `{name:"Empresa Auditoría Alfa", ...}`
- **THEN** the SPA SHALL render a Sonner toast with the text
  `Empresa "Empresa Auditoría Alfa" creada.`
- **AND** the toast SHALL auto-dismiss within Sonner's default duration

#### Scenario: Invitation send success closes the dialog and shows a toast

- **GIVEN** the invite dialog is open with valid email + role
- **WHEN** `POST /v1/tenants/{id}/invitations` returns 201 with
  `{email:"invitee@audit.test", ...}`
- **THEN** the SPA SHALL close the dialog
- **AND** SHALL reset the form
- **AND** SHALL render a Sonner toast with the text
  `Invitación enviada a invitee@audit.test.`

### Requirement: The invite dialog closes on ESC and Cancelar regardless of mutation state

The invite-member dialog SHALL close when the user presses ESC or
clicks `Cancelar`, including when a previous mutation is pending or
has errored. Closing SHALL NOT cancel an in-flight network request,
but SHALL hide the dialog and reset the form state.

#### Scenario: ESC closes the dialog from a fresh-open state

- **GIVEN** the invite dialog is open with empty fields
- **WHEN** the user presses ESC
- **THEN** the dialog SHALL be closed
- **AND** the form SHALL be reset

#### Scenario: Cancelar closes the dialog after a failed submit

- **GIVEN** the invite dialog is open and a `POST` previously returned 409
- **AND** the inline error alert is rendered
- **WHEN** the user clicks `Cancelar`
- **THEN** the dialog SHALL be closed
- **AND** the form SHALL be reset
