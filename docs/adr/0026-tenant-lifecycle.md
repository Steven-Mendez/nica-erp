# ADR-0026 — Tenant lifecycle

**Status**: Provisional — states are defined but no transition is implemented in sprints 00-09 (lifecycle operations are post-MVP per [18-roadmap.md](../18-roadmap.md)). Revisit when the first tenant operation runbook is written.
**Date**: 2026-05-23

## Context
[ADR-0002](0002-postgres-rls.md) commits to a pool model with RLS isolation. What's missing: the **states** a tenant moves through, who can drive each transition, and what happens to data at each step. Without this, signup, suspension, and deletion are ad-hoc — and fiscal data retention ([ADR-0014](0014-soft-delete.md)) is impossible to reason about.

## Decision
**Four states, three irreversible transitions.** State lives in `tenants.status` (enum). Transitions emit integration events (per [ADR-0006](0006-transactional-outbox.md)) for audit and downstream effects.

```
provisioning ──► active ──► suspended ──► purged
                   ▲           │
                   └───────────┘
```

| State | Meaning | What works | What doesn't |
|---|---|---|---|
| `provisioning` | Signup in progress (Cognito user created, RLS schema not yet seeded) | Signup callback endpoints | API; user sees "we're getting your workspace ready" |
| `active` | Default operating state | Everything | — |
| `suspended` | Non-payment, abuse, or owner request | Read-only API; no event publishing; no UI mutation | Mutations return 403 with `problem+json` type `tenant-suspended` |
| `purged` | Fiscal retention window expired and owner requested deletion | Nothing | Tenant ID 410 Gone; data hard-deleted |

### Transitions

| From | To | Driver | Trigger | Side effects |
|---|---|---|---|---|
| (none) | `provisioning` | self-signup | `POST /v1/auth/register` succeeds | `TenantProvisioning` event |
| `provisioning` | `active` | system | Cognito email verified + RLS schema seeded | `TenantActivated` event; first admin user role granted |
| `active` | `suspended` | super-admin (manual) | runbook in [`../13-operations.md`](../13-operations.md) | `TenantSuspended` event; sessions revoked next refresh |
| `suspended` | `active` | super-admin (manual) | runbook | `TenantReactivated` event |
| `suspended` | `purged` | super-admin + owner consent | runbook; only after fiscal retention (5 years per DGI, per [ADR-0017](0017-backups-pitr.md)) | `TenantPurged` event; data hard-deleted in batched transaction; backup snapshots retained under `retention/legal-hold/` |

### Hard constraints
- **Fiscal data is never deleted while inside the retention window.** Purge before year 5 requires explicit legal-hold override and is logged.
- **`active → purged` is forbidden.** Suspension is mandatory as a cooling-off step.
- **`purged → *` is irreversible.** Recovery is from backup snapshot only and requires a new tenant ID.
- **Session revocation on suspend** is best-effort — JWTs valid until natural expiry (≤ 1 hour, per [06 — Security model § TTLs](../06-security-model.md#ttls)). Backend additionally checks `tenants.status` on every authenticated request via the same dependency that loads the tenant context.

## Consequences
- (+) Every transition has a single source of truth (`tenants.status`) and an audit trail (the event).
- (+) Compliance posture is explicit — DGI 5-year retention is encoded in the transition rules, not in dev folklore.
- (+) Super-admin actions are funneled through documented runbooks, not console clicks.
- (+) Read-only suspended state preserves the customer's ability to export their data while disputes are resolved.
- (−) Adds a `tenants.status` check on every authenticated request (~1 query, cached per request).
- (−) Self-service purge UI is out of scope — operator runbook only. Acceptable until tenant churn exceeds a couple per quarter.
- (−) Purge transaction can be large (multi-table cascading delete); batched with a watchdog timeout — patterns in [ADR-0028](0028-data-migration-strategy.md).

## Alternatives
- **Soft-only model (no hard purge, ever)** — rejected: violates "right to deletion" expectations and accumulates dead data indefinitely.
- **Self-service suspend/resume via API** — rejected: too easy to deny service accidentally; super-admin gate is intentional friction.
- **State as a derived computed column from billing/payment status** — rejected: couples tenant lifecycle to billing model that [ADR-0023](0023-no-ci-cd-mvp.md)-context drops out of scope ("no monetization layer").

## Revisit triggers
- Tenant count > 50 — automate the suspend/reactivate runbook; consider self-service suspend.
- First tenant purge request before year 5 — formalize legal-hold override process.
- Regulatory change to DGI retention period — update the `suspended → purged` precondition.
- Bounce/complaint volume from suspended tenants > 5% — re-evaluate read-only access during suspension.
