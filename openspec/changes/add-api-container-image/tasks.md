## 1. Dockerfile and build context

- [ ] 1.1 Author `apps/api/Dockerfile` with the builder + runtime
      stages described in the spec (uv-based install, weasyprint
      apt packages, `ARG GIT_SHA` / `ENV GIT_SHA`, `EXPOSE 8000`,
      uvicorn `CMD`).
- [ ] 1.2 Author `apps/api/.dockerignore` excluding `.venv/`,
      `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`,
      `.ruff_cache/`, `.coverage`, `tests/`,
      `alembic/versions/__pycache__/`, `.env`, `.env.local`,
      `.env.local.example`.
- [ ] 1.3 Smoke-test the build locally with
      `docker build --platform linux/amd64 --build-arg GIT_SHA=$(git rev-parse HEAD) apps/api/`
      and confirm the resulting image runs
      `uvicorn bootstrap.api:app` on port 8000.
- [ ] 1.4 Smoke-test that `python -c "import weasyprint"` inside the
      built image exits 0.

## 2. Build-and-push script

- [ ] 2.1 Author `scripts/build-and-push-image.sh` with
      `set -euo pipefail`, the prerequisite checks
      (`aws sts get-caller-identity`, `docker info`, git repo,
      `ecr_repository_url` non-empty).
- [ ] 2.2 Implement the dirty-tree check and the `ALLOW_DIRTY=1`
      opt-out with `-dirty-<unix-ts>` tag substitution and a stderr
      warning.
- [ ] 2.3 Implement ECR login via `aws ecr get-login-password ... | docker login --username AWS --password-stdin <repo>`.
- [ ] 2.4 Build the image with `--platform linux/amd64` and
      `--build-arg GIT_SHA=$(git rev-parse HEAD)`, tag as
      `${ecr_repo}:${SHORT_SHA}` (or the dirty variant), push to
      ECR, and write the final tag to `.deploy-image-tag`.

## 3. Makefile target

- [ ] 3.1 Add `build-image` to the root `Makefile` delegating to
      `scripts/build-and-push-image.sh`. Document it under
      `make help`.
- [ ] 3.2 Add `.deploy-image-tag` to the repo-root `.gitignore` (or
      to `infra/terraform/.gitignore` per `add-terraform-state-backend`,
      whichever is appropriate to keep it untracked).

## 4. Settings hand-off audit

- [ ] 4.1 Confirm `bootstrap.settings.Settings.git_sha` already
      reads `os.environ.get("GIT_SHA", "unknown")`; no code change
      needed if it does.
- [ ] 4.2 Add a unit or integration test that asserts
      `Settings(GIT_SHA="abcdef0").git_sha == "abcdef0"`.

## 5. Verification

- [ ] 5.1 With `add-terraform-state-backend` applied, run
      `make build-image` and confirm
      `aws ecr describe-images --repository-name nica-erp` shows
      exactly one image tagged `<short-sha>`.
- [ ] 5.2 Confirm `.deploy-image-tag` contains that same short SHA.
- [ ] 5.3 Repeat `make build-image` without committing; confirm the
      script aborts with a non-zero exit code and a dirty-tree
      diagnostic.
- [ ] 5.4 Re-run with `ALLOW_DIRTY=1` and confirm the pushed tag
      matches `^[0-9a-f]{7,}-dirty-[0-9]+$` and a warning was
      printed to stderr.
- [ ] 5.5 Inspect `docker history --no-trunc` and confirm no
      `tests/` or `__pycache__/` layers exist in the image.
