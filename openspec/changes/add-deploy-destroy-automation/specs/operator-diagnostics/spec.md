## ADDED Requirements

### Requirement: `make logs` tails the API CloudWatch log group

The root `Makefile` SHALL declare a target `logs` delegating to
`scripts/tail-logs.sh`. The script SHALL invoke
`aws logs tail /nica-erp/api --follow --since 5m --format short`
and SHALL pass through SIGINT to terminate cleanly.

#### Scenario: logs streams API output

- **WHEN** `make logs` is run with the API service healthy
- **THEN** within 5 seconds, stdout SHALL include at least one log
  line emitted by the API task (e.g. a `GET /api/healthz` access
  line)

### Requirement: `make urls` prints the public endpoints

The root `Makefile` SHALL declare a target `urls` delegating to
`scripts/print-urls.sh`. The script SHALL read
`cloudfront_distribution_domain` from
`terraform -chdir=infra/terraform/bootstrap output` and SHALL
print exactly two lines:

- `https://<dist-id>.cloudfront.net/`
- `https://<dist-id>.cloudfront.net/api/healthz`

#### Scenario: urls is parseable by other scripts

- **WHEN** `make urls` is run and its stdout is piped to
  `head -n 1`
- **THEN** the first line SHALL match the pattern
  `^https://[a-z0-9]+\.cloudfront\.net/$`

### Requirement: `check-credentials.sh` validates the AWS caller

`scripts/check-credentials.sh` SHALL run
`aws sts get-caller-identity` and SHALL exit non-zero if the call
fails. When the environment variable `AWS_ACCOUNT_ID` is set, the
script SHALL also verify that the returned `Account` field matches
exactly and SHALL exit non-zero with a diagnostic if it does not.
On success the script SHALL print the caller identity to stdout
and exit `0`.

#### Scenario: Unset AWS_ACCOUNT_ID does not block the script

- **WHEN** `check-credentials.sh` is run with `AWS_ACCOUNT_ID`
  unset and a valid AWS profile
- **THEN** the script SHALL exit `0` and stdout SHALL include the
  JSON returned by `aws sts get-caller-identity`

#### Scenario: Mismatched AWS_ACCOUNT_ID aborts deploy

- **WHEN** `AWS_ACCOUNT_ID=123456789012 make deploy` is run while
  authenticated against account `999999999999`
- **THEN** `check-credentials.sh` SHALL exit non-zero, the
  diagnostic SHALL name both account IDs, and no Terraform or AWS
  mutation SHALL have been issued
