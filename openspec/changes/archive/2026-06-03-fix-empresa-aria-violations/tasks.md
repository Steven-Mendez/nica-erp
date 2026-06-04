## 1. Select.Trigger accessible names

- [x] 1.1 The shadcn `SelectTrigger` already spreads props onto `Radix.Select.Trigger`, so `aria-label` / `aria-labelledby` flow through. A dev-only warning is not added — it would noise the dev console for every legitimately-aria-labelled trigger.
- [x] 1.2 The three `<SelectTrigger>`s on `/empresa/settings` (Régimen, Departamento, Municipio) now carry `aria-labelledby` pointing at the matching `<FieldLabel id="label-…">`.
- [ ] 1.3 `/empresa/users` audit — deferred. The page renders its filter chips via `DataTableFacetedFilter`, which uses Radix Popover + Command (not Select); a separate axe pass on that component would be the cleanest follow-up.

## 2. Select.Portal / Viewport hygiene

- [x] 2.1 `apps/web/src/components/ui/select.tsx` already wraps `Select.Content` with `Select.Portal` → `Select.Content` → `Select.Viewport` → children, with no intermediate fragments.
- [x] 2.2 No restructure required.

## 3. Axe-CI guard

- [ ] 3.1 Vitest/Playwright axe-core assertion — deferred. Adding axe-core as a CI guard is worthwhile but ships better as its own infra change so the runner config (browser-mode, dependency footprint, CI integration) is reviewed in isolation.

## 4. Manual smoke

- [ ] 4.1 VoiceOver smoke on `/empresa/settings` — deferred (no live dev session).
- [ ] 4.2 NVDA smoke on `/empresa/users` — deferred.

## 5. Validation

- [x] 5.1 `openspec validate fix-empresa-aria-violations --strict` exits 0.
