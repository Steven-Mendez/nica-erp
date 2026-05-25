# 16 — Tooling

Two stacks: **Python** (`apps/api`) and **TypeScript** (`apps/web`).

---

## Python (`apps/api`)

| Tool | Purpose |
|---|---|
| **uv** | Package and environment manager. Deterministic (`uv.lock`). Replaces pip, pip-tools, virtualenv, pipx. `uv sync`, `uv add`, `uv run`. |
| **ruff** | Lint + format (Rust, ~100× flake8+black). Rules: defaults + `I`, `B`, `UP`, `RUF`, `N`. Black style. |
| **mypy --strict** | In `domain/` and `application/`. Relaxed adapters (external APIs are poorly typed). Scope in `pyproject.toml` (`files = [...]`), not via CLI. SQLAlchemy 2.0 plugin. |
| **import-linter** | Validates `domain ← application ← adapters` and forbids cross-imports between `contexts/X` and `contexts/Y` except via ports. |
| **pre-commit** | See §Pre-commit hooks below. |

### Pre-commit hooks

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: bash -c 'cd apps/api && uv run ruff format'
        language: system
        types: [python]
        pass_filenames: false
      - id: ruff-check
        name: ruff check
        entry: bash -c 'cd apps/api && uv run ruff check --fix'
        language: system
        types: [python]
        pass_filenames: false
      - id: mypy
        name: mypy (domain + application)
        entry: bash -c 'cd apps/api && uv run mypy'
        language: system
        types: [python]
        pass_filenames: false
      - id: web-typecheck
        name: tsc --noEmit
        entry: bash -c 'cd apps/web && pnpm typecheck'
        language: system
        files: ^apps/web/.*\.(ts|tsx)$
        pass_filenames: false
      - id: web-lint
        name: eslint
        entry: bash -c 'cd apps/web && pnpm lint'
        language: system
        files: ^apps/web/.*\.(ts|tsx|js|jsx)$
        pass_filenames: false
```

Installation: `pre-commit install` (once). Manual: `pre-commit run --all-files`.

Later (when applicable): add `import-linter` (`uv run lint-imports`) when introducing the first bounded context with a real boundary; `pytest -m unit` when the suite is fast enough.

### GitHub Actions

`.github/workflows/api-checks.yml` and `.github/workflows/web-checks.yml` run **only static verification** ([ADR-0023](adr/0023-no-ci-cd-mvp.md) — they do not deploy). Triggers via `paths`:

```yaml
# api-checks.yml
on:
  push: { branches: [main] }
  pull_request: { paths: ['apps/api/**'] }
jobs:
  checks:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: apps/api } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run mypy
      - run: uv run lint-imports        # from sprint 02
      - run: uv run pytest -m unit
```

```yaml
# web-checks.yml
on:
  push: { branches: [main] }
  pull_request: { paths: ['apps/web/**'] }
jobs:
  checks:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: apps/web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'pnpm' }
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - run: pnpm install --frozen-lockfile
      - run: pnpm typecheck
      - run: pnpm lint
      - run: pnpm format:check
      - run: pnpm test --run
