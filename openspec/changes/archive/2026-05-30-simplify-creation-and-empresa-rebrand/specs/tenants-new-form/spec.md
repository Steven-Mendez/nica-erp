## MODIFIED Requirements

### Requirement: `/tenants/new` is a single-step empresa-creation form

The route `/tenants/new` SHALL render a single-step form
that requires only the empresa name. The four-step wizard
established by sprints 3.7–3.10 (Identidad / Régimen
fiscal / Autorización DGI / Dirección + Revisión) SHALL be
removed from this route. No Select for régimen, no Select
for municipio, no DatePicker, no Checkbox for `is_withholder`,
no `<TooltipProvider>`, no per-step gating, no Revisión
panel. The page title (via `useDocumentTitle`) MUST be
`Crear empresa`.

The form MUST contain:

- One `<Input>` for `name` with a Spanish required mark
  (`<span aria-hidden="true" className="text-destructive">*</span>`)
  next to its `<Label>`.
- A single `<Button type="submit">` reading `Crear
  empresa`.
- An `<Alert variant="destructive">` slot that renders
  `formatApiError` output on backend failure (the helper
  established by sprint 3.8 is preserved).
- A `<Link to="/tenants">← Cancelar</Link>` consistent
  with sprints 3.6/3.10.

The form MUST POST `{ name }` to `/v1/tenants` (no other
fields), THEN call `POST /v1/tenants/{id}/switch`, THEN
navigate to `/dashboard`. The Zod resolver MUST validate
only the `name` field at submit time.

#### Scenario: Single-field form on mount

- **WHEN** the user mounts `/tenants/new`
- **THEN** the rendered DOM contains exactly one form
  input labelled "Nombre" (or "Nombre de la empresa"),
  a required-mark `*` next to its label, and a "Crear
  empresa" submit button; no Régimen Select, no
  Municipio Select, no DatePicker, no Checkbox, no
  Tooltip icons, and no `<TooltipProvider>` are present

#### Scenario: Submission posts only `name`

- **WHEN** the user types "Mi Empresa" into Nombre and
  submits the form
- **THEN** `useCreateTenantMutation().mutate` is called
  with `{ name: "Mi Empresa" }` (the payload MUST NOT
  contain `ruc`, `regime`, `municipality`,
  `authorization_dgi`, `fiscal_address`, or
  `is_withholder` set to a non-default value)

### Requirement: User-visible copy on `/tenants/new` reads "empresa"

Every visible string on `/tenants/new` SHALL use the
Spanish word "empresa" (not "organización"). This applies
to the page title, the field label, the placeholder, the
submit button, the cancel link, and any error/help copy.
"Organización" / "Organizaciones" MUST NOT appear anywhere
in the route's source. The backend identifier names
(`/v1/tenants`, `tenant_id`, the imported `Tenant` type)
stay unchanged per ADR-0034.

#### Scenario: No "organización" copy on /tenants/new

- **WHEN** the route is rendered and the DOM is inspected
- **THEN** no rendered text contains "organización" or
  "Organización" (case-insensitive match returns zero
  results)

#### Scenario: "Empresa" copy is present

- **WHEN** the route is rendered
- **THEN** the page title is "Crear empresa", the submit
  button reads "Crear empresa", and the field label reads
  "Nombre" (a basic Spanish noun with no qualifier — the
  form context already establishes that this is the
  empresa's name)
