# ADR-0035 — Onboarding endpoints leave the caller session-ready

**Status**: Accepted
**Date**: 2026-05-31

## Context

Two endpoints sit at the *exit* of an onboarding ramp:

1. `POST /v1/auth/confirm-signup` confirms the email code minted by
   `POST /v1/auth/register`. Today it returns `204 No Content` and the
   SPA navigates to `/login`, forcing the user to retype the password
   they typed seconds earlier on `/signup`. The terminal log captured
   during a pilot run shows the round-trip explicitly:

   ```
   POST /v1/auth/register      201
   POST /v1/auth/confirm-signup 204    # no tokens
   POST /v1/auth/login          200    # forced re-entry of credentials
   ```

2. `POST /v1/invitations/accept` creates a `Membership` for the caller
   on the invited tenant. It does **not** call
   `IdentityProvider.update_active_tenant`, so the caller's JWT still
   has no `custom:active_tenant` claim. The next read from a tenant-
   scoped route returns `403`, and the frontend has to detour through
   the empresa picker so a separate `POST /v1/tenants/{id}/switch`
   call can mint a JWT with the claim populated. The same pilot run
   captured the detour:

   ```
   POST /v1/invitations/accept                      200
   GET  /v1/tenants/<id>/invitations                403   # JWT lacks active_tenant
   POST /v1/tenants/<id>/switch                     200   # now JWT has the claim
   GET  /v1/tenants/<id>/invitations                200
   ```

Both round-trips are redundant: at the moment the user calls each
endpoint, the backend already has every credential and decision it
needs to issue the next session. The current shape forces the SPA to
re-collect or re-derive state it can already infer.

The two endpoints are independent (one fixes signup, the other fixes
invite acceptance), but the design question is the same — whether
"terminal" steps in an onboarding flow are allowed to mint tokens as
a side effect of the action they perform, or whether token minting
stays exclusive to `/v1/auth/login` and `/v1/tenants/{id}/switch`.

The single-coder constraint ([ADR-0018](0018-rolling-deploys.md))
rules out heavier solutions like server-side session storage or
introducing a separate "complete-signup" orchestrator service.

## Decision

**Onboarding-terminal endpoints SHALL leave the caller in the session
state the action implies.** Concretely:

- `POST /v1/auth/confirm-signup` SHALL accept an optional `password`
  in its request body. When `password` is present and the email code
  confirms successfully, the use case SHALL invoke
  `IdentityProvider.authenticate` in the same transaction and return
  `200 OK` with `{ access_token, refresh_token, id_token }`. When
  `password` is absent the endpoint keeps its current `204 No Content`
  shape (backwards compatible).
- `POST /v1/invitations/accept` SHALL accept an optional
  `refresh_token` in its request body. After persisting the
  `Membership`, if the caller has **no prior `custom:active_tenant`
  claim** (typical first-membership invitee), the use case SHALL call
  `IdentityProvider.update_active_tenant(user_id, tenant_id)` and
  then `IdentityProvider.refresh(refresh_token)` to mint a fresh
  bundle of tokens with the claim populated. The response shape adds
  an optional `tokens` field. When the caller already had an
  `active_tenant` (veteran user joining an additional tenant), no
  token rotation happens and the response keeps the existing shape;
  the caller stays inside the empresa they were using.

Token rotation in `accept-invitation` SHALL only fire on the
first-membership path so a user who is invited to a *second* empresa
does not get silently switched out of the empresa they are working
on. Choosing which empresa is active on a subsequent invitation
remains an explicit action via the sidebar `OrganizationSwitcher`.