```

OpenAPI client sync (sprint 01+): an additional job brings up an ephemeral backend (compose + migrate), runs `pnpm gen:api` and fails if `git diff apps/web/src/api/schema.d.ts` is not empty.

### Testing

| | |
|---|---|
| `pytest` + `pytest-asyncio` (mode auto) | Markers `unit`, `integration`, `e2e`, `contract`. |
| `testcontainers` | Real ephemeral Postgres in integration (RLS, JSONB, specific types). |
| `httpx` async | E2E via `AsyncClient(app=app, base_url="http://test")` (direct ASGI, no network). |
| `respx` | Mocks for outgoing HTTP (BCN scraper, etc.). |

### DB and migrations

- **SQLAlchemy 2.0 async** with `DeclarativeBase`. Repositories implement context's `XRepository`. Pool `pool_size=5, max_overflow=10` per task. RDS per-instance capacity in [10 § Capacity](10-infrastructure.md#capacity-and-scalability).
- **asyncpg** pure async driver.
- **Alembic** single tree in `apps/api/alembic/versions/`. Naming `NNNN_short_description.py`. Migrations generate RLS, indexes, partial indexes, FKs. Runs as **one-off ECS task** on deploy.

### FastAPI

Routers per context (`contexts/<ctx>/adapters/inbound/http/router.py`). OpenAPI at `/docs` and `/redoc`. DI via `bootstrap/container.py` + `Depends()`.

**Middleware order** (LIFO in Starlette): `logging` → `metrics` → `tenant context` → `auth` → routers. `logging` registered first wraps everything and captures exceptions from the following.

**Pydantic v2** only in the HTTP adapter (request/response). Domain uses its own `dataclass(frozen=True)`.

### Logging and PDF

- **structlog** JSON (canonical fields in [12 — Observability §Log schema](12-observability.md#log-schema)).
- No X-Ray (cost). Traceability via `correlation_id` in Logs Insights.
- **weasyprint** HTML+CSS → PDF. Jinja2 templates. Fonts installed in Dockerfile; Lambda uses container image for the same reason.

---

## TypeScript (`apps/web`)

| Tool | Purpose |
|---|---|
| **Node** `>=20.11 <23` | LTS Iron + Jod. `package.json engines.node` + `.nvmrc`. |
| **pnpm** `>=9 <10` | `packageManager` field, `corepack enable`. Workspaces for future shared packages. |
| **Vite 5** | Dev server with HMR + Rollup build. [ADR-0009](adr/0009-frontend-stack.md). |
| **TypeScript 5 strict** | `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `exactOptionalPropertyTypes`. `any` forbidden by ESLint; escape via `unknown`. |
| **TanStack** | Router (typed, file-based), Query (cache + sync), Table, Form (default; react-hook-form only if an external lib requires it). |
| **Zod** | Validation + derived types. `@hookform/resolvers/zod`. |
| **UI** | Tailwind, **shadcn/ui** copied into the repo, **Radix** (accessible base), **lucide-react** icons, **sonner** toasts, class-variance-authority + clsx + tailwind-merge. [ADR-0009](adr/0009-frontend-stack.md). |
| **HTTP client** | `openapi-typescript` generates types, `openapi-fetch` typed runtime. |
| **Tests** | Vitest unit, React Testing Library components, Playwright E2E (MVP optional). |
| **Lint/format** | ESLint (TS+React), Prettier. |

Frontend detail in [09](09-frontend.md).

---

## CLI, diagrams, editor

- `typer` optional for administrative CLIs (`scripts/admin.py users list`).
- **Mermaid** in ` ```mermaid ` blocks; renders on GitHub. Optional export: `pnpm dlx @mermaid-js/mermaid-cli mmdc -i in.mmd -o out.png`.
- **Editor**: VS Code or PyCharm. VS Code extensions: Python, Pylance, Ruff, Even Better TOML, Docker, Mermaid Preview, ESLint, Tailwind CSS IntelliSense.
- **`.editorconfig`**: `indent_size=4`; `2` for JSON/YAML/MD/TS/JS.

---

## Local AWS CLI

`aws` v2 with profile `pyme-erp`. `Makefile` assumes that profile (`AWS_PROFILE=pyme-erp make deploy`). No SSO or assume-role: IAM user with rotatable credentials and minimum policy (Terraform, ECR push, `ecs run-task`, `s3 sync`).

---

## Pinned versions

`apps/api/pyproject.toml` (majors): Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0, asyncpg 0.29, psycopg 3.1 (sync for Alembic), Alembic 1.13, Pydantic 2.7+, structlog 24, boto3 1.34+, weasyprint 62 (cap < 64), passlib[bcrypt], pyjwt[crypto], httpx 0.27+. Dev: ruff, mypy, pytest + asyncio, testcontainers[postgres], respx, import-linter, pre-commit.

`apps/web/package.json` (majors): React 18.3, TanStack Router 1.40, Query 5.50, Table 8.20, Form 0.30, Zod 3.23, react-hook-form 7.52 + resolvers 3.9, openapi-fetch 0.11, Tailwind 3.4, lucide-react 0.430, sonner 1.5, date-fns 3.6, i18next 23.14 + react-i18next 15. Dev: TypeScript 5.5, Vite 5.4, openapi-typescript 7.4, ESLint 9.9, Prettier 3.3, Vitest 2.

Updated for a concrete reason (CVE, required feature), not out of habit.
