## Why

The 2026-06-03 audit found four interlocking inconsistencies between
the `/tenants/new` wizard and the `/empresa/settings` editor for the
same fiscal data (F-006, F-012, F-034, F-035, plus a DGI-date labelling
mismatch). Concrete drift:

| Field | Wizard (`/tenants/new` step 2) | Settings (`/empresa/settings`) | API response |
|---|---|---|---|
| Location label | `Municipio` | `Departamento` + `Municipio` (separate) | both `departamento` and `municipality` present |
| Departamento options | 17 (15 deps + RAAN + RAAS) | 15 alphabetical (no RAAN/RAAS) | (data source unknown) |
| RUC placeholder | `0010101800010X` (13 digits + letter) | `J03-100000-00010` (letter + dashed groups) | persisted raw |
| DGI dates | `Válido desde` / `Válido hasta` | `Inicio de vigencia` / `Vencimiento` | n/a |

User impact: every empresa created via the wizard stores its real
*departamento* into the API field labelled `municipality`. After the
wizard, the settings page asks the user to fill the (still empty)
`Departamento` and to choose a `Municipio` — meaning either the data
the user typed earlier is silently wrong, or they have to re-enter it.
The data corrupts any downstream reports that filter by departamento.

This change picks **one canonical fiscal-data model** and forces both
screens (and the API schema) onto it.

## What Changes

### Decision — canonical model

The canonical model SHALL match `/empresa/settings`'s richer shape:

- `departamento`: enum of the 15 departments AND the 2 autonomous
  regions (RAAN, RAAS), so 17 total.
- `municipality`: free-text for now; future iteration may make it a
  dependent enum keyed by `departamento`.
- `ruc`: stored without dashes (canonical form `0010101800010X`); on
  display, the editor formats with dashes (`001-010180-00010-X` or
  whichever Nicaraguan convention the team picks — a UI helper, not
  a storage change).
- DGI dates: labels are `Inicio de vigencia` and `Vencimiento` (the
  settings labels). The wizard SHALL rename its step-3 fields to
  match. Storage stays `authorization_dgi.valid_from` /
  `valid_until`.

### Backend — schema alignment

- `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`
  (and underlying domain): confirm the input schema exposes both
  `departamento` and `municipality`, with `departamento` constrained
  to the 17-value enum. Add a Pydantic validator that rejects unknown
  values with a Spanish field-level error.
- Migration: backfill is OPTIONAL (existing data only contains audit
  artifacts). If any non-test row has `municipality` set to a value
  that matches a known departamento name, move it to `departamento`
  and null `municipality`. Skip if the dataset is known empty.

### Frontend — wizard step 2 rewrite

- `apps/web/src/routes/tenants/new.tsx` step 2:
  - Rename the existing single field from `Municipio` to
    `Departamento` (canonical 17-value enum, alphabetical order,
    Managua highlighted as suggested default — see G16 for the
    "highlight Managua" UX detail; this change just unifies the list).
  - Add a NEW `Municipio` field below `Departamento`, free text for
    now (matches settings).
  - Both fields persist to the same API keys as the settings editor
    (`departamento`, `municipality`).
  - Update copy on the wizard sidebar so "Régimen fiscal" still
    fits.

### Frontend — RUC placeholder / format unification

- Pick one canonical placeholder string and use it in BOTH the wizard
  and the settings editor. Recommendation (per the settings team's
  earlier choice): `J03-100000-00010` (15 chars with dashes) on the
  visible input, but persist as `J0310000000010` (no dashes) by
  stripping non-alphanumerics on submit. Document the convention in
  the schema docstring.
- Add a small Vitest unit test for the strip helper.

### Frontend — DGI date labels unified

- In the wizard step 3 (Autorización DGI), rename the visible labels
  from `Válido desde` / `Válido hasta` to `Inicio de vigencia` /
  `Vencimiento` so the wizard and the settings editor use the same
  Spanish copy. Internal field names (`valid_from` / `valid_until`)
  stay.

### Tests

- Backend: unit test that schema accepts each of the 17
  `departamento` values and rejects an unknown one with a Spanish
  field error.
- Frontend Vitest:
  - Wizard step 2 renders `Departamento` (17 options) and
    `Municipio` (free text); submitting persists to the correct API
    keys.
  - Settings editor still works (already covered by existing tests —
    add the 17-option assertion).
  - RUC strip helper: `J03-100000-00010 → J0310000000010`,
    `j0310000000010 → J0310000000010` (uppercase normalise).
- Browser smoke: create a new empresa through the wizard, immediately
  open `/empresa/settings` — the `Departamento` field is pre-filled
  with the wizard's selection. (Today it's empty.)

## Non-goals

- Designing the dependent `Municipio` enum (153 entries). Free text
  for now; a future change can introduce a typeahead and the data
  source.
- Backfill of production data — there is no production data yet.
- The fiscal-data missing-flag dashboard banner change (F-013 + the
  banner-dismiss UX) — separate UX bundle.
