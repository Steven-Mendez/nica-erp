# `modules/email`

Single-purpose Terraform module that registers **one SES email
identity** for the operator's sender address. This is the entire
outbound-email surface area for the MVP.

## Scope

- One `aws_sesv2_email_identity` resource keyed by `var.from_address`.
- Tagged `Project = nica-erp` for cost attribution.
- Region: `us-east-1` (matches the rest of the demo stack).

## Out of scope (intentional)

- **No domain identity.** The MVP has no controlled DNS zone, so there
  is no way to publish DKIM, SPF, or DMARC records. See
  [ADR-0020](../../../../docs/adr/0020-no-custom-domain-mvp.md).
- **No `MAIL FROM` domain.** Same reason.
- **No DKIM / SPF / Route53.** Same reason.
- **No service-quota request.** The deployment lives permanently in
  the SES sandbox (≤ 50 verified recipient addresses, 200 mails / 24h).
  Exiting the sandbox is post-MVP work and is only meaningful with a
  custom domain.

## Operator verification ritual

After `terraform apply`, AWS sends a verification email to the
configured `from_address`. **The operator must click the verification
link** before the first user signup, or Cognito-triggered emails (and
any `ses:SendEmail` call from the API) will be rejected.

Terraform cannot click the link — this step is operator action, not
infrastructure automation. The `verification_reminder` output and the
`envs/demo` output `ses_verification_reminder` surface this
instruction.

To re-trigger the verification email if the original is lost:

```bash
aws sesv2 put-email-identity-mail-from-attributes \
  --profile nica-erp \
  --region us-east-1 \
  --email-identity "$FROM_ADDRESS"
```

…then re-check the mailbox.

## Sandbox constraints (verify before launch)

- Recipients must each be verified individually.
- Daily send quota: 200 messages.
- Maximum send rate: 1 message / second.

The demo deployment respects these limits by design (single-operator
flows, low signup volume).

## Inputs

| Name           | Type           | Default                  | Description                                                                  |
| -------------- | -------------- | ------------------------ | ---------------------------------------------------------------------------- |
| `from_address` | `string`       | required                 | Operator's email address registered as the SES sender identity.              |
| `tags`         | `map(string)`  | `{ Project = nica-erp }` | Tag set merged onto the SES identity.                                        |

## Outputs

| Name                    | Description                                                                                          |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| `from_address`          | Echo of the registered sender address.                                                               |
| `verification_reminder` | Human-readable instruction reminding the operator to verify the SES sender before the first signup. |
