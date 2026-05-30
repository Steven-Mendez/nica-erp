## 1. Sprint doc

- [x] 1.1 Append a "Sprint follow-up — `/tenants/new` form ergonomics (sprint 3.8, 2026-05-27)" section to `docs/sprints/03-tenants-and-rls.md` after the existing 3.7 follow-up. Cover: motivation (5 UX defects + Spanish errors + 422 surfacing), scope (only `/tenants/new` + schema file + new municipalities constant), non-goals (no date picker, no wizard restructure, no backend changes).

## 2. Install shadcn primitives

- [x] 2.1 From `apps/web/`, run `pnpm dlx shadcn@latest add select checkbox tooltip`. Confirm three new files in `components/ui/` and three new `@radix-ui/*` deps in `package.json`.

## 3. Catalog + schema

- [x] 3.1 Create `apps/web/src/features/tenants/municipalities.ts` exporting `MUNICIPALITIES` (17 entries: Managua, León, Granada, Masaya, Estelí, Matagalpa, Chinandega, Jinotega, Nueva Segovia, Madriz, Boaco, Carazo, Chontales, Rivas, Río San Juan, RAAN, RAAS) as a `readonly` tuple, plus `type Municipality = (typeof MUNICIPALITIES)[number]`.
- [x] 3.2 Edit `apps/web/src/features/tenants/schemas/index.ts`: add Spanish `{ message }` to every constraint (`name`, `ruc`, `municipality`, `authorization_dgi.number`, `authorization_dgi.valid_from`, `authorization_dgi.valid_to`, `fiscal_address`, `email`, `proposed_role`, `role`). Replace `municipality: z.string().min(1)` with `municipality: z.enum(MUNICIPALITIES, { message: "..." })`.

## 4. Migrate /tenants/new

- [x] 4.1 In `apps/web/src/routes/tenants/new.tsx`, wrap the route root `<div>` in `<TooltipProvider delayDuration={300}>`.
- [x] 4.2 Replace `<select id="regime">` block with `<Select value={...} onValueChange={...}>` + `<SelectTrigger><SelectValue/></SelectTrigger>` + `<SelectContent>` containing two `<SelectItem value="general">General</SelectItem>` / `<SelectItem value="simplified">Simplificado</SelectItem>`. Wire via `Controller` (Select is not a native `<select>`, so `register` won't bind properly).
- [x] 4.3 Replace the Municipio `<Input>` with `<Select>` over `MUNICIPALITIES.map(m => <SelectItem value={m} key={m}>{m}</SelectItem>)`. Wire via `Controller`.
- [x] 4.4 Replace `<input type="checkbox">` for `is_withholder` with `<Checkbox id="is_withholder" checked={...} onCheckedChange={...}>` + `<Label htmlFor="is_withholder">Es retenedor</Label>`. Wire via `Controller`.
- [x] 4.5 Next to the labels of Régimen, Municipio, DGI número, and Es retenedor, render an `<Info>` (`lucide-react`) icon inside `<Tooltip><TooltipTrigger><Info className="size-3.5 text-muted-foreground" /></TooltipTrigger><TooltipContent>{copy}</TooltipContent></Tooltip>`. Copies as specified in the spec.

## 5. Surface backend validation errors

- [x] 5.1 In `apps/web/src/routes/tenants/new.tsx`'s `createMut` `onError` handler, when `err instanceof ApiError && err.status === 422`, walk `err.detail` (expected shape: `{ detail: [{ loc, msg, type }, ...] }`), pick the first item, map `loc[1]` to a Spanish field label (`name`→"Nombre", `ruc`→"RUC", `regime`→"Régimen", `municipality`→"Municipio", `authorization_dgi.number`→"Número DGI", `authorization_dgi.valid_from`→"Vigencia desde", `authorization_dgi.valid_to`→"Vigencia hasta", `fiscal_address`→"Dirección fiscal", `is_withholder`→"Es retenedor"), and set `errorMsg` to `${label}: ${msg}`. Fall back to "No se pudo crear la organización. Revisa los datos e intenta de nuevo." when detail is missing or unparseable. Import `ApiError` from `@/features/tenants/api/endpoints`.

## 6. Tests

- [x] 6.1 Add `apps/web/tests/unit/routes/tenants-new.test.tsx`: (a) renders Identidad step, (b) shows Spanish error for empty name on submit, (c) Régimen Select renders both options after advancing, (d) Municipio Select renders 17 options, (e) is_withholder Checkbox toggles and form value updates, (f) Tooltip on Es retenedor surfaces the explanation copy on hover.
- [x] 6.2 Run `pnpm -C apps/web test`, `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`. All three must pass.

## 7. Forward-compat with sprint 3.6

- [x] 7.1 Append to `openspec/changes/welcome-onboarding-rename-members/tasks.md` a `Carry over /tenants/new improvements from add improve-tenants-new-form` task that lists: preserve shadcn Select for régimen/municipio, Checkbox for is_withholder, Tooltips on fiscal-jargon fields, Spanish Zod messages, and the `MUNICIPALITIES` constant. Sprint 3.6's `/organizations/new` rewrite MUST start from a copy of the new `/tenants/new` body.

## 8. Smoke

- [x] 8.1 In the dev server, complete the wizard end-to-end: typing a non-catalog municipality should be impossible (Select), Spanish errors render on each empty step, the Es retenedor tooltip surfaces on hover, and on submit a backend 422 (force one by, e.g., editing the request to ship `regime: "wrong"`) surfaces the field-specific Spanish error in the wizard `<Alert>`.
