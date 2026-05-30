# ADR-0031 — Invitation token transport: hash fragment + POST body

**Status**: Accepted
**Date**: 2026-05-27

## Context
Sprint 03 issued invitation links of the shape
`POST /v1/invitations/{token}/accept`, with the signed token in the
URL path. Sprint 3.6 introduces a Supabase-style onboarding flow
where the invited user clicks the email link, the SPA loads, and the
SPA exchanges the token for membership. Two leakage surfaces become
explicit at that point:

1. **Server-side logs**: CloudFront, ALB, FastAPI access logs and any
   intermediate proxy record the full URL path of every request,
   including the token. A token valid for seven days that ends up in
   log retention is a credential left in plaintext.
2. **Referer headers and browser history**: when the invited page
   makes any cross-origin fetch (analytics, image CDN, etc.) the
   `Referer` header carries the path. Browser history and shared
   screenshots also expose it.

The single-coder constraint ([ADR-0018](0018-rolling-deploys.md))
rules out heavyweight mitigations like rotating-key magic links or
short-lived JWT exchanges that would add infra. The token itself is
already high-entropy and single-use; the question is how to *carry*
it from email to backend without dropping it in places we cannot
scrub.

## Decision
**Hash fragment + POST body**.

- The invitation email links to
  `https://<host>/invitations/accept#t=<token>`.
- The browser never sends the fragment to the server: `#t=…` does
  not appear in access logs, `Referer` headers, CDN traces, or
  upstream forwards.
- The SPA reads `location.hash`, immediately calls
  `history.replaceState(null, "", location.pathname)` to strip the
  token from the visible URL and the history stack, and POSTs the
  token in the body:

  ```http
  POST /v1/invitations/accept
  Content-Type: application/json
  { "token": "<token>" }
  ```

- The legacy `POST /v1/invitations/{token}/accept` endpoint is
  removed outright (no transitional 410 Gone). The project has
  not yet shipped, so there are no outstanding invitation links
  to honour; a deep link from the discarded shape now surfaces a
  plain 404 from the router.
- A separate `GET /v1/invitations/{token}/preview` returns
  `{ email, organization_name, role }` for the pre-signup screen
  (so the SPA can pre-fill the invited user's email without
  decoding the token client-side). The token still travels in the
  URL path on the preview call — its result is innocuous metadata
  the recipient already has from the email — but the call is
  rate-limited per token to make brute-force enumeration uneconomic.

## Consequences
- (+) Tokens never appear in server-side request logs, referer
  headers, or CDN traces.
- (+) `history.replaceState` clears the token from the user's
  browser history and the visible address bar within a tick of page
  load.
- (+) Dropping the legacy endpoint outright keeps the router
  surface minimal; the project has no pre-cutover invitations
  in the wild that would benefit from a transitional 410.
- (-) The link is no longer copy-pasteable to a `curl` example
  without first reading the documentation: the SPA must be the
  carrier. For programmatic acceptance (CI, integration tests) the
  POST body form is used directly, which is actually the documented
  shape going forward.
- (-) The preview endpoint adds a new public route. It is
  rate-limited and returns only data the recipient already
  possesses from the email body, so the exposure is bounded.
- The decision is **frontend-driven**; backend changes are minimal
  (one new POST endpoint, one new GET endpoint, the legacy path
  deleted). No DB or JWT changes.

## Alternatives
- **Token in query string (`?t=…`)** — rejected: query strings
  appear in access logs and `Referer` headers in the same way path
  parameters do.
- **Magic link issuing a short-lived JWT** — rejected: requires a
  second server-side store for the magic ticket and a separate
  expiry policy. The existing single-use token is already
  appropriate; the problem is transport, not lifetime.
- **Keep the token in the path and aggressively scrub logs** —
  rejected: log scrubbing is a runtime promise; a missed
  configuration leaks. Defense in depth prefers the channel where
  the token never travels.
- **Token in custom header (e.g. `X-Invite-Token`)** — rejected for
  the *initial* click: the first request is a navigation, not a
  fetch, so the SPA cannot set a header until it has executed. The
  hash-fragment approach is the only one that works without an
  intermediate landing.

## Revisit triggers
- A managed magic-link service is adopted for other flows
  (passwordless login, magic-invitation for staff). At that point
  this decision should be re-evaluated against using the same
  infrastructure.
- Logging infrastructure gains automatic redaction of path
  parameters matching a known token shape; if reliable, the
  fragment trick is still preferred but the urgency drops.
