# ADR-0005 — Cognito User Pool Lite tier + local `IdentityProviderLocal` adapter

**Status**: Accepted
**Date**: 2026-05-23

## Context
Auth: signup, login, refresh, forgot password, optional MFA, custom attributes (active tenant). The domain must not know the IdP, and local development must run offline.

> **Cognito pricing was restructured in November 2024** (Lite/Essentials/Plus tiers). Verify current rates before operating; the "50k MAU free" cap referenced here corresponds to the Lite tier in effect at design time.

## Decision
Production: Cognito Lite tier. Own `/v1/auth/*` endpoints delegating to Cognito (no Hosted UI), App Client without a client secret, `custom:active_tenant` attribute. Development: `IdentityProviderLocal` implements the same `IdentityProvider` port, `auth_local_users` table, JWT HS256 with the key in `.env.local`, emails to Mailpit. JWT shape identical to Cognito's. Wiring in `bootstrap/container.py` based on `APP_ENV`.

## Consequences
- (+) Fully offline dev; swap proven by construction.
- (+) Future migration to Keycloak / Auth0 / homegrown: the pattern is already in place.
- (−) Two adapters to maintain (~600 LOC).
- (−) JWT shape must match (claims `sub`, `email`, `email_verified`, `token_use`, `custom:active_tenant`, `aud`, `iss`, `exp`, `iat`); divergence breaks the middleware at deploy time.
- (−) Local↔AWS contract tests are mandatory: introduced in [sprint 02](../sprints/02-identity-and-rbac.md) when wiring `IdentityProviderCognito`; the suite is consolidated in [sprint 09](../sprints/09-mvp-validation.md) under the rolling-deploy model from [ADR-0018](0018-rolling-deploys.md).

## Alternatives
- **Homegrown auth (JWT + bcrypt)** — rejected: means owning crypto, lockouts, password policies, MFA, recovery.
- **Self-hosted Keycloak** — rejected: 24/7 container + operational effort.
- **Other IdPs (Auth0, Firebase, Cognito Essentials)** — rejected: lock-in, black box, or cost from the first MAU.
- **Cognito Lite tier in prod + local Python adapter for dev** — chosen.

## Revisit triggers
- Cognito pricing or tier structure changes again in a way that erodes the free MAU cap.
- A feature appears (B2B SSO, advanced MFA, federation) that Lite cannot cover and Essentials/Plus pricing becomes worthwhile.
- The two-adapter cost outweighs the offline-dev benefit — e.g., contract drift causes recurring deploy breakage.

Detail in [`../06-security-model.md`](../06-security-model.md).
