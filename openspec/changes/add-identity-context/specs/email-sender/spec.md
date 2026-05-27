## ADDED Requirements

### Requirement: `EmailSender` port has one method

The `EmailSender` outbound port SHALL declare exactly one method:
`async send(*, to: str, subject: str, html: str, text: str) -> None`.
Both `html` and `text` SHALL be supplied so the adapter can build a
multipart message that degrades gracefully for clients that disable
HTML. The port MUST NOT include attachments in MVP scope.

#### Scenario: Port signature is stable

- **WHEN** `inspect.signature(EmailSender.send).parameters` is
  enumerated
- **THEN** the parameters SHALL be exactly `to`, `subject`, `html`,
  `text` (in addition to `self`), all keyword-only

### Requirement: `EmailSenderSmtp` adapter for Mailpit

`EmailSenderSmtp(host, port)` SHALL connect to the given SMTP host
without STARTTLS and without authentication (Mailpit accepts unsigned
mail on `1025`). It SHALL build a multipart/alternative MIME message
with the `text` part first and the `html` part second. Connection
errors SHALL raise a typed exception so the use case can map to a 5xx
with a stable `code`.

#### Scenario: Mail lands in Mailpit

- **WHEN** `EmailSenderSmtp("localhost", 1025).send(to="a@b.io",
  subject="hi", html="<p>x</p>", text="x")` is awaited
- **THEN** the Mailpit HTTP API `GET /api/v1/messages` SHALL list the
  message with the supplied subject and recipient

### Requirement: `EmailSenderSes` adapter pinned to a verified sender

`EmailSenderSes(client, from_address)` SHALL accept a SESv1 boto3
client (`boto3.client("ses")`) and SHALL call `client.send_email` with
`Source=from_address`, `Destination={"ToAddresses": [to]}`, and
`Message={"Subject": {"Data": subject, "Charset": "UTF-8"},
"Body": {"Html": {"Data": html, "Charset": "UTF-8"}, "Text": {"Data":
text, "Charset": "UTF-8"}}}`. The adapter MUST NOT accept a runtime
override of `from_address`; the sender is fixed at construction time so
the spec contract matches the SES-verified identity.

#### Scenario: Sender address is always the constructor value

- **WHEN** `EmailSenderSes(client, "ops@example.com").send(to=...,
  subject=..., html=..., text=...)` is awaited
- **THEN** the recorded `client.send_email` call SHALL carry
  `Source = "ops@example.com"` regardless of the `to` value

#### Scenario: SES non-2xx raises a typed error

- **WHEN** `client.send_email` raises a `botocore.exceptions.ClientError`
  whose response status is 4xx or 5xx
- **THEN** the adapter SHALL raise its typed error so the use case can
  surface a 5xx with a stable `code`
