## 1. Sprint doc

- [x] 1.1 Append a "Sprint follow-up — `/tenants/new` polish: required marks + Revisión card (sprint 3.10, 2026-05-27)" section to `docs/sprints/03-tenants-and-rls.md` after the existing 3.9 follow-up. Cover: motivation (eager errors + horrible Revisión), scope (one file), non-goals (no shared RequiredMark primitive, no step restructure).

## 2. Form mode + error gating

- [x] 2.1 In `apps/web/src/routes/tenants/new.tsx`, change `useForm({ ..., mode: "onChange" })` to `useForm({ ..., mode: "onTouched", reValidateMode: "onChange" })`.
- [x] 2.2 Destructure `touchedFields` and `isSubmitted` from `form.formState` alongside `errors`.
- [x] 2.3 Wrap every per-field error block with `(touchedFields.<path> || isSubmitted) && errors.<path>` so the message renders only after touch or submit. Paths to gate: `name`, `ruc`, `regime`, `municipality`, `authorization_dgi.number`, `authorization_dgi.valid_from`, `authorization_dgi.valid_to`, `fiscal_address`.

## 3. RequiredMark

- [x] 3.1 Define a `const RequiredMark = () => <span aria-hidden="true" className="text-destructive">*</span>` at module scope in `new.tsx`.
- [x] 3.2 Render `<RequiredMark />` next to every required-field label. Layout: wrap label + RequiredMark + (existing) InfoTip in `<div className="flex items-center gap-1.5">`. Required fields: Nombre, RUC, Régimen, Municipio, Número DGI, Válido desde, Válido hasta, Dirección fiscal. NOT for: Es retenedor. (Superseded by sprint 3.11 ADR-0034: only `name` retains the mark; the rest became optional.)

## 4. Revisión redesign

- [x] 4.1 Import `Separator` from `@/components/ui/separator` and `Badge` from `@/components/ui/badge` (both already installed; no new CLI calls). Import `format` from `date-fns` and `es` from `date-fns/locale` (already used by `date-picker.tsx`).
- [x] 4.2 Replace the existing `<div className="rounded-md border bg-muted/30 p-3 text-sm">...<dl>...</dl></div>` block with a sectioned card-layout `<div>` containing four `<section>`s: Identidad, Régimen fiscal, Autorización DGI, Dirección. Each section: an uppercase tracking-wide `<h3 className="text-xs uppercase tracking-wide text-muted-foreground mb-1.5">` heading, followed by a `<dl className="grid sm:grid-cols-2 gap-x-4 gap-y-1.5">` of stacked label-then-value pairs (label `text-xs text-muted-foreground`, value `text-sm font-medium`).
- [x] 4.3 Place a `<Separator />` between consecutive sections (three separators total).
- [x] 4.4 Render the Régimen value as `{getValues("regime") === "general" ? "General" : "Simplificado"}` (already done in the existing code; preserve).
- [x] 4.5 Render the Retenedor row's `<dd>` as `<Badge variant={getValues("is_withholder") ? "default" : "secondary"}>{getValues("is_withholder") ? "Sí" : "No"}</Badge>`.
- [x] 4.6 Render the Vigencia row as a single full-width `<div className="sm:col-span-2">` containing the two dates formatted with `format(new Date(\`${iso}T00:00:00\`), "dd MMM yyyy", { locale: es })`, joined by ` → `.

## 5. Tests

- [x] 5.1 Extend `apps/web/tests/unit/routes/tenants-new.test.tsx` with: (a) on first render of the form, asterisks (`*` inside `aria-hidden` spans) appear next to the Nombre and RUC labels; (b) submitting an empty form shows the Spanish error AFTER click (regression check on existing test still passes); (c) the Es retenedor label has NO asterisk.
- [x] 5.2 Run `pnpm -C apps/web test|typecheck|lint`. All green.

## 6. Forward-compat with sprint 3.6

- [x] 6.1 In `openspec/changes/welcome-onboarding-rename-members/tasks.md` task 12.1, add a bullet: "polish from sprint 3.10 (`polish-tenants-new-form-final`): `mode: "onTouched"`, per-field touched-or-submitted error gating, `<RequiredMark>` indicators on required labels (excluding `is_withholder`), and the four-section card-style Revisión layout with `<Badge>` for Retenedor and the Vigencia arrow row."

## 7. Smoke

- [x] 7.1 In the dev server: mount `/tenants/new`, advance through Identidad → Régimen → DGI → Address without touching Dirección fiscal, observe NO error message on Address arrival, then submit empty and observe the Spanish error appearing. Verify the Revisión panel reads cleanly: four sections, separators between, Badge on Retenedor, Vigencia on one line with Spanish month names.
