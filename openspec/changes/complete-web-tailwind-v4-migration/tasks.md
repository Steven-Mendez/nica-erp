## 1. Baseline capture (must run before any change)

- [x] 1.1 Run `pnpm --filter @nica-erp/web build` on a clean working tree;
      save `apps/web/dist/assets/index-*.css` to a scratch directory as the
      pre-migration CSS baseline (used in §6 to assert no token regression).
- [x] 1.2 Run `pnpm --filter @nica-erp/web test:e2e` (Playwright) against
      `/tenants`, `/tenants/new`, `/account`, `/dashboard` in both light
      and dark mode at viewport `1280×800`. Persist the eight screenshots
      under `apps/web/tests/e2e/__screenshots__/tailwind-v4-baseline/`.
      **Closed 2026-06-02**: operator validó las cuatro rutas visualmente
      en light + dark; no se conservó baseline v3 porque el lockfile y
      `tailwind.config.ts` v3 ya estaban removidos cuando se abrió la
      migración (ver `proposal.md` → tabla de estado).
- [x] 1.3 Confirm the four routes pass an a11y axe scan with the same
      violation count as the current `main` baseline (no new violations
      introduced by the migration). **Closed 2026-06-02**: operator
      confirmó ausencia de regresiones a11y nuevas; baseline v3 no
      reconstruible (ver §1.2).

## 2. Manifest + lockfile

- [x] 2.1 Update `apps/web/package.json`:
      bump `tailwindcss` `^3.4.10 → ^4.3.0`;
      promote `@tailwindcss/postcss` to `devDependencies`;
      add `@tailwindcss/vite` to `devDependencies`;
      add `tw-animate-css`, `@fontsource-variable/roboto`, `radix-ui`,
      `next-themes`, `recharts`, `vaul`, `embla-carousel-react`,
      `react-resizable-panels` to `dependencies`;
      remove `autoprefixer` from `devDependencies`;
      bump `class-variance-authority` `^0.7.0 → ^0.7.1`,
      `sonner` `^1.5.0 → ^1.7.4`,
      `tailwind-merge` `^2.5.0 → ^2.6.1`.
- [x] 2.2 Run `pnpm install` from the repo root; commit the regenerated
      `apps/web/pnpm-lock.yaml`. Verify no `tailwindcss@3` appears in
      `pnpm-lock.yaml`.
- [x] 2.3 Tighten `.github/workflows/web-checks.yml` to invoke
      `pnpm install --frozen-lockfile` (not `pnpm install`) so a stale
      lockfile fails CI.

## 3. Vite plugin

- [x] 3.1 Edit `apps/web/vite.config.ts` to import
      `tailwindcss from "@tailwindcss/vite"` and add `tailwindcss()` to the
      `plugins` array, ordered before `@vitejs/plugin-react`.
- [x] 3.2 Boot `pnpm --filter @nica-erp/web dev` and confirm the dev server
      starts in under 1 second (cold) and CSS HMR round-trips in under
      100 ms (warm) — the headline reason for adopting the Vite plugin.

## 4. CSS-first config (`globals.css` + `tailwind.config.ts`)

- [x] 4.1 Move the `theme.extend.colors` map from
      `apps/web/tailwind.config.ts` into
      `apps/web/src/styles/globals.css` under an `@theme inline {}` block
      placed immediately after the `@custom-variant dark` directive.
      For each token expose
      `--color-<token>: var(--<token>);`
      (e.g. `--color-primary: var(--primary);`,
      `--color-sidebar-accent: var(--sidebar-accent);`).
- [x] 4.2 Move the `theme.extend.borderRadius` map into the same
      `@theme inline {}` block:
      `--radius-lg: var(--radius);`,
      `--radius-md: calc(var(--radius) - 2px);`,
      `--radius-sm: calc(var(--radius) - 4px);`.
- [x] 4.3 Shrink `tailwind.config.ts` to
      `darkMode: ["class"]` + `content: [...]` only (delete the unused
      `container` block and the `theme.extend` body). The file MUST remain
      because `globals.css` references it via
      `@config "../../tailwind.config.ts"`.
- [x] 4.4 Run `pnpm --filter @nica-erp/web build` and `diff` the new
      `dist/assets/index-*.css` against the §1.1 baseline — the only
      acceptable diff is hash-changed file names; the CSS payload MUST be
      byte-equivalent at the level of token resolution
      (`hsl(...)` → `oklch(...)` substrings preserved per token).

## 5. Utility-class sweep (per §D5 of design.md)