Token transport on the wire is unchanged: tokens stay in the response
body, the SPA stores them in JS process memory per
[`docs/06-security-model.md` §Refresh and revocation](../06-security-model.md#refresh-and-revocation),
and no new persistence layer or cookie surface is introduced.

## Consequences

- (+) The invited-new-user happy path collapses from five HTTP calls
  with one mandatory re-typed password and one picker detour to three
  HTTP calls with neither: register → confirm-with-password → accept.
- (+) The `204` shape of `confirm-signup` is preserved when the SPA
  cannot supply a password (e.g. after a hard refresh on `/confirm`),
  so the change is purely additive on the wire.
- (+) The use cases stay the only place where session state is
  mutated; the contracts grow optionally, and existing integration
  tests for the bare `204` and the unconditional accept response
  continue to pass.
- (-) `confirm-signup` becomes the second endpoint in the system that
  may issue tokens. The contract test parametrised over
  `IdentityProviderLocal` and `IdentityProviderCognito`
  ([sprint 09](../sprints/09-mvp-validation.md)) gains a second
  authenticated path it must cover.
- (-) The password flows over the wire in the `confirm-signup` body
  in addition to `/v1/auth/login`. Both endpoints already terminate
  on TLS at CloudFront → ALB and neither request body is logged; the
  exposure surface is the same as `/v1/auth/login` today.
- (-) `accept-invitation` now reads the caller's prior `active_tenant`
  claim from the bearer token to decide whether to rotate tokens.
  Misreading that claim (e.g. accepting a stale token) would silently
  switch a veteran user's active empresa. The use case SHALL read the
  claim from the validated `CurrentUserContext`, not from the
  caller-supplied refresh token, to keep the decision derived from
  authenticated state only.
- The decision applies **only** to these two endpoints. Other
  terminal actions (`POST /v1/tenants` which creates the user's first
  empresa, `POST /v1/auth/password/reset` which lands the user back
  at `/login`) keep their current shapes; the policy is opt-in per
  endpoint, not a system-wide rule.

## Alternatives

- **A — Frontend stores the typed password in `sessionStorage` and
  calls `/v1/auth/login` immediately after `confirm-signup`** —
  rejected: a plaintext password in browser storage (even cleared on
  success) is a category of XSS exposure the project has explicitly
  excluded by keeping tokens in JS memory only. Passing the password
  via router state would lose it on `/confirm` refresh and still
  requires two HTTP calls; the second call also generates a separate
  audit-log entry that fragments the signup story.
- **B — Issue a short-lived "post-confirm" magic token from
  `confirm-signup` which the SPA exchanges at `/v1/auth/login` for
  full tokens** — rejected: introduces a second token store and a
  second expiry policy for one round-trip of value. The single-coder
  constraint makes the additional state machine net-negative.
- **C — Make `accept-invitation` *always* rotate tokens with the new
  `active_tenant` claim** — rejected: a veteran user accepting an
  invitation to a second empresa would be silently moved out of the
  empresa they were working on. The first-membership-only gate keeps
  the surprising side effect bounded to a state where the user has no
  current empresa to be moved out of.
- **D — Add a single composite endpoint
  `POST /v1/onboarding/complete-signup-and-accept-invitation`** —
  rejected: couples two contexts (`identity` and `tenants`) in one
  router and one use case, breaking the hexagonal boundary established
  by [ADR-0001](0001-hexagonal-architecture.md). The independent
  optional-field shape keeps each context owning its own contract.
- **E — Chosen**: each endpoint independently accepts the extra input
  needed to leave the caller session-ready and rotates tokens in its
  own use case.

## Revisit triggers

- An HttpOnly cookie + BFF surface is adopted for session transport.
  At that point token rotation moves to a `Set-Cookie` header and the
  shape of these responses changes; the decision to *mutate session
  on terminal onboarding endpoints* still holds, but the wire form is
  re-evaluated.
- A second magic-link-style flow (e.g. passwordless login) joins the
  identity surface and would benefit from a dedicated post-confirm
  exchange. Alternative **B** above SHOULD be re-evaluated against
  that shared infrastructure rather than per endpoint.
- `accept-invitation` grows a "switch on accept even if I already had
  an active empresa" caller toggle, in which case the
  first-membership gate becomes one branch of an explicit policy.
