## Context

`web-checks` has been red on `main` since commit `1f5dcda` (run 26422639639):

```
##[error]src/components/ui/badge.tsx(4,20): error TS2307: Cannot find module '@/lib/utils' or its corresponding type declarations.
##[error]src/components/ui/card.tsx(3,20): error TS2307: Cannot find module '@/lib/utils' or its corresponding type declarations.
##[error]src/components/ui/skeleton.tsx(3,20): error TS2307: Cannot find module '@/lib/utils' or its corresponding type declarations.
```

The file exists locally at `apps/web/src/lib/utils.ts` (the shadcn `cn()` helper from `tasks.md` 2.4 of the walking-skeleton change) but `git ls-files apps/web/src/lib/` returns nothing — `.gitignore` line 17 declares `lib/`, inherited verbatim from the Python `Distribution / packaging` template (it sits next to `build/`, `dist/`, `wheels/`, `*.egg-info/`). `git check-ignore -v apps/web/src/lib/utils.ts` confirms the line that wins. The result: locally everything resolves through `paths: { "@/*": ["./src/*"] }`; on a fresh checkout (CI, new contributor) the file is absent and `tsc` cannot type the `cn()` import.

The same workflow run emits an unrelated but pressing warning:

> Node.js 20 actions are deprecated. The following actions are running on Node.js 20: actions/checkout@v4, actions/setup-node@v4, pnpm/action-setup@v4. … Node.js 20 will be removed from the runner on September 16th, 2026.

Per Context7 the current majors are:
- `actions/checkout@v6` (v5 introduced node24, v6 added a credentials-isolation tweak with no workflow-side change)
- `actions/setup-node@v6`
- `pnpm/action-setup@v6`

Both workflow files are already tracked in the repo (`git ls-files .github/workflows/` returns both); they were authored as part of the walking-skeleton change but pin the deprecated action majors. The bump is purely a content edit — no new files, no path changes.

## Goals / Non-Goals

**Goals:**
- Turn `web-checks` green on `main` on the next push.
- Eliminate the Node 20 deprecation banner by upgrading the three GitHub-maintained actions to their latest majors.
- Keep the `.gitignore` honest: Python build artefacts stay ignored, but `apps/web/src/lib/` (a TypeScript directory that happens to share a name with a Python build output) is preserved.

**Non-Goals:**
- No source/feature changes to the SPA. The walking-skeleton behaviour is unchanged.
- No upgrade of pnpm (`9.15.0`) or Node (`24`). Lockfile compatibility is preserved.
- No changes to `api-checks` beyond the action version bumps — the Python toolchain (uv, ruff, mypy, import-linter, pytest) is left alone.
- No new CI features: still no deploy, no build artefacts published, no e2e job — [ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md) still holds.

## Decisions

### Decision 1 — Fix the `.gitignore` by adding an explicit `!apps/web/src/lib/**` exception (do not narrow `lib/`)