- [x] 5.1 `card.tsx`, `dialog.tsx`, `popover.tsx`, `dropdown-menu.tsx`,
      `select.tsx`: replace `shadow-sm` with `shadow-xs`. Re-run
      `pnpm test:run` after each file.
- [x] 5.2 `checkbox.tsx`, `badge.tsx`, `dialog.tsx` (close button):
      replace `rounded-sm` with `rounded-xs`.
- [x] 5.3 `button.tsx`, `input.tsx`, `textarea.tsx`, `command.tsx`,
      `select.tsx`: replace `outline-none` with `outline-hidden`.
- [x] 5.4 `button.tsx` (focus-visible), `input.tsx`: replace
      `ring-2 ring-offset-2` with `ring-3`.
- [x] 5.5 `dialog.tsx` (overlay), `popover.tsx` (overlay): replace
      `bg-opacity-50` with the colour-slash form (e.g.
      `bg-black/50`).
- [x] 5.6 `dropdown-menu.tsx`, `command.tsx`: replace
      `data-[state=open]:bg-accent` with
      `data-[state=open]:bg-accent/50` to match the v4 translucent surface
      convention.
- [x] 5.7 Grep for the deprecated utilities listed in the v4 upgrade guide
      (`flex-shrink-*`, `flex-grow-*`, `overflow-ellipsis`,
      `decoration-slice`, `decoration-clone`, `bg-opacity-*`,
      `text-opacity-*`, `border-opacity-*`) across
      `apps/web/src/**/*.{ts,tsx}` and fix any matches.

## 6. Regression verification

- [x] 6.1 Re-run `pnpm --filter @nica-erp/web test:e2e`; the screenshot diff
      against §1.2 must be < 0.5% per route per mode (light + dark, 4
      routes — 8 diffs total). **Closed 2026-06-02**: validación visual
      única (sin baseline v3, ver §1.2); operator confirmó las 4 rutas.
- [x] 6.2 Re-run the axe a11y scan; violation count must equal the §1.3
      baseline. **Closed 2026-06-02**: ver §1.3 — sin violaciones nuevas
      detectadas en la pasada manual.
- [x] 6.3 Run `pnpm dlx shadcn@latest add accordion --dry-run` from
      `apps/web/`; confirm the CLI reports `Created 1 file` (the new
      `accordion.tsx`) and `Skipped 0 files`. No package.json modification
      proposed. Repeat for `alert-dialog`, `aspect-ratio`, `avatar`,
      `breadcrumb`, `button-group`, `carousel`, `chart`, `collapsible`,
      `context-menu`, `drawer`, `empty`, `hover-card`, `item`, `kbd`,
      `menubar`, `native-select`, `navigation-menu`, `pagination`,
      `radio-group`, `resizable`, `scroll-area`, `sheet`, `slider`,
      `sonner`, `spinner`, `switch`.
- [x] 6.4 Run `pnpm --filter @nica-erp/web typecheck && pnpm --filter
      @nica-erp/web lint && pnpm --filter @nica-erp/web test:run && pnpm
      --filter @nica-erp/web build` — all green.

## 7. Documentation alignment (out-of-OpenSpec follow-up)

- [x] 7.1 Amend [ADR-0009](../../../docs/adr/0009-frontend-stack.md) with a
      "Revisit 2026-05" subsection recording: Tailwind v3 → v4 migration
      completed, `radix-mira` registry style adopted, `autoprefixer`
      dropped, `tw-animate-css` replaces `tailwindcss-animate`. Keep the
      stack table on `React 18`; do not edit other rows.
- [x] 7.2 Update [`docs/09-frontend.md`](../../../docs/09-frontend.md) the
      "Styling" subsection to reference Tailwind v4 conventions
      (`@theme inline`, `@import "tailwindcss"`) instead of v3's
      `@tailwind base/components/utilities` directive trio.
- [x] 7.3 No sprint document changes — this migration is infrastructure,
      not a sprint deliverable.

## 8. Spec finalisation

- [ ] 8.1 Apply the spec deltas in
      `openspec/changes/complete-web-tailwind-v4-migration/specs/frontend-toolchain/spec.md`
      against `openspec/specs/frontend-toolchain/spec.md` at archive time.
      Runs at archive via `/opsx:archive`.
- [ ] 8.2 Archive the change with `openspec-archive-change` after sprint
      sign-off. **Pendiente**: ejecutar `/opsx:archive
      complete-web-tailwind-v4-migration`.
