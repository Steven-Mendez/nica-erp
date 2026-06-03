## MODIFIED Requirements

### Requirement: Tailwind is wired to shadcn theme tokens

`apps/web/tailwind.config.ts` MUST enable `darkMode: ["class"]` and
content-scan `./index.html` and `./src/**/*.{ts,tsx}`. The file MUST NOT
declare a `theme.extend.colors` or `theme.extend.borderRadius` map; under
Tailwind v4 those tokens are declared in `apps/web/src/styles/globals.css`
inside an `@theme inline {}` block (see the "Global stylesheet" requirement
below). The file is preserved as a JS module solely so the `@config` directive
in `globals.css` resolves; deleting it triggers Tailwind extension warnings
in editors and removes the future migration affordance for `content`-scan
edge cases.

PostCSS MUST load `@tailwindcss/postcss` (v4 plugin package) and MUST NOT
load `tailwindcss` directly or `autoprefixer` separately — both are folded
into the v4 plugin. Vite MUST additionally register `@tailwindcss/vite` in
its `plugins` array (ordered before `@vitejs/plugin-react`) so dev-mode CSS
HMR bypasses PostCSS for the recommended speedup.

#### Scenario: Production CSS resolves theme tokens through CSS variables

- **WHEN** `pnpm build` produces `dist/assets/index-*.css`
- **THEN** the bundle contains `oklch(...)` color values bound to the
  semantic tokens (`--primary`, `--secondary`, `--card`, `--border`,
  `--ring`, `--sidebar`, `--chart-1`..`--chart-5`) and is free of any
  `hsl(var(--...))` substring (the v3 wrapper pattern has been removed)

#### Scenario: Dark mode is class-gated

- **WHEN** a developer adds `class="dark"` to a parent element
- **THEN** Tailwind switches to dark-mode utilities driven by the
  `@custom-variant dark (&:where(.dark, .dark *))` directive in
  `globals.css`, and the `.dark` block overrides the variable values

#### Scenario: Vite plugin is registered before React plugin

- **WHEN** `apps/web/vite.config.ts` is loaded
- **THEN** the `plugins` array contains `@tailwindcss/vite` at an index
  strictly less than `@vitejs/plugin-react`, so Tailwind processes CSS
  before React hot-replacement boundaries are computed

#### Scenario: autoprefixer is not declared

- **WHEN** `apps/web/package.json#devDependencies` is read
- **THEN** the `autoprefixer` key is absent; vendor-prefixing happens
  inside `@tailwindcss/postcss` and a separate declaration is redundant

### Requirement: shadcn primitives are themed and located under `components/ui/`

`apps/web/components.json` MUST declare `style: "radix-mira"` (the v4-only
registry namespace adopted in May 2026), `tsx: true`,
`tailwind.config: "tailwind.config.ts"`,
`tailwind.css: "src/styles/globals.css"`, `baseColor: "olive"`,
`cssVariables: true`, `aliases.components: "@/components"`, and
`aliases.utils: "@/lib/utils"`. The file MUST NOT declare `$schema`. The
sprint-00 deliverables MUST ship at least the `Card`, `Badge`, and
`Skeleton` primitives under `apps/web/src/components/ui/`, each adapted to
the project's `forwardRef` + `HTMLAttributes` pattern. Card surface
utilities MUST use `bg-card text-card-foreground border` (not hard-coded
`bg-white text-slate-*`). The Badge component MUST expose the default
shadcn variants (`default`, `secondary`, `destructive`, `outline`) and
SHOULD additionally expose semantic variants `ok`, `warn`, `danger` for
status presentation. The Skeleton component MUST render a
`<div data-slot="skeleton">` with the base classes
`animate-pulse rounded-md bg-muted` and accept a `className` override that
callers use to set `h-*`/`w-*`/`inline-block` at the use site. The
`cn(...)` helper MUST live at `apps/web/src/lib/utils.ts` and combine
`clsx` + `tailwind-merge`.

#### Scenario: components.json points the shadcn CLI at the right files

