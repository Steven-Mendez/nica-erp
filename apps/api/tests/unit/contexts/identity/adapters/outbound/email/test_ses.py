"""Unit tests for :class:`EmailSenderSes`.

botocore is not a project dependency (SES wiring only matters in AWS),
so we synthesise a stand-in ``ClientError`` class and inject a
``MagicMock`` SES client. The contract under test is the exact
``send_email`` kwargs shape required by the email-sender spec.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from contexts.identity.adapters.outbound.email import ses as ses_module
from contexts.identity.adapters.outbound.email.ses import EmailSenderSes
from contexts.identity.application.errors import EmailSendError


@pytest.mark.unit
async def test_ses_send_passes_canonical_payload() -> None:
    client = MagicMock()
    sender = EmailSenderSes(client=client, from_address="ops@example.com")

    await sender.send(
        to="customer@example.com",
        subject="hello",
        html="<p>hi</p>",
        text="hi",
    )

    client.send_email.assert_called_once_with(
        Source="ops@example.com",
        Destination={"ToAddresses": ["customer@example.com"]},
        Message={
            "Subject": {"Data": "hello", "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": "<p>hi</p>", "Charset": "UTF-8"},
                "Text": {"Data": "hi", "Charset": "UTF-8"},
            },
        },
    )


@pytest.mark.unit
async def test_ses_send_wraps_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Synthesise a botocore.exceptions module with a ClientError class so
    # the adapter catches the right exception even without boto3 installed.
    fake_botocore = types.ModuleType("botocore")
    fake_exceptions = types.ModuleType("botocore.exceptions")

    class _ClientError(Exception):
        pass

    fake_exceptions.ClientError = _ClientError  # type: ignore[attr-defined]
    fake_botocore.exceptions = fake_exceptions  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_exceptions)

    # Force the helper to pick up the freshly-injected ClientError class.
    monkeypatch.setattr(ses_module, "_load_client_error", lambda: _ClientError)

    client = MagicMock()
    client.send_email.side_effect = _ClientError("ses down")
    sender = EmailSenderSes(client=client, from_address="ops@example.com")

    with pytest.raises(EmailSendError):
        await sender.send(to="a@b.io", subject="hi", html="<p/>", text="x")


@pytest.mark.unit
async def test_ses_from_address_is_fixed_at_construction() -> None:
    client = MagicMock()
    sender = EmailSenderSes(client=client, from_address="ops@example.com")
    await sender.send(to="other@example.com", subject="s", html="<p/>", text="t")
    kwargs = client.send_email.call_args.kwargs
    assert kwargs["Source"] == "ops@example.com"
