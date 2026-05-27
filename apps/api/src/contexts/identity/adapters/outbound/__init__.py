"""Outbound adapter implementations for the identity context.

Sub-packages:

- ``identity_provider`` — local (DB-backed) and Cognito ``IdentityProvider``
  adapters.
- ``persistence`` — SQLAlchemy-backed ``UserRepository`` plus low-level
  helpers for the ``auth_local_users`` ledger.
- ``email`` — SMTP (Mailpit) and SES ``EmailSender`` adapters, plus the
  signup/password-reset Jinja-free string templates.
"""