- **WHEN** a future sprint runs `pnpm dlx shadcn@latest add <component>`
  against the v4 registry
- **THEN** the CLI reads `components.json`, resolves the `radix-mira`
  style, writes the new primitive under `@/components/ui/`, and uses
  `@/lib/utils#cn` for class merging

#### Scenario: dry-run install of a missing primitive proposes no overwrites

- **WHEN** `pnpm dlx shadcn@latest add accordion --dry-run` is invoked
  from `apps/web/`
- **THEN** the CLI reports `Created 1 file` for `accordion.tsx`, reports
  `Skipped 0 files`, and does NOT propose any modification to
  `package.json`, `tailwind.config.ts`, `postcss.config.js`, or any
  pre-existing component file

#### Scenario: Card uses theme tokens

- **WHEN** `<Card>` is rendered
- **THEN** the produced className contains `bg-card`,
  `text-card-foreground`, and `border` (no `bg-white` or `text-slate-900`
  literals)

#### Scenario: Badge offers semantic state variants

- **WHEN** `<Badge variant="ok">` and `<Badge variant="danger">` are used
- **THEN** the rendered className differs (e.g. emerald vs red palette)
  and TypeScript infers the variant from the `cva` definition

### Requirement: Global stylesheet defines light and dark token sets

`apps/web/src/styles/globals.css` MUST load Tailwind via
`@import "tailwindcss"` (the v4 import directive — the v3 trio
`@tailwind base/components/utilities` MUST NOT appear). It MUST also import
`tw-animate-css` and `@fontsource-variable/roboto`. It MUST declare a
`@custom-variant dark (&:where(.dark, .dark *))` directive and point at the
JS config via `@config "../../tailwind.config.ts"`.

The file MUST declare an `@theme inline {}` block that exposes every
semantic token as a Tailwind colour utility by binding to the corresponding
CSS variable — at minimum: `--color-background`, `--color-foreground`,
`--color-card`, `--color-card-foreground`, `--color-popover`,
`--color-popover-foreground`, `--color-primary`, `--color-primary-foreground`,
`--color-secondary`, `--color-secondary-foreground`, `--color-muted`,
`--color-muted-foreground`, `--color-accent`, `--color-accent-foreground`,
`--color-destructive`, `--color-destructive-foreground`, `--color-success`,
`--color-success-foreground`, `--color-warning`, `--color-warning-foreground`,
`--color-border`, `--color-input`, `--color-ring`, `--color-sidebar`,
`--color-sidebar-foreground`, `--color-sidebar-primary`,
`--color-sidebar-primary-foreground`, `--color-sidebar-accent`,
`--color-sidebar-accent-foreground`, `--color-sidebar-border`,
`--color-sidebar-ring`, `--color-chart-1` through `--color-chart-5`. The
block MUST also expose `--radius-lg: var(--radius)`,
`--radius-md: calc(var(--radius) - 2px)`,
`--radius-sm: calc(var(--radius) - 4px)`.

Under `@layer base`, the `:root` selector MUST define `oklch(...)` values
for every token consumed by the `@theme inline` block. A `.dark` selector
MUST override the same set with a dark palette. The base layer MUST apply
`border-border outline-ring/50` to every element and
`bg-background text-foreground antialiased` to `<body>`.

#### Scenario: Base layer paints the body

- **WHEN** the application is rendered in a browser
- **THEN** the body computes its background from the `--background` OKLCH
  value and its colour from the `--foreground` OKLCH value without any
  utility classes on the `<body>` element

#### Scenario: v3 directive trio is absent

- **WHEN** `apps/web/src/styles/globals.css` is read
- **THEN** the file contains zero occurrences of the substrings
  `@tailwind base`, `@tailwind components`, or `@tailwind utilities`, and
  the file's first non-empty line is `@import "tailwindcss";`

#### Scenario: @theme inline block exists and binds every semantic token

- **WHEN** the migration is complete
- **THEN** `globals.css` contains an `@theme inline { ... }` block whose
  body defines `--color-<token>` declarations covering all the tokens
  enumerated in the requirement body (a future test asserts this with a
  regex grep)
