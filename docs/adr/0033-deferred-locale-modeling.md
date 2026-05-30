# ADR-0033 — Deferred locale modeling

**Status**: Provisional (decided pre-implementation; revisit when i18n is on the roadmap)
**Date**: 2026-05-27

## Context
The `users` table inherited a single `locale` column with default
`'es-NI'` and `NOT NULL`, alongside `timezone` (default
`'America/Managua'`) and `display_name`. Sprint 3.6 introduces a
welcome screen on first login where the user is asked to fill in
their own profile — *not* defaults the system invents.

While planning the welcome screen the locale field surfaced a
non-trivial modelling question. BCP-47 conflates two distinct
concerns in one string: the **language** the UI is rendered in
(Spanish, English, …) and the **region** that drives formatting
(currency, decimal separator, date layout). A Nicaraguan operator
who prefers their UI in English has no clean BCP-47 to pick
(`en-NI` exists but is rare in real product locale lists), and a
non-Nicaraguan operator working with a Nicaraguan tenant inherits
the wrong formatting if we collapse it under their UI choice.

The product MVP does not require localisation in any language other
than Nicaraguan Spanish. Forcing a decision on locale modelling
now risks shipping a token shape (`'es-NI'`) that we will have to
migrate later. The single-coder constraint
([ADR-0018](0018-rolling-deploys.md)) discourages building i18n
infrastructure before there is a second locale to serve.

## Decision
**Drop the column's default and `NOT NULL`; do not expose `locale`
in the UI yet; document the future split.**

- Migration 0004 (sprint 3.6) makes `locale` nullable and removes
  the `'es-NI'` default. Existing rows keep their current value
  (the migration only touches column metadata).
- The welcome screen asks for `display_name` and `timezone`, **not**
  `locale`. The field stays in the API response (`/v1/me`) for
  contract stability, serialised as `string | null`, ignored by
  the frontend.
- All user-facing copy is hard-coded in Nicaraguan Spanish for
  this sprint. The frontend rename of "tenant" → "organization"
  ([ADR-0032](0032-tenant-vs-organization-naming.md)) introduces
  the *vocabulary* boundary that a future i18n layer will plug
  into, but no `t()` function is added now.
- When i18n becomes a roadmap item, the working hypothesis to
  evaluate is **splitting `locale` into `ui_language` (`es`, `en`,
  …) and `formatting_region` (`NI`, `MX`, `US`, …)**. The current
  `locale` column either becomes one of those two or is retired in
  favour of the pair, depending on what the i18n library of choice
  prefers.

## Consequences
- (+) No premature data model for a problem with no live use
  case. The product ships sooner.
- (+) Users are never silently labelled as Nicaraguan-Spanish
  speakers when they signed up from another country.
- (+) The future i18n sprint inherits a clean slate: a nullable
  field that can become the language column, or be dropped, with
  no historic defaults to unwind.
- (-) Until i18n lands, the SPA only renders Spanish. An
  English-preferring operator has no way to change that. Their
  workaround is browser translation extensions until the i18n
  sprint.
- (-) The `users.locale` column carries no information for new
  users, which can be confusing for someone reading the schema
  cold. The column comment will be updated to point at this ADR.

## Alternatives
- **Keep `locale='es-NI'` default and ship as-is** — rejected:
  the welcome screen would either ask the user for a locale we
  cannot localise the UI into yet (confusing) or hide a default
  the user never approved (the bug the user explicitly flagged
  during sprint 3.6 planning).
- **Split into `ui_language` + `formatting_region` now** —
  rejected: two columns, two domain enums, a UI surface that asks
  for both, all to serve a single-locale MVP. Premature.
- **Drop the column entirely now** — rejected: the API response
  `/v1/me` is consumed by callers (the SPA today, possibly
  integrations later); removing a documented field is a breaking
  change with no upside until we know what replaces it.

## Revisit triggers
- A second UI language becomes a roadmap commitment.
- A non-Nicaraguan tenant pilots the product and reports
  formatting/currency confusion serious enough to need
  per-user-and-tenant formatting control.
- An i18n library is selected; its data model dictates whether
  the column stays as-is, splits, or is replaced.
