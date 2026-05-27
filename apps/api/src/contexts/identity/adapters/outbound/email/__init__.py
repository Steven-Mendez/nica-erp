"""Email-sender adapters for the identity context.

Modules:

- ``smtp`` — :class:`EmailSenderSmtp` targeting Mailpit / any SMTP server.
- ``ses`` — :class:`EmailSenderSes` targeting AWS SES via a boto3 client.
- ``templates`` — packaged ``.html`` / ``.txt`` bodies for signup and reset
  emails; rendered by :func:`render` in :mod:`.templates`.
"""
