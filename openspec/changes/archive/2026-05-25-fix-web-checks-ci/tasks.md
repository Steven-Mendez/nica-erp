## 1. `.gitignore` reconciliation

- [x] 1.1 In the root `.gitignore`, append (under the existing `# Frontend generated OpenAPI client` block) an explicit negation pair that re-includes `apps/web/src/lib/`:
  ```gitignore
  # Re-include the frontend lib/ dir (Python `lib/` rule above is too broad)
  !apps/web/src/lib/
  !apps/web/src/lib/**
  ```
- [x] 1.2 Verify `git check-ignore -v apps/web/src/lib/utils.ts` now reports the negation rule (or no rule at all) instead of `lib/`

## 2. Track the shadcn helper

- [x] 2.1 Confirm `apps/web/src/lib/utils.ts` exists locally with the `cn(...inputs: ClassValue[])` body (no edit — the file was authored in the walking-skeleton change)
- [x] 2.2 `git add apps/web/src/lib/utils.ts`

## 3. Workflow action-version bumps (files already tracked)

- [x] 3.1 In `.github/workflows/web-checks.yml`: bump `actions/checkout@v4` → `@v6`, `pnpm/action-setup@v4` → `@v6`, `actions/setup-node@v4` → `@v6`. No other line changes.
- [x] 3.2 In `.github/workflows/api-checks.yml`: bump `actions/checkout@v4` → `@v6` and `astral-sh/setup-uv@v3` → `@v8` (Context7 confirms v8 is the current major; v3 is five majors behind). No other line changes.
- [x] 3.3 Confirm `git diff .github/workflows/` shows exactly five version-bump lines

## 4. Local verification (apps/web)

- [x] 4.1 `pnpm install --frozen-lockfile` (no-op if already installed)
- [x] 4.2 `pnpm typecheck` exits zero
- [x] 4.3 `pnpm lint` exits zero
- [x] 4.4 `pnpm format:check` exits zero
- [x] 4.5 `pnpm test:run` exits zero (the existing index.test.tsx passes)
- [x] 4.6 `pnpm build` produces `dist/` with the existing seven-token CSS bundle (no regression)

## 5. Spec drift reconciliation

- [x] 5.1 Run `openspec validate fix-web-checks-ci --strict` and fix any reported drift
- [x] 5.2 Confirm the modified `frontend-toolchain` requirement still matches the workflows on disk (action versions, step order, working directory)

## 6. Push and observe

- [ ] 6.1 Single commit grouping `.gitignore`, both workflow files, `apps/web/src/lib/utils.ts`, and the OpenSpec change folder
- [ ] 6.2 Push to `main`
- [ ] 6.3 Watch the next `web-checks` run via `gh run watch` (or `gh run list --branch=main --limit=1`); the run MUST be green and the logs MUST NOT contain the Node 20 deprecation warning
- [ ] 6.4 Watch the next `api-checks` run; it MUST still be green

## 7. Archive

- [ ] 7.1 `openspec archive fix-web-checks-ci` — folds the delta into `openspec/specs/frontend-toolchain/spec.md` and moves the change folder under `openspec/changes/archive/`
- [ ] 7.2 Verify the resulting `frontend-toolchain/spec.md` contains the new scenarios (incl. "No deprecated action versions" and "shadcn helper is tracked")
