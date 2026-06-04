# invitation-email-localization Specification

## Purpose
TBD - created by archiving change localize-invitation-email-to-spanish. Update Purpose after archive.
## Requirements
### Requirement: Invitation emails are bilingual with Spanish as the primary language

The system SHALL render the invitation email with the Spanish copy
appearing before the English copy in both subject and body. The subject
SHALL match the pattern `nica-erp: invitación a <tenant_name> /
invitation to <tenant_name>`. The text body SHALL contain a Spanish
block first (greeting, "Has sido invitado a unirte a <tenant_name>",
the accept URL with expiry note, and a "Si no esperabas..." sign-off)
followed by an English block with the same information.

#### Scenario: Subject is bilingual, Spanish first

- **GIVEN** an invitation issued for tenant `Empresa Auditoría Alfa`
- **WHEN** the system renders the invitation email
- **THEN** the email subject SHALL match
  `nica-erp: invitación a Empresa Auditoría Alfa / invitation to Empresa Auditoría Alfa`

#### Scenario: Body has Spanish block followed by English block

- **GIVEN** the same invitation
- **WHEN** the system renders the text body
- **THEN** the first non-blank line of the body SHALL start with
  `Invitación a Empresa Auditoría Alfa`
- **AND** the body SHALL contain the Spanish phrase
  `Has sido invitado a unirte a Empresa Auditoría Alfa`
- **AND** the body SHALL contain the Spanish phrase
  `Acepta aquí (expira en 7 días)`
- **AND** the body SHALL contain the English phrase
  `You have been invited to join Empresa Auditoría Alfa`

#### Scenario: Accept URL is rendered as a plain text URL on a line of its own

- **GIVEN** the rendered email body
- **WHEN** the recipient inspects the message
- **THEN** the accept URL SHALL appear on its own line in both the
  Spanish and English blocks so any mail client (Mailpit, Gmail,
  Outlook) auto-linkifies it

