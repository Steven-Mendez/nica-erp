# Sprint 08 — `notifications` with SES sandbox + deploy

**Goal.** The SMB receives emails on key events (invoice issued with PDF attached, tenant invitation, low stock). Introduces the `notifications_worker` Lambda subscribed to SQS `notif-queue` (rule of the bus from [sprint 07](07-outbox-eventbridge-audit.md)) and completes the SES wiring from [sprint 02](02-identity-and-rbac.md). **SES stays in permanent sandbox with email-only verification** ([ADR-0020](../adr/0020-no-custom-domain-mvp.md)): recipients verified individually in console (≤50). Closes with invoice issued from the SPA + email with PDF to `alert_email`.

---

## Dependencies

- [02](02-identity-and-rbac.md) (`EmailSender` port + `EmailSenderSes` for signup, SES email identity verified).
- [05](05-parties-and-sales.md) (PDF in S3 via `FileStorage`).
- [07](07-outbox-eventbridge-audit.md) (bus + SQS + consumer pattern with `processed_events`).

**Critical deploy preconditions**:
- `alert_email` verified in SES (console → Verified identities) **before** `make deploy`. Without this, sends fail silently and the E2E fails.
- Any demo/QA recipient email also verified individually (≤50 in sandbox). Without domain identity a domain cannot be auto-approved.
- SES and Cognito share `us-east-1` (Cognito email plugin requirement).

---

## `notifications/` context

- Aggregate: `Notification`. Events: `NotificationSent`, `NotificationFailed`, `NotificationBounced` (future).
- VOs: `EmailTemplate` (name + path), `NotificationType` (enum).

```sql
CREATE TABLE notifications (
  id              UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL,
  user_id         UUID,                          -- nullable (external)
  to_email        TEXT NOT NULL,
  type            TEXT NOT NULL,                 -- invoice_issued, invitation, low_stock, ...
  subject         TEXT NOT NULL,
  status          TEXT NOT NULL,                 -- pending, sent, failed, bounced
  template        TEXT NOT NULL,
  context         JSONB NOT NULL,
  sent_at         TIMESTAMPTZ,
  error           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notification_preferences (
  user_id         UUID NOT NULL,
  tenant_id       UUID NOT NULL,
  channel         TEXT NOT NULL,                 -- email, in_app
  type            TEXT NOT NULL,
  enabled         BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY (user_id, tenant_id, channel, type)
);
```

RLS by `tenant_id` on both (pattern [sprint 03](03-tenants-and-rls.md)).

---

## `EmailSender` port

```python
class EmailSender(Protocol):
    async def send(
        self, to: list[str], subject: str, html_body: str, text_body: str,
        attachments: list[Attachment] | None = None, reply_to: str | None = None,
    ) -> SendResult: ...
```

Adapters:
- `EmailSenderSes` (prod): boto3 `ses.send_raw_email` (attachment support). `from_address` = email identity verified in console from [sprint 02](02-identity-and-rbac.md). In sandbox it only reaches verified addresses; validated with `alert_email`.
- `EmailSenderSmtp` (dev): `localhost:1025` (Mailpit) via `aiosmtplib`.

Wiring follows README §Shared patterns; `build_email_sender()` branches `EmailSenderSmtp` ↔ `EmailSenderSes(client=boto3.client("ses"), from_address=settings.ses_from_address)`.

## Jinja2 templates

In `apps/api/templates/email/`:
- `invoice_issued.html` / `.txt` — invoice with PDF attached.
- `member_invited.html` — tenant invitation.
- `low_stock_alerted.html` — alert to the owner when a product falls below `StockLevel.min_stock_level` ([sprint 04](04-catalog-and-inventory.md)).
- `password_reset.html` — used by `IdentityProviderLocal`; in prod Cognito sends it.

---

## `notifications_worker` handler

Implements the canonical Lambda consumer pattern ([sprint 07](07-outbox-eventbridge-audit.md)): SQS batch ≤10, parse `body["detail"]`, idempotency with `processed_events(consumer='notifications_worker', event_id)`, partial batch responses.

