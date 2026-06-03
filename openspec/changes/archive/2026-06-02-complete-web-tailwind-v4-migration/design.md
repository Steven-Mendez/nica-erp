# Design — Complete web Tailwind v4 migration

## Context

The frontend baseline established by
[ADR-0009](../../../docs/adr/0009-frontend-stack.md) pinned Tailwind v3 in
May 2026. Between sprint 02 and sprint 03 a partial migration to Tailwind v4
was performed (likely while bootstrapping the `radix-mira` style from the
shadcn v4 registry) but was never landed end-to-end: the CSS, PostCSS plugin,
and components.json moved to v4, while `package.json` and
`tailwind.config.ts` remained on v3. This change closes the gap.

The trigger that exposed the gap was an operator-driven
`pnpm dlx shadcn@latest add ...` invocation that attempted to install
twenty-nine missing primitives. The shadcn CLI detected the v4 registry style
in `components.json`, ran its built-in "ensure v4" preflight, and proposed a
sweeping `package.json` rewrite (Tailwind v3 → v4, plus seven new runtime
deps) as well as overwriting twenty-three already-present primitives. The
overwrite was reverted before commit; the underlying inconsistency it
revealed is what this change repairs.

Authoritative sources consulted:

- [Tailwind CSS v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide) —
  the `@tailwindcss/upgrade` codemod, the `@import "tailwindcss"` directive,
  the PostCSS/Vite plugin split, and the renamed-utility matrix.
