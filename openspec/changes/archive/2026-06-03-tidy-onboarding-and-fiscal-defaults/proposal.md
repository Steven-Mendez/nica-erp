## Why

Bundle of P3 polish items from the 2026-06-03 audit. None individually
warrant a dedicated change, but together they remove a visible layer of
"this app feels half-done" friction that hits new SMB operators on
their first 60 seconds.

- **F-007** — `/welcome` timezone picker dumps 418 raw IANA names
  alphabetically (starts with `Africa/Abidjan`), no search, no
  Nicaragua default.
- **F-008** — `/welcome` and `/onboarding` both render the heading
  `Bienvenido a Nica ERP`, making them feel like the same screen
  twice.
- **F-037** — `/empresa/settings` Departamento combobox defaults to
  `Boaco` (alphabetical first) rather than `Managua`.
- **F-038** — `/empresa/settings` Municipio dropdown is enabled but
  empty until Departamento is selected; no inline hint.
- **F-039** — Theme dialog and Account menu can both be open
  simultaneously after operator clicks both header buttons.
- **F-019** — `POST /v1/tenants {name:"<...>"}` silently strips
  `<` and `>` from the tenant name. Defense-in-depth is fine; silent
  destructive normalisation is not.
- **F-004** — Auth emails (signup, OTP) are bilingual with English at
  equal weight; the project's Spanish-only rule prefers Spanish
  primary.

This change packages all seven as a single polish pass.

## What Changes

### Frontend

- `/welcome` timezone picker: pre-select `America/Managua`, add a
  search input, group "Comunes (Centroamérica)" at the top with
  `America/Managua`, `America/Tegucigalpa`, `America/El_Salvador`,
  `America/Guatemala`, `America/Mexico_City`. Render Spanish-friendly
  labels (`Managua (GMT-6)`) alongside the IANA name.
- `/onboarding` heading: rename from `Bienvenido a Nica ERP` to
  `Crea tu primera empresa`. Subtitle remains as-is.
- `/empresa/settings` Departamento combobox: default selection
  `Managua` (not alphabetical first). Municipio field renders the
  helper text `Elige un departamento primero.` and is visually
  disabled while Departamento is empty.
- Header overlays: when the operator opens the Account menu, any
  open Theme dialog SHALL close (and vice versa). Implement via a
  single shared "open overlay id" store in the AppShell.

### Backend

- `POST /v1/tenants` / `PATCH /v1/tenants/{id}`: reject names that
  contain `<` or `>` with 422 + Spanish copy `El nombre no puede
  contener "<" o ">"` instead of silently stripping. The tenant-name
  validator SHALL document this rule.
- Auth emails (`signup`, `resend`, `forgot-password`): swap the
  current bilingual structure so Spanish is the primary block (full
  body in Spanish first, English as a shorter trailing block). Match
  the structure of the G6 invitation email.

### Tests

- Vitest: `/welcome` timezone search matches `Managua` after typing
  `mana`; the default selected option is `America/Managua`.
- Vitest: `/onboarding` heading renders `Crea tu primera empresa`.
- Vitest: `/empresa/settings` Departamento defaults to `Managua`;
  Municipio shows the Spanish hint when Departamento is unset.
- Vitest: opening the Account menu closes an open Theme dialog (and
  vice versa).
- Backend unit: `POST /v1/tenants` with `name:"< Example >"` returns
  422 and does NOT persist a row.
- Backend unit: signup email renders Spanish first, English second.

## Non-goals

- Localizing IANA timezone display via a full i18n library — manual
  static mapping is enough.
- Backporting the "Spanish primary" email format to old historical
  invitations / messages.
- Reordering the wizard's Departamento list (G7 owns the canonical
  17-value list; this change just defaults the selection).
