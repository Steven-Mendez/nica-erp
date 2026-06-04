## MODIFIED Requirements

### Requirement: Problem-code-to-Spanish copy lives in a single registry

`apps/web/src/api/errors.ts` SHALL export `messageForProblem(problem:
ApiProblem): string` that maps the documented auth problem codes to
Spanish copy. The registry MUST include at minimum:

- `auth.invalid_credentials` → `"Correo o contraseña incorrectos."`
- `auth.lockout_active` → `"Demasiados intentos. Intenta de nuevo en {minutos} minutos."`
  (template; `{minutos}` is replaced with `ceil(retry_after_seconds / 60)`, clamped to a minimum of 1)
- `auth.invalid_confirmation_code` → `"Código incorrecto o expirado. Solicita uno nuevo."`
- `auth.signup_email_not_confirmed` → `"Confirma tu correo antes de iniciar sesión."`
- `auth.token_expired` → `"Tu sesión expiró. Inicia sesión de nuevo."`
- `auth.reset_token_used` → `"Este enlace ya fue utilizado. Solicita uno nuevo."`
- `auth.reset_token_expired` → `"El enlace expiró. Solicita uno nuevo."`
- `auth.resend_throttled` → `"Espera unos segundos antes de pedir otro código."`

Any problem code not in the registry SHALL fall through to the
generic Spanish copy `"Ocurrió un error. Intenta de nuevo."` and
SHALL NOT render the raw English code.

#### Scenario: Unknown problem code renders the generic Spanish fallback

- **WHEN** `messageForProblem` is called with an `ApiProblem` whose `code` is not in the registry
- **THEN** the returned string is `"Ocurrió un error. Intenta de nuevo."`

#### Scenario: lockout_active copy formats the Retry-After window

- **WHEN** `messageForProblem({ code: "auth.lockout_active", retry_after_seconds: 125 })` is called
- **THEN** the returned string is `"Demasiados intentos. Intenta de nuevo en 3 minutos."` (125 seconds → ceil to 3 minutes)

#### Scenario: resend_throttled copy is the documented Spanish string

- **WHEN** `messageForProblem({ code: "auth.resend_throttled", status: 429, retry_after_seconds: 30 })` is called
- **THEN** the returned string is `"Espera unos segundos antes de pedir otro código."`