- [shadcn/ui Tailwind v4 guide](https://ui.shadcn.com/docs/tailwind-v4) —
  the `@theme inline` CSS-first config pattern, the `tw-animate-css`
  replacement for `tailwindcss-animate`, the `data-slot` attribute
  convention, and the React 19 forwardRef removal (deferred — see
  Non-goals in [proposal.md](./proposal.md)).
- [shadcn/ui v4 migration discussion #2996](https://github.com/shadcn-ui/ui/discussions/2996) —
  community-reported gotchas: CLI validator briefly demanding a v3 config to
  exist, `sidebar` requiring manual patches, chart color-variable
  adjustments, and `border-border` utility breakage if `@theme inline` is
  not wired correctly.

## Goals / Non-Goals

**Goals**

- A fresh checkout that runs `pnpm install` produces a deterministic
  lockfile resolving `tailwindcss@4.3.x` and no `tailwindcss@3.x` anywhere
  in the dependency tree.
- `pnpm build` produces a CSS bundle that paints the four authenticated
  routes identically to the pre-migration baseline (Playwright screenshot
  diff < 0.5% per route).
- `pnpm dlx shadcn@latest add accordion --dry-run` (and the same for
  twenty-eight other components listed in proposal §What Changes) reports
  zero modifications to pre-existing files.
- The frontend-toolchain spec is updated to lock the v4 contract so a
  future change cannot silently regress it.

**Non-goals**

- React 19 (covered separately when ADR-0009 revisit triggers fire).
- Replacing the OKLCH palette (the current palette is already v4-ready).
- Bringing `apps/web/src/components/ui/*` to the v4-canonical
  `data-slot` + named-function pattern. The existing forwardRef pattern
  keeps working under v4; only utility-class breaking changes are
  addressed here.

## Decisions

### D1. CSS-first config with `@theme inline`

`@theme inline { --color-primary: var(--primary); ... }` lets us keep the
`oklch(...)` values declared once in `:root`/`.dark` while exposing them as
Tailwind utilities. The `inline` variant is required so the value substitutes
at build time and remains overridable at runtime via the same CSS variable —
matching the dark-mode switch behavior we already rely on.

The JS config (`tailwind.config.ts`) shrinks to `darkMode: ["class"]` +
`content: [...]`. We keep the JS file rather than deleting it so the
`@config "../../tailwind.config.ts"` directive in `globals.css` stays valid;
removing the directive triggers a wave of editor warnings in VS Code's
Tailwind extension.

### D2. Vite plugin + PostCSS plugin in parallel

`@tailwindcss/vite` is the official recommendation for Vite projects (~3×
faster dev CSS HMR), but `@tailwindcss/postcss` must remain registered to
participate in the production `vite build` content-scan + minification step.
Both plugins peacefully coexist — Vite uses the Vite plugin in dev and falls
back to PostCSS at build.

### D3. Keep `radix-mira` registry style

`components.json` declares `style: "radix-mira"`. This is the v4-only
registry namespace the operator selected when bootstrapping the project.
Switching to `default` or `new-york` would require regenerating every
component file (and reverts the design decisions encoded in the OKLCH
palette). The cost of keeping `radix-mira` is one new transitive dep
(`radix-ui` mono-package) which we're already adopting for sidebar/chart.

### D4. Lockfile regeneration in CI

After this change merges, CI must run `pnpm install --frozen-lockfile`
against a clean cache to confirm reproducibility. The `web-checks.yml`
workflow already runs `pnpm install` — we tighten it to
`--frozen-lockfile` as a guard.

### D5. Breaking-change utility sweep

The `shadcn add --overwrite` install captured a candid v4 rewrite of every
primitive — we mined that overwrite (now reverted) to enumerate the
utility-class deltas the CLI applied to existing components:

| v3 utility | v4 replacement | Files touched |
|---|---|---|
| `shadow-sm` | `shadow-xs` | card, dialog, popover, dropdown-menu, select |
| `rounded-sm` | `rounded-xs` | checkbox, badge, dialog (close button) |
| `outline-none` | `outline-hidden` | button, input, textarea, command, select |
| `ring-2 ring-offset-2` | `ring-3` | button (focus-visible), input |
| `bg-opacity-50` | `bg-black/50` | dialog (overlay), popover (overlay) |
| `data-[state=open]:bg-accent` | `data-[state=open]:bg-accent/50` | dropdown-menu, command (matches new translucent surface) |

The sweep is mechanical — one edit per file, one utility at a time, with the
existing Vitest snapshot tests catching regressions.

### D6. Sidebar primitive deferred

`components/ui/sidebar.tsx` requires manual patches per
[shadcn discussion #2996](https://github.com/shadcn-ui/ui/discussions/2996).
We do not install it in this change. The project already has a hand-rolled
`components/app-sidebar/sidebar.tsx` (per
[`docs/09-frontend.md` §App shell](../../../docs/09-frontend.md#app-shell))
that does not depend on the shadcn primitive — the dashboard shell change
[`add-frontend-dashboard-shell`](../add-frontend-dashboard-shell/proposal.md)
already specified this. The v4-finished registry merely unblocks future
installation if we change our minds.

## Risks

- **Risk**: a downstream component imports a utility class that v4 silently
  no-ops (e.g. `flex-shrink-0`). **Mitigation**: the upgrade codemod
  (`npx @tailwindcss/upgrade`) catches these; we run it against
  `apps/web/src/**/*.{ts,tsx}` and inspect the diff before commit.
- **Risk**: `tw-animate-css` plays animations that the prior `tailwindcss-animate` did
  not, causing visual drift on the dialog/popover open-state. **Mitigation**:
  Playwright screenshot diff baseline captured before the migration and
  asserted < 0.5% per route after.
- **Risk**: the `@config` directive becomes unsupported in a future Tailwind
  v4.x. **Mitigation**: tracked in ADR-0009 revisit triggers; if we drop the
  JS config entirely the `darkMode` and `content` declarations move into
  `globals.css` via `@source` + `@variant`.

## Migration order

The change is structured so each step lands as a single commit (small enough
to revert atomically if it surfaces a regression):

1. `package.json` deps + lockfile regen (no behavior change yet — CSS already v4).
2. `vite.config.ts` plugin add (HMR speedup, no functional change).
3. `tailwind.config.ts` shrink + `globals.css` `@theme inline` block
   (semantic equivalence; visual diff must be empty).
4. Utility-class sweep across `components/ui/*.tsx` (per the D5 matrix).
5. `web-checks.yml` tightened to `--frozen-lockfile`.
6. Spec update in `openspec/specs/frontend-toolchain/spec.md` (the delta in
   this change archives).
