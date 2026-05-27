## Context

`add-terraform-state-backend` creates an empty ECR repository.
`add-aws-runtime-stack` will declare an ECS task definition whose
`image` argument points at `${ecr_repo}:${tag}`. Between those two
lies the question this change answers: what's in the image, and how
does it get there.

Two constraints make the answer non-trivial:

- **WeasyPrint baseline.** Sprint 05 (sales) generates PDF invoices
  with `weasyprint`, which needs `libcairo2`, `libgdk-pixbuf-2.0-0`,
  `libpango*`, `shared-mime-info`, `fonts-liberation`, `libffi-dev`
  installed at the OS level. Sprint 01 deliberately installs them
  now to avoid an image rebuild round-trip in sprint 05
  ([sprint 01 §Production Dockerfile](../../../docs/sprints/01-aws-wiring-rolling-deploys.md)).
- **`GIT_SHA` reaches `/healthz`.** The walking skeleton already
  reads `os.environ["GIT_SHA"]` at app startup; in AWS that env var
  is supplied at image build time (not at task launch), so the image
  must bake the SHA in via a build arg.

This change is also where the operational convention "no CI/CD in
the MVP" ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md)) becomes
visible: image builds happen on the operator host, not in GitHub
Actions. The script has to be defensible enough for a human to run
unattended.

## Goals / Non-Goals

**Goals:**

- A single `make build-image` call produces an immutable, tagged
  image in ECR whose `/healthz` endpoint (once it runs) returns
  `git_sha = <full or short SHA of HEAD>`.
- The image's runtime stage already contains every native library
  weasyprint needs; no `apt-get install` happens later in the
  project's lifecycle.
- The image is built for `linux/amd64` regardless of the operator's
  host architecture (Apple Silicon hosts use buildx emulation),
  because the ECS task runs on Fargate `linux/amd64`.
- The tag scheme is deterministic and reflects exactly one commit;
  re-pushing the same SHA is impossible because the ECR repo is
  `IMMUTABLE`.
- The script writes the produced tag to `.deploy-image-tag` (a
  gitignored file) so `add-deploy-destroy-automation`'s deploy
  script can read it without re-running git.

**Non-Goals:**

- Multi-architecture manifests (`linux/arm64` Fargate tasks). The
  MVP runs `linux/amd64` only.
- Image signing (cosign/SLSA), SBOM emission, runtime image scanners
  beyond ECR's built-in scan-on-push. Useful eventually, out of
  scope for sprint 01.
- Buildkit cache pushed to a remote registry. Local layer caching is
  enough at the volume of one operator.
- Running the build under GitHub Actions
  ([ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md)).
- The migration one-off task (`alembic upgrade head` via ECS
  RunTask) — it reuses this image but the RunTask wrapper is in
  `add-deploy-destroy-automation`.

## Decisions

### Multistage Dockerfile with a `uv`-built `.venv`

The builder stage uses `uv sync --frozen --no-dev --no-install-project`
plus `uv pip install --no-deps .` so the project itself plus its
locked production dependencies land inside a single `.venv` folder
that the runtime stage copies via `COPY --from=builder /app/.venv /app/.venv`.

Rationale: this is exactly the recipe the sprint doc spells out, and
it keeps the runtime image free of `uv` itself (saving ~40 MB) while
still being byte-identical to what `uv` produces locally.

Alternative considered: a single-stage image that runs `uv sync` at
build. Rejected — leaves the build cache and uv toolchain in the
runtime image and conflates dev/prod sync flags.

### Runtime base `python:3.13-slim`, not `distroless` or `alpine`

`apps/api/pyproject.toml` pins `requires-python = ">=3.13,<3.14"`
and `uv.lock` declares `requires-python = "==3.13.*"`, so the image
base SHALL be `python:3.13-slim` (any earlier minor would make
`uv sync --frozen` fail at build time).

`weasyprint` requires glibc-linked libraries (`libcairo2` and
friends); Alpine's musl is a poor fit and shipping shims would
inflate the image more than the slim variant. `distroless`
ships no shell, which conflicts with the operator-readable
`docker exec` debugging story we want during sprint 01.

### `linux/amd64` only, enforced at build time

`docker build` is invoked with `--platform linux/amd64`. On Apple
Silicon, buildx uses QEMU emulation; the resulting image still runs
natively on Fargate `linux/amd64`.