Branches by `event_type`:
- `InvoiceIssued` → email to `customer.email` with PDF attached (download from S3).
- `MemberInvited` → email with link `https://<dist-id>.cloudfront.net/invitations/{token}/accept` (the SPA resolves the flow and calls `/api/v1/invitations/{token}/accept`). CloudFront domain read from SSM `/nica-erp/demo/web/public_url` (written by `compute/`).
- `LowStockAlerted` → email to the owner.
- `UserRegistered` → welcome email (signup confirmed; written to outbox by sprint 02).
- `NumberSequenceLowAlerted` → email to the owner when the DGI range reaches `low_threshold_pct` ([`../17-compliance-nicaragua.md` §NumberSequence](../17-compliance-nicaragua.md#numbersequence)).

Per event: load context (customer, invoice, PDF from S3) — Lambda in private VPC with egress to RDS:5432 SG (see [`../10-infrastructure.md`](../10-infrastructure.md)). Jinja2 render. Create `Notification` `status='pending'`. `email_sender.send()`. Mark `'sent'` or `'failed'`.

---

## EventBridge rule

LocalStack: setup in `docker/localstack-init.sh` (queue `notif-queue` + DLQ, rule `notif-selective` with event pattern `{"source":["nica-erp"], "detail-type":["InvoiceIssued","MemberInvited","LowStockAlerted","UserRegistered","NumberSequenceLowAlerted"]}` → target `notif-queue`). Precondition: identity (sprint 02) writes `UserRegistered` to outbox; if not implemented, remove from the pattern.

Endpoints: [`../08-api-conventions.md` #notifications](../08-api-conventions.md#notifications).

## Migration 0008

`notifications`, `notification_preferences` with RLS. `notifications.user_id` acts as a natural ownership column. Additional seed in `permissions` + `role_permissions` (see §Permissions below).

---

## Permissions ([ADR-0022](../adr/0022-rbac-model.md))

| Permission | Resources | Default roles |
|---|---|---|
| `notification:read` | `Notification` (always `user_id = me`) | all |
| `notification-preference:write` | `NotificationPreference` | all |
| `notification:resend` | resend to others | admin, owner |

`Notification` has no `*:read-all` variant — each user only sees their inbox. `notification:resend` is reserved to `admin`+ because it allows triggering emails with content crossed between members.

---

## Frontend

Routes `/settings/notifications` (preferences per channel, scoped to the tenant) and `/notifications` (user inbox). Hooks `useListNotifications`, `useGetNotificationPreferences`, `useUpdateNotificationPreferences`, `useResendNotification` (admin). `Switch` per `(channel, type)`; mutation failure reverts the optimistic update and shows a toast. Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: Jinja2 template render with several contexts; handler with `EmailSender` mock.
- Integration: `EmailSenderSmtp` sends to Mailpit (check via `http://localhost:8025/api/v1/messages`).
- E2E: invoice with `customer.email` → ≤5 s → email in Mailpit with PDF attached.

---

## Verifiable outcome (local)

```bash
make worker-outbox & make worker-audit & make worker-notif &
curl -X POST localhost:8000/v1/customers ... -d '{"name":"...","email":"cliente@empresa.test","ruc":"..."}'
curl -X POST localhost:8000/v1/invoices/<id>/issue ...
sleep 5
open http://localhost:8025                                        # email with PDF attached
```

---

## Deploy

### Terraform additions

- **`notifications_worker` Lambda**: container image in VPC, event source mapping from `notif-queue` ([sprint 07](07-outbox-eventbridge-audit.md)). Batch size 5 (slow email), partial batch responses.
- **EventBridge rule `notif-rule`** → `notif-queue` with selective event pattern: `source=["nica-erp"]`, `detail-type=["UserRegistered","InvoiceIssued","LowStockAlerted","MemberInvited","NumberSequenceLowAlerted"]`.
- **SES Configuration Set** (optional, not urgent): without traffic outside sandbox, bounces/complaints ~0. If kept, `nica-erp-default` with event publishing to SNS `nica-erp-bounce-complaint`.
- **IAM**: role `nica-erp-lambda-notif-role` with `AWSLambdaVPCAccessExecutionRole`, `ssm:GetParameter` + `kms:Decrypt`, `ses:SendRawEmail` with condition `ses:FromAddress = <verified_email_identity>`, `sqs:{ReceiveMessage,DeleteMessage}` over `notif-queue`.
- **Migration 0008**: RLS applied.

### Wiring

`EmailSender` already wired from [sprint 02](02-identity-and-rbac.md); the change: the Lambda consumer triggers `EmailSender` from bus events instead of in-process from the backend.

### SES stays in permanent sandbox

Without domain identity there is no DKIM/SPF; external providers would reject or filter sends. The MVP operates with individual email identities (≤50 verified in console). The historical free tier of 62k emails/month from EC2 was **removed in September 2024**; current sandbox quota: 3000 emails/month. When a domain is registered for a prospect, [ADR-0020 §Reversal plan](../adr/0020-no-custom-domain-mvp.md) describes the path (domain identity + DKIM + Service Quotas ticket).

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus:
- Pre: `alert_email` verified in SES sandbox.
- Issue invoice for customer with `email = alert_email` (or another verified address) → ≤2 min → inbox with PDF attached, subject with invoice number.
- `aws ses get-send-statistics --query 'SendDataPoints[-1:].[Timestamp,DeliveryAttempts,Bounces,Complaints]'` → `DeliveryAttempts > 0`, `Bounces = 0`.

Done without exit ticket.
