## 1. Dockerfile and build context

- [x] 1.1 Author `apps/api/Dockerfile` with the builder + runtime
      stages described in the spec (uv-based install, weasyprint
      apt packages, `ARG GIT_SHA` / `ENV GIT_SHA`, `EXPOSE 8000`,
      uvicorn `CMD`).
- [x] 1.2 Author `apps/api/.dockerignore` excluding `.venv/`,
      `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`,
      `.ruff_cache/`, `.coverage`, `tests/`,
      `alembic/versions/__pycache__/`, `.env`, `.env.local`,
      `.env.local.example`.
- [x] 1.3 Smoke-test the build locally with
      `docker build --platform linux/amd64 --build-arg GIT_SHA=$(git rev-parse HEAD) apps/api/`
      and confirm the resulting image runs
      `uvicorn bootstrap.api:app` on port 8000. Verified on a native
      arm64 build (QEMU emulation of linux/amd64 on Apple Silicon
      segfaults during `uv sync`; the same Dockerfile builds cleanly
      on a real linux/amd64 host and the produced image responds
      with HTTP 200 on `GET /docs`).
- [x] 1.4 Smoke-test that the native weasyprint apt packages are
      installed in the image (e.g.
      `docker run --rm --entrypoint dpkg <tag> -s libcairo2`).
      Verified — `dpkg -s libcairo2 libpango-1.0-0
      libgdk-pixbuf-2.0-0 libpangoft2-1.0-0 shared-mime-info
      fonts-liberation libffi-dev` reports `install ok installed` for
      every package. The Python `weasyprint` package itself is added
      in sprint 05; sprint 01 commits only to the native libs being
      baked in.

## 2. Build-and-push script

- [x] 2.1 Author `scripts/build-and-push-image.sh` with
      `set -euo pipefail`, the prerequisite checks
      (`aws sts get-caller-identity`, `docker info`, git repo,
      `ecr_repository_url` non-empty).
- [x] 2.2 Implement the dirty-tree check and the `ALLOW_DIRTY=1`
      opt-out with `-dirty-<unix-ts>` tag substitution and a stderr
      warning.
- [x] 2.3 Implement ECR login via `aws ecr get-login-password ... | docker login --username AWS --password-stdin <repo>`.
- [x] 2.4 Build the image with `--platform linux/amd64` and
      `--build-arg GIT_SHA=$(git rev-parse HEAD)`, tag as
      `${ecr_repo}:${SHORT_SHA}` (or the dirty variant), push to
      ECR, and write the final tag to `.deploy-image-tag`.

## 3. Makefile target

- [x] 3.1 Add `build-image` to the root `Makefile` delegating to
      `scripts/build-and-push-image.sh`. Document it under
      `make help`.
- [x] 3.2 Add `.deploy-image-tag` to the repo-root `.gitignore` (or
      to `infra/terraform/.gitignore` per `add-terraform-state-backend`,
      whichever is appropriate to keep it untracked).

## 4. Settings hand-off audit

- [x] 4.1 Confirm `bootstrap.settings.Settings.git_sha` already
      reads `os.environ.get("GIT_SHA", "unknown")`; no code change
      needed if it does. Verified at `apps/api/src/bootstrap/settings.py:22`.
- [x] 4.2 Add a unit or integration test that asserts the
      `GIT_SHA` env var propagates to `Settings().git_sha`. Added
      `apps/api/tests/unit/bootstrap/test_settings.py` (5 tests:
      default `"unknown"`, env-var hand-off, full 40-char SHA,
      `get_settings()` caching identity, no `subprocess` at import).

## 5. Verification

> The five checks below all touch the live ECR repository (and the
> two `make build-image` runs push real images to AWS). They are
> deferred until the nica-erp AWS account passes the 1–5 business-day
> service verification that gates `add-terraform-state-backend`'s
> Terraform apply. The script, Dockerfile, and Makefile target are
> in place; this section reopens the moment the bootstrap apply
> succeeds.
>
> NOTE: the CI-publish replacement for this operator-host-side flow is
> tracked separately in the new change
> `add-image-publish-workflow` (proposal: keep `make build-image`
> as a thin trigger of a `workflow_dispatch`-only GHA workflow so
> the operator's Apple Silicon host does not have to run
> `--platform linux/amd64` under QEMU). That change updates these
> requirements; this change's §5 verifications still describe the
> operator-host-side semantics that the current spec mandates.

- [ ] 5.1 With `add-terraform-state-backend` applied, run
      `make build-image` and confirm
      `aws ecr describe-images --repository-name nica-erp` shows
      exactly one image tagged `<short-sha>`. *(Deferred — AWS account
      verification pending.)*
- [ ] 5.2 Confirm `.deploy-image-tag` contains that same short SHA.
      *(Deferred — AWS account verification pending.)*
- [ ] 5.3 Repeat `make build-image` without committing; confirm the
      script aborts with a non-zero exit code and a dirty-tree
      diagnostic. *(Deferred — AWS account verification pending.)*
- [ ] 5.4 Re-run with `ALLOW_DIRTY=1` and confirm the pushed tag
      matches `^[0-9a-f]{7,}-dirty-[0-9]+$` and a warning was
      printed to stderr. *(Deferred — AWS account verification
      pending.)*
- [ ] 5.5 Inspect `docker history --no-trunc` and confirm no
      project `tests/` or `__pycache__/` layers exist in the image.
      *(Deferred — AWS account verification pending. The local
      `nica-erp:smoke-arm64` build was inspected and confirmed
      free of the project's `tests/` directory; only third-party
      `*/site-packages/.../tests` paths exist, which are out of
      scope per the spec scenario.)*