Rationale: avoids the silent "works on my arm64 mac, hangs on
Fargate" failure mode.

### Tags derived from `git rev-parse --short HEAD`

`SHORT_SHA = $(git rev-parse --short HEAD)` (7 chars by default) is
the image tag. The full 40-char SHA goes into the `GIT_SHA` build
arg so `/healthz` reports the full value.

Rationale: short SHAs are easier to read in ECS console / ALB logs;
full SHAs match the value in `/healthz` and in commit messages.

### Dirty-tree refusal with an opt-out

A pristine `git diff --quiet && git diff --cached --quiet` is the
default. Failures abort with an explanatory error. Setting
`ALLOW_DIRTY=1` switches the tag to `${SHORT_SHA}-dirty-<unix-ts>`
and prints a warning.

Rationale: deploying a dirty tree silently has no way to be
reproduced later; an explicit escape hatch (with a noisy tag and a
warning) covers the operator-debugging case without making it the
default. The ECR `IMMUTABLE` tag policy still applies to the
`dirty` tags — they cannot be overwritten, only superseded.

### `.deploy-image-tag` is the hand-off artifact

`build-and-push-image.sh` writes the pushed tag (e.g.
`abc1234`) to `.deploy-image-tag` at repo root. The deploy script
in `add-deploy-destroy-automation` reads this file rather than
guessing from git, so an operator who built once and rebases later
still deploys the actual built image. The file is gitignored.

Rationale: keeps build and deploy decoupled while still giving
deploy a deterministic input.

### `.dockerignore` is permissive enough for cache hits

The ignore list excludes tests, caches, env files, and the entire
`apps/web/` tree, but does **not** exclude `pyproject.toml` /
`uv.lock` (obviously), `alembic/`, `README.md`, or anything else
the runtime needs.

Rationale: a too-strict ignore breaks the build; a too-loose ignore
busts the layer cache when unrelated files change. Tests and
caches are the biggest cache-busters in practice.

### No CI/CD; image builds run from the operator host

Per [ADR-0023](../../../docs/adr/0023-no-ci-cd-mvp.md) there is no
GitHub Actions step that runs `make build-image`. The script
authenticates via the operator's AWS credentials
(`aws ecr get-login-password`) and pushes from the operator host.

Trade-off: a build is reproducible to the operator who ran it but
not centrally audited. Acceptable at the MVP stage; revisit when
the project grows.

## Risks / Trade-offs

- **Risk**: weasyprint libs inflate the image to ~600 MB. → **Trade-off**:
  accepted; the alternative (rebuild in sprint 05) is worse.
- **Risk**: `python:3.12-slim` ships security patches asynchronously
  from the base image release. → **Mitigation**: ECR scans on push
  surface CVEs; the operator can rebuild on demand. No automated
  rebuild trigger in sprint 01.
- **Risk**: `--platform linux/amd64` on Apple Silicon is slow
  (5–10× slower than native arm64). → **Trade-off**: accepted; the
  build is a once-per-deploy operation and Fargate arm64 task
  support is out of scope for the MVP.
- **Risk**: `ALLOW_DIRTY=1` lets an operator ship code that doesn't
  match HEAD. → **Mitigation**: tag includes the literal `dirty`
  segment plus a timestamp, and the script prints a warning to
  stderr. The `IMMUTABLE` repo policy prevents the dirty tag from
  ever being reused.
- **Risk**: a build with the wrong `GIT_SHA` makes `/healthz`
  misleading. → **Mitigation**: `GIT_SHA` is captured by the
  script before any branch movement and passed as a single
  build-arg; it cannot diverge from the tag derivation.

## Migration Plan

This change has no prior image-publishing process to migrate from.

- Deploy:
  1. Apply `add-terraform-state-backend` so the ECR repo exists.
  2. Run `make build-image`; verify
     `aws ecr describe-images --repository-name nica-erp` lists the
     tag.
  3. Inspect `.deploy-image-tag`; confirm it matches
     `git rev-parse --short HEAD`.
- Rollback: ECR `IMMUTABLE` policy means published images are not
  rewritten; a "rollback" is simply deploying a previous tag from
  the registry once the deploy automation in
  `add-deploy-destroy-automation` exists. The lifecycle policy in
  `add-terraform-state-backend` keeps the last 5 tags, which is the
  rollback window.

## Open Questions

- (none — the Dockerfile body and the script's contract are pinned
  by sprint 01 and ADR-0023)
