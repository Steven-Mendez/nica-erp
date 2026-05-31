# ADR-0009 — Frontend stack: React + TanStack + Vite + shadcn/ui

**Status**: Accepted
**Date**: 2026-05-23

## Context
The ERP needs a UI for administrative staff at SMBs — dense tables, long forms, reasonable accessibility, low bundle for CloudFront serving Nicaragua over mobile connections. A single dev needs a stable, well-supported stack (no beta/RC for primary components) and tight integration with the rest of the AWS-only operating model.

This ADR consolidates three decisions that were originally separate (framework choice, bundler choice, component library choice). They all answer the same question — what does the frontend look like — and split made cross-referencing brittle.

## Decision
**One frontend stack, fully under repo control, served as a static SPA from S3 behind CloudFront in the same `us-east-1` account.**

| Layer | Choice |
|---|---|
| Language | TypeScript 5.x, `strict` mode |
| UI framework | React 18 |
| Router | TanStack Router |
| Data | TanStack Query |
| Tables | TanStack Table |
| Forms | TanStack Form |
| Styling | Tailwind CSS |
| Components | shadcn/ui (Radix + Tailwind) — copied into `apps/web/src/components/ui/`, not an npm dependency |
| Icons | lucide-react |
| Toasts | sonner |
| Validation | Zod |
| HTTP client | Generated from OpenAPI via `pnpm gen:api` |
| Bundler | Vite 5 (esbuild in dev, Rollup at build) |
| Test runner | Vitest |
| Hosting | S3 (private bucket, OAC) + CloudFront default `*.cloudfront.net` ([ADR-0020](0020-no-custom-domain-mvp.md)) |

The frontend lives in `apps/web/`. Behavior: CloudFront serves `/*` → S3 (SPA) and `/api/*` → ALB origin, so the frontend calls `/api` on the same origin (`VITE_API_BASE_URL=/api`), no CORS. Detail in [`../09-frontend.md`](../09-frontend.md).

## Consequences
- (+) Consumable product, not just an HTTP contract.
- (+) Every primary component is stable (no beta/RC).
- (+) End-to-end typing — generated client closes the contract gap.
- (+) Bundle stays small — Tailwind purge + tree-shaken Rollup output; only imported shadcn components ship.
- (+) Single AWS account, one Terraform module owns the SPA; idle ≈ $0.02/month.
- (+) The SPA still serves when the backend is destroyed (HTML loads; `/api/*` calls fail gracefully).
- (+) Vite dev server cold-start < 1s, HMR < 100ms.
- (+) `vite.config.ts` fits in ~30 lines.
- (−) Two stacks in the repo (Python + TS) — mitigated by the `apps/api` vs `apps/web` split.
- (−) shadcn updates are manual — Radix fixes do not arrive automatically. Acceptable: explicit cost in exchange for no forced framework migrations.
- (−) No SSR (intentional — the audience is authenticated). If SSR is ever needed, TanStack Start is the upgrade path, but it stays out of scope until pre-1.0 risk clears.
- (−) First CloudFront provision takes minutes (one-time).

## Alternatives

### Framework
- **TanStack Start** — rejected: pre-1.0 at decision time; reconsider when stable.
- **Next.js** / **Remix** — rejected: bring opinionated routing/data layers that conflict with the TanStack line.
- **React 19** — rejected: TanStack and shadcn compatibility lagged at decision time.

### Bundler
- **Webpack 5** — rejected: heavy config, slow dev server, weaker HMR.
- **Parcel 2** — rejected: smaller ecosystem.
- **Turbopack** — rejected: pre-1.0 outside Next.js; ties to Vercel ecosystem.
- **esbuild direct** / **Rsbuild** — rejected: smaller plugin ecosystems for TanStack/shadcn.

### Component library
- **Material-UI / Chakra / Ant Design / Bootstrap** — rejected: theming systems collide with Tailwind, bundles too large.
- **Radix primitives without shadcn** — rejected: would need Button/Input/Card written from scratch (which is what shadcn does).
- **Headless UI** — rejected: smaller catalog than Radix.

### Hosting
- **Vercel / Cloudflare Pages** — rejected: external dependency outside the one-AWS-account canon.

## Revisit triggers
- A second product surface (mobile app, marketing site) appears — re-evaluate whether SSR or a different framework better matches.
- React 19 + TanStack/shadcn alignment lands — opportunistic upgrade window.
- shadcn manual-update cost crosses a budget (e.g., > 4 hours/quarter) — consider a maintained library.
- First tenant with measured TTI > 3s on 3G — re-examine bundle, lazy boundaries, or CDN edge selection.

## Revisit 2026-05 — Tailwind v4 + shadcn v4 alignment

The stack table above stays accurate (still React 18, still TanStack, still Vite, still shadcn copied into `apps/web/src/components/ui/`), but four pieces of the Styling row moved underneath it:

- **Tailwind CSS v3 → v4.** The build pipeline switched from `postcss + autoprefixer + @tailwindcss/postcss` to the native `@tailwindcss/vite` plugin. `postcss.config.js`, `autoprefixer`, and the standalone `postcss` devDep are gone; vendor prefixing is now handled by Lightning CSS inside the Tailwind plugin.
- **CSS-first theme config.** The colour and `borderRadius` maps that used to live in `tailwind.config.ts` `theme.extend` now live in a `@theme inline {}` block in `src/styles/globals.css`. `tailwind.config.ts` is reduced to `darkMode + content` and kept only because globals.css references it via `@config`.
- **shadcn `radix-mira` registry style.** `components.json` pins `style: "radix-mira"` and `baseColor: "olive"`. New primitives (accordion, sheet, pagination, table, chart, drawer, carousel, resizable, sonner) are added on demand and bring their unbundled `radix-ui` peer with them.
- **`tailwindcss-animate` → `tw-animate-css`.** The original plugin was deprecated in March 2025; v4 uses a CSS-import (`@import "tw-animate-css"`) instead of `@plugin "tailwindcss-animate"`.

OKLCH dark-mode tokens (`oklch(L C h)`) were already in place before this migration and are preserved unchanged; the byte-equivalence check at migration time confirmed all 27 colour tokens resolve identically in the generated CSS.

Out of scope, kept for a future revisit: shadcn step 6 (`forwardRef` → `React.ComponentProps`) blocks on the React 18 → 19 upgrade trigger above.
