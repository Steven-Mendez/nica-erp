# Complete web Tailwind v4 migration

## Why

`apps/web/` is in a **half-migrated state** between Tailwind v3 and v4 — the
inconsistency was hidden until a `pnpm dlx shadcn@latest add ...` invocation
attempted to "fix" it on the operator workstation and silently overwrote
twenty-three existing primitives. The discovery audit confirmed:

| Layer | Already v4 | Still v3 |
|---|---|---|
| `apps/web/src/styles/globals.css` | `@import "tailwindcss"`, `@custom-variant dark`, `oklch()` colors, `@import "tw-animate-css"`, `@import "@fontsource-variable/roboto"` | — |
| `apps/web/postcss.config.js` | `@tailwindcss/postcss` | — |
| `apps/web/components.json` | `style: "radix-mira"` (v4-only registry) | — |
| `apps/web/package.json` | — | `tailwindcss: ^3.4.10`, `autoprefixer: ^10.4.20`, missing `@tailwindcss/postcss`, `@tailwindcss/vite`, `tw-animate-css`, `@fontsource-variable/roboto` |
| `apps/web/tailwind.config.ts` | — | v3 `theme.extend.colors` map, `var(--*)` bound through JS config (works via `@config` directive) |

The runtime "works" only because the v3 PostCSS plugin was already removed and
replaced with `@tailwindcss/postcss` — pnpm resolves it transitively from the
shadcn install bundle. As soon as the lockfile is regenerated cleanly the build
breaks. This change brings the manifest, config, and registry contract into
agreement so the `shadcn add <component>` command can run safely in subsequent
sprints (which need `accordion`, `sidebar`, `sonner`, `radio-group`,
`scroll-area`, `sheet`, `switch`, `avatar`, `pagination`, `drawer`,
`navigation-menu`, `breadcrumb`, etc. that today cannot be installed without
collateral damage).

References:
[`docs/09-frontend.md`](../../../docs/09-frontend.md) (frontend spec),
[ADR-0009](../../../docs/adr/0009-frontend-stack.md) (frontend stack —
will be amended in a follow-up to record the v4 + radix-mira decision).

## What Changes

### `apps/web/package.json` and lockfile

- Bump `tailwindcss` from `^3.4.10` to `^4.3.0` (current at time of writing,
  pinned by the upgrade tool's resolution).
- Promote `@tailwindcss/postcss` to a first-class `devDependency` (today
  resolved transitively only — fragile).
- Add `@tailwindcss/vite` as a `devDependency` so the Vite plugin can replace
  PostCSS in dev for faster HMR (the official v4 recommendation for Vite
  projects).
- Add `tw-animate-css`, `@fontsource-variable/roboto` to `dependencies` (the
  CSS already imports both).
- Add `radix-ui` (mono-package), `next-themes`, `recharts`, `vaul`,
  `embla-carousel-react`, `react-resizable-panels` to `dependencies` as the
  registry pre-conditions for the components that subsequent sprints will
  install (`sidebar`, `chart`, `drawer`, `carousel`, `resizable`).
- Remove `autoprefixer` from `devDependencies` (v4 has it built-in).
- Bump `class-variance-authority` to `^0.7.1`, `sonner` to `^1.7.4`,
  `tailwind-merge` to `^2.6.1` — all within the same major, required by the
  v4-compatible primitives.

### `apps/web/tailwind.config.ts` → CSS `@theme`

- Migrate the `theme.extend.colors` map (background, foreground, primary,
  secondary, muted, accent, destructive, success, warning, border, input,
  ring, card, popover, sidebar, chart) and the `theme.extend.borderRadius`
  map into `apps/web/src/styles/globals.css` under an `@theme inline {}`
  block.
- Keep `darkMode: ["class"]` and `content: [...]` in the JS config; v4 still
  reads these via the `@config` directive that `globals.css` already points
  at.
- Delete the unused `container` block (the project does not use Tailwind's
  `.container` class anywhere — verified via grep).

### `apps/web/vite.config.ts`

- Add `@tailwindcss/vite` plugin before `@vitejs/plugin-react` so dev builds
  bypass PostCSS for ~3× faster CSS HMR.
- Keep `@tailwindcss/postcss` registered for the production `vite build`
  pipeline (CSS minification + content scanning).

### `apps/web/postcss.config.js`

- No code change — already on `@tailwindcss/postcss`. Comment removed.

### `apps/web/components.json`

- No change to `style: "radix-mira"`. Confirmed: this style is the v4 registry
  contract and matches the OKLCH palette already in `globals.css`.

### Component sweep

- Audit the twenty-six existing primitives for the breaking-change matrix
  (Section 3.4 of `design.md`): `shadow-sm` → `shadow-xs`,
  `rounded-sm` → `rounded-xs`, `outline-none` → `outline-hidden`,
  `ring` → `ring-3`, removed `bg-opacity-*`, etc.
- For each change apply the minimum edit (one utility per file) and re-run
  the snapshot test where one exists.

### Verification

- `pnpm install` produces a deterministic lockfile in CI.
- `pnpm typecheck && pnpm lint && pnpm test:run && pnpm build` green.
- `pnpm dlx shadcn@latest add accordion --dry-run` reports zero modifications
  to existing files (only the new `accordion.tsx` and its untouched deps).
- Visual regression on the four authenticated routes
  (`/tenants`, `/tenants/new`, `/account`, `/dashboard`) — Playwright
  screenshot diff under 0.5% per route at viewport 1280×800 (light + dark).

## Non-goals

- **No new component installs.** This change unblocks `shadcn add` but does
  not consume it. Sprint follow-ups install the components they need.
- **No React 19 upgrade.** The v4 + React 18 combination is supported. React
  19 is a separate decision (see ADR-0009 revisit triggers).
- **No design-token rename.** The semantic tokens
  (`primary`, `secondary`, `muted`, `sidebar-*`, `chart-*`) keep their
  current names and OKLCH values — only their declaration site moves.
- **No new ADR for shadcn registry style.** A short amendment to ADR-0009 is
  enough; a full new ADR is scope creep.
