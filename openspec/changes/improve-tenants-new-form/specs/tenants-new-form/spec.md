## ADDED Requirements

### Requirement: All validation messages are in Spanish

The `/tenants/new` wizard SHALL surface only Spanish
validation copy. Every Zod constraint in
`apps/web/src/features/tenants/schemas/index.ts` (covering
`createTenantSchema`, `updateTenantSchema`,
`inviteMemberSchema`, `updateMemberRoleSchema`) MUST declare
an explicit Spanish `message` so the form never renders the
default English Zod error (`String must contain at least 1
character(s)`, `Invalid email`, `Invalid string`, etc.).

#### Scenario: Empty name submission shows Spanish error

- **WHEN** the user submits the Identidad step with an empty
  `name` field
- **THEN** the rendered error reads `El nombre es obligatorio.`
  (or equivalent Spanish copy), never `String must contain at
  least 1 character(s)`

#### Scenario: Malformed RUC shows Spanish error

- **WHEN** the user types `123` into RUC and triggers
  validation
- **THEN** the rendered error reads `13 dígitos + 1 letra
  mayúscula` (existing copy, kept)

### Requirement: Régimen renders a shadcn Select

The Régimen step SHALL render the régimen field as a shadcn
`<Select>` composed of `<SelectTrigger>`, `<SelectValue>`,
`<SelectContent>`, and `<SelectItem>` for exactly two options:
`general` ("General") and `simplified` ("Simplificado"). The
bare `<select>` HTML element MUST be removed.

#### Scenario: Régimen Select renders both options

- **WHEN** the user advances to the Régimen step and opens the
  Régimen trigger
- **THEN** the popover lists exactly two items labelled
  "General" and "Simplificado"

#### Scenario: Régimen selection updates form state

- **WHEN** the user picks "Simplificado"
- **THEN** the controlled form value `regime` is the string
  `"simplified"` and the `<SelectValue>` displays "Simplificado"

### Requirement: Municipio renders a shadcn Select over the canonical catalog

The Municipio field SHALL render a shadcn `<Select>` over the
17-entry catalog exported from
`apps/web/src/features/tenants/municipalities.ts`. The catalog
MUST mirror the backend
`apps/api/src/contexts/tenants/domain/municipality.py::KNOWN_MUNICIPALITIES`
set exactly (same 17 strings, same casing). The schema MUST
constrain `municipality` to `z.enum(MUNICIPALITIES)` so a
non-catalog value is rejected client-side before the POST.

#### Scenario: Municipio Select renders all 17 entries

- **WHEN** the user opens the Municipio trigger
- **THEN** the popover lists exactly 17 items including
  "Managua", "León", "Granada", "RAAN", "RAAS", "Río San Juan"

#### Scenario: Municipio selection updates form state

- **WHEN** the user picks "León"
- **THEN** the controlled form value `municipality` is the
  string `"León"`

### Requirement: is_withholder uses shadcn Checkbox with Tooltip

The `is_withholder` field SHALL render as a shadcn `<Checkbox>`
+ `<Label>` pair. An info-circle icon SHALL sit next to the
label and SHALL trigger a `<Tooltip>` whose content explains
the fiscal term in Spanish, e.g., "Un retenedor IR es una
empresa designada por la DGI para retener impuestos a sus
proveedores en cada pago." The bare `<input type="checkbox">`
MUST be removed.

#### Scenario: Checkbox primitive renders

- **WHEN** the Régimen step is visible
- **THEN** the rendered DOM contains a `[role="checkbox"]`
  element (Radix's checkbox role) and no `<input
  type="checkbox">` is present

#### Scenario: Hovering the info icon surfaces the explanation

- **WHEN** the user hovers (or focuses) the info icon next to
  "Es retenedor"
- **THEN** a tooltip appears containing the Spanish
  explanation "Un retenedor IR es una empresa designada por la
  DGI para retener impuestos a sus proveedores en cada pago."

### Requirement: Régimen and DGI número labels carry tooltips

The Régimen field label and the DGI número field label SHALL
each carry an info-circle icon that, on hover or focus, MUST
trigger a shadcn `<Tooltip>` with a one-sentence Spanish
explanation:

- Régimen: "General: factura IVA estándar. Simplificado:
  cuota fija mensual."
- DGI número: "Número de autorización de impresión emitido
  por la DGI para los rangos de comprobante fiscal."

#### Scenario: Régimen label has an info tooltip

- **WHEN** the user hovers the info icon next to the Régimen
  label
- **THEN** a tooltip containing both régimen explanations
  appears

#### Scenario: DGI número label has an info tooltip

- **WHEN** the user advances to the Autorización DGI step and
  hovers the info icon next to "Número"
- **THEN** a tooltip explaining the DGI número appears

### Requirement: Backend validation errors are rendered in the UI

The wizard SHALL surface backend validation detail on POST
failure. When `POST /v1/tenants` returns a 422 with an
RFC-7807 or FastAPI validation-error body, the wizard MUST
render the specific failed field and message — not just a
generic `"failed: 422"`. The displayed message MUST be in
Spanish where the backend supplies a Spanish message; the
field name MUST be human-readable (e.g., "Municipio" rather
than "body.municipality"). When the backend returns no
machine-readable detail, the wizard MUST fall back to the
generic Spanish message "No se pudo crear la organización.
Revisa los datos e intenta de nuevo."

#### Scenario: Backend rejects malformed payload

- **WHEN** the user submits the final step and the backend
  responds 422 with detail
  `[{"loc": ["body", "municipality"], "msg": "..."}]`
- **THEN** the wizard `<Alert variant="destructive">`
  surfaces a message referencing the Municipio field, not
  just `"POST /v1/tenants failed: 422"`

### Requirement: Tooltip provider wraps the wizard root

The `/tenants/new` route component SHALL wrap its root
`<div>` in a single shadcn `<TooltipProvider>` so all
in-route tooltips share one provider and inherit a consistent
`delayDuration`.

#### Scenario: Single TooltipProvider in route

- **WHEN** the route is mounted
- **THEN** the rendered tree contains exactly one
  `<TooltipProvider>` ancestor for all `<Tooltip>` instances
