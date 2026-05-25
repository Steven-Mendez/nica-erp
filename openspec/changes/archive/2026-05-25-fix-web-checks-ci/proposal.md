## Why

The `web-checks` workflow has been red on `main` since commit `1f5dcda` because `apps/web/src/lib/utils.ts` — the canonical shadcn `cn()` helper — is silently swallowed by line 17 of the root `.gitignore` (`lib/`, a leftover from the Python template) and was never committed. CI therefore cannot resolve `@/lib/utils` and `pnpm typecheck` fails on three files (`badge.tsx`, `card.tsx`, `skeleton.tsx`). The same run surfaces a second issue: the workflow files (`web-checks.yml`, `api-checks.yml`) live only on the GitHub remote (added via the UI), and they pin `actions/checkout@v4`, `actions/setup-node@v4`, and `pnpm/action-setup@v4` — all flagged by GitHub for Node 20 deprecation (Node 20 is removed from runners on 2026-09-16). We want CI green and free of deprecated dependencies before sprint 01 starts.

## What Changes

- **Reconcile `.gitignore` with the monorepo layout** — add an explicit negation so the Python-derived `lib/` rule stops swallowing `apps/web/src/lib/` (the shadcn convention).
- **Track `apps/web/src/lib/utils.ts` in git** so CI can resolve `@/lib/utils` (no source edit; the file already exists locally and is referenced by `badge.tsx`, `card.tsx`, `skeleton.tsx`, and `components.json`).
- **Upgrade every third-party GitHub Action used by CI** to the latest non-deprecated major, per Context7:
  - `actions/checkout@v4` → `@v6` (runs on node24 from v5; v6 adds credential isolation)
  - `actions/setup-node@v4` → `@v6`
  - `pnpm/action-setup@v4` → `@v6` (still installs pnpm 9 via the `version` input — lockfile compatibility preserved)
  - `astral-sh/setup-uv@v3` → `@v8` (not on GitHub's Node 20 deprecation list — it's a composite action — but five majors behind; the user policy is "nothing stale")
- **No source/feature changes**, no Python changes, no new dependencies. The fix is entirely in `.gitignore`, `.github/workflows/`, and one git-add of an already-authored file.

## Capabilities

### New Capabilities
<!-- none — this is a fix to an existing capability -->

### Modified Capabilities
- `frontend-toolchain`: tighten the Continuous Integration requirement to pin non-deprecated action versions and to commit the workflow file in the repo (not the GitHub UI); add a requirement that `.gitignore` MUST NOT swallow `apps/web/src/lib/`.

## Impact

- **Code**: `.gitignore` (one negation appended), `.github/workflows/web-checks.yml` and `.github/workflows/api-checks.yml` (action-version bumps only, no other changes), and `apps/web/src/lib/utils.ts` (now tracked).
- **APIs**: none.
- **Dependencies**: none added. The pnpm version stays at 9 (matches `packageManager: "pnpm@9.15.0"` in `package.json` and the existing `pnpm-lock.yaml`).
- **Systems**: GitHub Actions only. The next push to `main` runs the new workflow file (locally tracked) and the Node 20 deprecation banner disappears. No deploy, no infrastructure change (still under [ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md)).
