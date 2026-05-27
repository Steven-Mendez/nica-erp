"""Unit tests for :class:`EmailSenderSmtp`.

We monkeypatch :func:`aiosmtplib.send` because spinning up a real SMTP
server here would belong to the integration suite. The multipart shape
of the outgoing message is the load-bearing contract — both ``text``
and ``html`` parts must survive into the message body in that order.
"""

from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import AsyncMock

import aiosmtplib
import pytest

from contexts.identity.adapters.outbound.email.smtp import EmailSenderSmtp
from contexts.identity.application.errors import EmailSendError


@pytest.mark.unit
async def test_smtp_builds_multipart_with_text_and_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, EmailMessage] = {}

    async def _fake_send(
        message: EmailMessage,
        *,
        hostname: str,
        port: int,
    ) -> None:
        captured["message"] = message
        captured["hostname"] = hostname  # type: ignore[assignment]
        captured["port"] = port  # type: ignore[assignment]

    monkeypatch.setattr(aiosmtplib, "send", _fake_send)
    sender = EmailSenderSmtp(host="mailpit.local", port=1025)

    await sender.send(
        to="ops@example.com",
        subject="hi",
        html="<p>x</p>",
        text="x",
    )

    msg = captured["message"]
    assert msg["From"] == "noreply@local.nica-erp.dev"
    assert msg["To"] == "ops@example.com"
    assert msg["Subject"] == "hi"
    payload = msg.get_payload()
    assert isinstance(payload, list)
    # The text part is set first; the HTML alternative is added second.
    assert payload[0].get_content_type() == "text/plain"
    assert payload[1].get_content_type() == "text/html"
    assert "x" in payload[0].get_content()
    assert "<p>x</p>" in payload[1].get_content()


@pytest.mark.unit
async def test_smtp_send_failure_raises_email_send_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_mock = AsyncMock(side_effect=ConnectionRefusedError("nope"))
    monkeypatch.setattr(aiosmtplib, "send", send_mock)
    sender = EmailSenderSmtp(host="mailpit.local", port=1025)

    with pytest.raises(EmailSendError):
        await sender.send(to="a@b.io", subject="hi", html="<p/>", text="x")
