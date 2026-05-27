"""Identity bounded context — adapters layer.

Holds the concrete SQLAlchemy / Cognito / SMTP / SES adapters that satisfy
the outbound ports declared in
``contexts.identity.application.ports.outbound``. The application layer
MUST NOT import anything from this package; the composition root in
``bootstrap`` does the wiring.
"""