The Python `lib/` rule exists because setuptools/distutils can emit `<pkg>/build/lib/<module>/...` and standalone `lib/` virtualenvs. It is conventionally part of the [GitHub Python `.gitignore`](https://github.com/github/gitignore/blob/main/Python.gitignore) template. Narrowing it (e.g., `apps/api/**/lib/`) is plausible but fragile: someone could later add a Python service under `services/<x>/` and silently re-enable build-artefact tracking.

Adding an explicit negation immediately under the `# Frontend …` section is the lowest-blast-radius fix:

```gitignore
# Re-include the frontend lib/ dir (the Python `lib/` rule above is broader than it should be)
!apps/web/src/lib/
!apps/web/src/lib/**
```

**Why two lines:** git only descends into a directory if the directory itself is un-ignored, so the negation must apply both to the directory and its contents.

**Alternative considered — move `utils.ts` out of `lib/`:** rejected. Breaks the shadcn convention (`@/lib/utils`) baked into `components.json` (`aliases.utils: "@/lib/utils"`) and the existing spec (`frontend-toolchain` requires `cn` at `apps/web/src/lib/utils.ts`). It also offers no benefit — the gitignore issue would just resurface for any future shadcn primitive that needs a helper module under `lib/`.

### Decision 2 — Pin to `@v6` across `checkout`, `setup-node`, and `pnpm/action-setup`

All three are GitHub-maintained or pnpm-maintained, all three publish floating major tags, and all three currently advertise `v6` as latest with the node24 runtime baked in. Context7 confirms:
- `actions/checkout`: README is titled "Checkout v6"; v5 already migrated to node24; v6 changes credential storage (no workflow-side change required).
- `actions/setup-node`: README examples use `@v6` with `node-version: 24`.
- `pnpm/action-setup`: README example shows `@v6` with `version: 10`. The `version` input continues to accept `9`, so we keep pnpm 9 to match the lockfile and `packageManager` field.

**Alternative considered — split (e.g., `checkout@v5`, others `@v6`):** rejected. Mixing majors invites a future "why is this one behind?" cleanup. All three are on node24 at their latest major; pinning to the same level is simpler.

### Decision 3 — Edit the two existing workflow files with version bumps only

Both workflow files already track the spec (working-dir `apps/web/`, `pnpm install --frozen-lockfile`, the four checks). Restructuring them risks semantic drift. The diff is exactly five lines: three bumps in `web-checks.yml` (`actions/checkout@v4` → `@v6`, `pnpm/action-setup@v4` → `@v6`, `actions/setup-node@v4` → `@v6`) and two bumps in `api-checks.yml` (`actions/checkout@v4` → `@v6`, `astral-sh/setup-uv@v3` → `@v8`). The `setup-uv` bump is not strictly required by GitHub's deprecation banner (it's a composite action without the Node 20 runtime risk), but Context7 confirms the latest major is `v8.1.0` and the user policy is "nothing stale". Any future restructure (matrix, concurrency, caching tweaks) is a separate change.

### Decision 4 — Track the existing `apps/web/src/lib/utils.ts` content as-is

The local file already implements the shadcn helper:

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

This is exactly what the existing spec (`frontend-toolchain` → "Application shell ⇒ `cn(...inputs: ClassValue[])`") requires. No edit, just a `git add` after the `.gitignore` fix.

## Risks / Trade-offs

- **[Risk] An out-of-band edit to the workflow file via the GitHub web UI re-introduces a deprecated action version** → Mitigation: the spec ADDs a "No deprecated action versions" scenario, so `openspec validate --strict` (run on every change touching the spec) and any future spec-vs-code drift check will fail loudly.
- **[Risk] The `pnpm/action-setup@v6` README documents pnpm 10; we still install pnpm 9** → Mitigation: the `version` input accepts any major. We will not change `packageManager` or `pnpm-lock.yaml`. If pnpm 9 ever drops node24 support (unlikely — the action's node runtime is independent of the installed pnpm), we revisit then.
- **[Trade-off] Adding the `!apps/web/src/lib/` negation makes the .gitignore slightly less self-explanatory** → Mitigation: a one-line comment above the negation explains why it is needed. The alternative (narrowing `lib/` directly) is worse — see Decision 1.
- **[Risk] Tracking the workflow files locally exposes them to the pre-commit hooks** → Mitigation: the existing pre-commit hooks (`web-typecheck`, `web-lint`) filter by `^apps/web/.*\.(ts|tsx|js|jsx)$` — `.github/workflows/*.yml` does not match, so it is a no-op.

## Migration Plan

1. Apply the `.gitignore` negation (Decision 1).
2. `git add apps/web/src/lib/utils.ts` (Decision 4) — file is unchanged.
3. Create `.github/workflows/web-checks.yml` and `.github/workflows/api-checks.yml` locally, mirroring the remote, with the three actions bumped to `@v6` (Decisions 2 & 3).
4. Update `openspec/specs/frontend-toolchain/spec.md` (via the delta in `specs/frontend-toolchain/spec.md`) — version pin, workflow-in-repo requirement, gitignore guard.
5. Run `pnpm typecheck && pnpm lint && pnpm format:check && pnpm test:run && pnpm build` in `apps/web/` — all green locally.
6. Commit, push to `main`, watch the next `web-checks` run pass with no Node 20 banner.
7. `openspec archive fix-web-checks-ci` once green.

**Rollback:** Revert the single commit. The remote workflows continue to run because GitHub falls back to the last commit-known version of `.github/workflows/*.yml`, which is the pre-revert state.

## Open Questions

None. All three failing modules import `@/lib/utils` only for `cn`; no other shadcn helpers are introduced by this change. The action-version bump is mechanical and reversible.
