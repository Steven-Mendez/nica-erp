## MODIFIED Requirements

### Requirement: `/tenants/new` is a four-step skippable wizard

The route `/tenants/new` SHALL render a four-step wizard for
empresa creation. The previous single-step form (established
by sprint 3.11 `simplify-creation-and-empresa-rebrand`) SHALL
be replaced. The four steps, in order, MUST be:

1. **Identidad** — captures `name` (*required*) and `ruc`
   (optional).
2. **Régimen fiscal** — captures `regime`, `municipality`,
   and `is_withholder` (all optional).
3. **Autorización DGI** — captures the DGI authorisation
   `number`, `valid_from`, and `valid_to` (all optional).
4. **Dirección y resumen** — captures `fiscal_address`
   (optional) and renders the Revisión card.

The page title (via `useDocumentTitle`) MUST be `Crear empresa`.

The Zod schema in
`apps/web/src/features/tenants/schemas/index.ts` MUST keep
`name` as the only required field and every other field as
`.optional()` (the relaxation from sprint 3.11 is preserved).

The wizard MUST preserve every sprint 3.7–3.10 ergonomic:

- `useForm({ mode: "onTouched", reValidateMode: "onChange" })`.
- Per-step error gating via `attemptedSteps` so per-field
  errors render only after a failed `trigger()` or an
  explicit submit.
- `<RequiredMark />` next to required labels (in this
  iteration: only `name`, per ADR-0034).
- shadcn `Select` for Régimen and Municipio, sourced from
  `MUNICIPALITIES`.
- shadcn `Checkbox` for `is_withholder` with an info
  `Tooltip`.
- shadcn `DatePicker` for DGI `valid_from` / `valid_to`
  with Spanish month names.
- Info `Tooltip` icons next to Régimen, Municipio, DGI
  número, and Es retenedor labels.
- Four-section Revisión card with `Separator` between
  sections, `Badge` for Retenedor, and a Vigencia row
  formatted `dd MMM yyyy → dd MMM yyyy` in Spanish.

#### Scenario: Identidad step renders on mount

- **WHEN** the user navigates to `/tenants/new`
- **THEN** the rendered DOM shows the Identidad step with a
  Nombre `<Input>` (with `*` mark) and a RUC `<Input>`, plus
  a "Continuar" primary button and a "Saltar y crear"
  secondary button

#### Scenario: Walking all four steps submits the full payload

- **GIVEN** the user fills every field across all four steps
- **WHEN** the user clicks "Crear empresa" on step 4
- **THEN** `POST /v1/tenants` is called with the full body
  `{ name, ruc, regime, municipality, authorization_dgi:
  { number, valid_from, valid_to }, fiscal_address,
  is_withholder }`

### Requirement: "Saltar y crear" submits whatever has been captured

Each of steps 1, 2, and 3 SHALL render a secondary `Saltar y
crear` button next to the primary `Continuar` button.
Clicking `Saltar y crear` MUST invoke
`form.handleSubmit(onSubmit)` directly, bypassing the
per-step `trigger(STEP_FIELDS[step])` gate. The Zod resolver
still runs at submit time — only `name` is validated as
required.

On step 4 (Dirección y resumen), the wizard MUST NOT render
a `Saltar y crear` button. The primary button on step 4
reads `Crear empresa` and submits via the standard
`form.handleSubmit(onSubmit)` path.

The backend's `CreateTenantRequest` (per
[ADR-0034](../../../docs/adr/0034-empresa-product-term-and-soft-creation.md))
coerces empty strings and nested empty `authorization_dgi`
objects to NULL, so the wizard MAY send raw form values
without client-side pre-stripping.

#### Scenario: Saltar y crear from step 1 with only a name

- **GIVEN** the user is on step 1 with `name = "Mi Empresa"`
  and every other field empty
- **WHEN** the user clicks `Saltar y crear`
- **THEN** the wizard calls `POST /v1/tenants` with the body
  `{ name: "Mi Empresa", is_withholder: false }` and any
  other optional fields are sent as their RHF-default empty
  values (which the backend coerces to NULL)

#### Scenario: Saltar y crear from step 3 mid-DGI

- **GIVEN** the user is on step 3 with `name` set, `regime
  = "general"`, and a half-typed DGI number
- **WHEN** the user clicks `Saltar y crear`
- **THEN** the wizard submits and the backend rejects the
  partial DGI with a 422 (since `valid_from`/`valid_to` are
  missing under a typed number); the wizard surfaces the
  Spanish field-level error in the `<Alert>` via
  `formatApiError`

### Requirement: Saltar y crear is disabled on step 1 until `name` is non-empty

On step 1 (Identidad), the `Saltar y crear` button MUST be
disabled while `form.watch("name").trim() === ""`. The check
SHALL use RHF's `watch` (not a local state mirror) so the
button enables on keystroke without manual wiring.

On steps 2 and 3, `Saltar y crear` MUST always be enabled.
Reaching step 2 implies the user already passed step 1's
`trigger("name")` gate, which proves `name` was non-empty
at that moment.

#### Scenario: Disabled while name is empty

- **WHEN** the user mounts `/tenants/new` and has not typed
  anything
- **THEN** the `Saltar y crear` button is `disabled`

#### Scenario: Enabled after typing a name

- **GIVEN** the user is on step 1 with an empty `name`
- **WHEN** the user types `Mi Empresa`
- **THEN** the `Saltar y crear` button is no longer disabled
