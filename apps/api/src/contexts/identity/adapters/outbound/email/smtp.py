"""SMTP-backed ``EmailSender`` adapter.

Targets Mailpit (and any unauthenticated SMTP server) on
``settings.smtp_host``/``settings.smtp_port``. Builds a
``multipart/alternative`` MIME message with the ``text`` part first so
mail clients that disable HTML still render the body verbatim. Connection
or send errors are mapped to :class:`EmailSendError` so the use case can
surface a stable 5xx ``code``.
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from contexts.identity.application.errors import EmailSendError


class EmailSenderSmtp:
    """``EmailSender`` adapter for SMTP servers without auth (Mailpit/MailHog)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str = "noreply@local.nica-erp.dev",
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = to
        msg["Subject"] = subject
        # set_content -> text/plain; add_alternative -> text/html, in that
        # order so multipart/alternative degrades to the text part for
        # clients that disable HTML rendering.
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            await aiosmtplib.send(msg, hostname=self._host, port=self._port)
        except Exception as exc:
            raise EmailSendError(f"SMTP send failed: {exc}") from exc


__all__ = ["EmailSenderSmtp"]
