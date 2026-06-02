# frontend-auth-error-feedback Specification

## Purpose
TBD - created by archiving change harden-auth-flows. Update Purpose after archive.
## Requirements
### Requirement: Auth mutations expose errors and only navigate on success

Every auth-related TanStack Query mutation SHALL expose `mutation.error` to its caller and SHALL navigate only from `onSuccess`. The affected mutations — `useLoginMutation`, `useConfirmSignupMutation`, `useForgotPasswordMutation`, `useResetPasswordMutation`, and `useResendCodeMutation` in `apps/web/src/features/auth/api/hooks.ts` — MUST:

- Place navigation calls (e.g. `navigate({ to: "/dashboard" })`) in
  `onSuccess` only, never in `onSettled` or `onError`.
- Leave `mutation.error` accessible to the caller — i.e. the
  mutation must not swallow errors or wrap them in `null` returns.

Their consuming route components (`routes/login.tsx`,
`routes/confirm.tsx`, `routes/forgot-password.tsx`,
`routes/reset-password.tsx`) SHALL render an inline
`<FormErrorAlert error={mutation.error} />` above the submit button
whenever `mutation.error` is non-null, and SHALL NOT trigger any
navigation on error.

#### Scenario: Wrong OTP code renders an inline alert and stays on /confirm

- **WHEN** the operator submits an incorrect code on `/confirm` and `POST /v1/auth/confirm-signup` returns 401 with `code: "auth.invalid_confirmation_code"`
- **THEN** the route stays on `/confirm`, the form fields remain enabled, and an inline alert renders the Spanish copy `"Código incorrecto o expirado. Solicita uno nuevo."`

#### Scenario: Used password-reset token renders an inline alert and stays on /reset-password

- **WHEN** the operator submits a previously-used reset token to `POST /v1/auth/reset-password` and the backend returns the `auth.reset_token_used` problem
- **THEN** the route stays on `/reset-password` and renders the Spanish copy `"Este enlace ya fue utilizado. Solicita uno nuevo."` inline; the route does NOT navigate to `/login`

#### Scenario: Login lockout renders the throttle banner with retry window

- **WHEN** `POST /v1/auth/login` returns 429 with `code: "auth.lockout_active"` and `Retry-After: 600`
- **THEN** the `/login` form renders the Spanish copy `"Demasiados intentos. Intenta de nuevo en 10 minutos."` (rounded up from the 600-second header) inline

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

Any problem code not in the registry SHALL fall through to the
generic Spanish copy `"Ocurrió un error. Intenta de nuevo."` and
SHALL NOT render the raw English code.

#### Scenario: Unknown problem code renders the generic Spanish fallback

- **WHEN** `messageForProblem` is called with an `ApiProblem` whose `code` is not in the registry
- **THEN** the returned string is `"Ocurrió un error. Intenta de nuevo."`

#### Scenario: lockout_active copy formats the Retry-After window

- **WHEN** `messageForProblem({ code: "auth.lockout_active", retry_after_seconds: 125 })` is called
- **THEN** the returned string is `"Demasiados intentos. Intenta de nuevo en 3 minutos."` (125 seconds → ceil to 3 minutes)

### Requirement: FormErrorAlert is the only path for inline auth-error display

A new component at `apps/web/src/components/form/form-error-alert.tsx` SHALL be the single path for inline auth-error display, rendering a Spanish-language alert block from an unknown error value. It MUST:

- Return `null` when `error` is `null` or `undefined`.
- Call `messageForProblem` when the error is an `ApiProblem`.
- Render the generic Spanish fallback for any other error type.
- Carry `role="alert"` and be focused-on by screen readers via
  `aria-live="assertive"`.

#### Scenario: FormErrorAlert renders nothing when error is null

- **WHEN** `<FormErrorAlert error={null} />` renders
- **THEN** the rendered output is empty

#### Scenario: FormErrorAlert is announced to assistive tech

- **WHEN** `<FormErrorAlert error={problem} />` mounts with a non-null error
- **THEN** the alert element carries `role="alert"` and `aria-live="assertive"`

