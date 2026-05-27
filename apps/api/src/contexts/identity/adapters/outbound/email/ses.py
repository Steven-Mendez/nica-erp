"""AWS SES (SESv1)-backed ``EmailSender`` adapter.

Wraps a synchronous boto3 ``ses`` client in :func:`asyncio.to_thread` so
the port stays async. The ``from_address`` is fixed at construction time
to match the SES-verified identity — runtime callers MUST NOT override
it.

``botocore`` is intentionally NOT in the API project's runtime
dependency list (SES wiring only matters in the AWS deployment), so the
``ClientError`` lookup is deferred to the ``send`` body via
:func:`_load_client_error`. When boto3/botocore is unavailable we fall
back to catching the broad :class:`Exception` family — the operational
risk is acceptable because the SES adapter is only ever wired when the
AWS deployment installs botocore as part of its boto3 stack.

The client itself is typed as :class:`Any` because boto3's stubs are not
vendored here.
"""

from __future__ import annotations

import asyncio
from typing import Any

from contexts.identity.application.errors import EmailSendError


def _load_client_error() -> type[BaseException]:
    """Return ``botocore.exceptions.ClientError`` if installed, else ``Exception``.

    Centralising the import here keeps the module importable in environments
    that do not ship botocore (local dev, unit tests) while still mapping
    real SES failures to :class:`EmailSendError` in AWS deployments.
    """

    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return Exception
    cls: type[BaseException] = ClientError
    return cls


class EmailSenderSes:
    """``EmailSender`` adapter that calls SESv1's ``send_email``."""

    def __init__(self, *, client: Any, from_address: str) -> None:
        self._client = client
        self._from = from_address

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        client_error = _load_client_error()
        try:
            await asyncio.to_thread(
                self._client.send_email,
                Source=self._from,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html, "Charset": "UTF-8"},
                        "Text": {"Data": text, "Charset": "UTF-8"},
                    },
                },
            )
        except client_error as exc:
            raise EmailSendError(f"SES send failed: {exc}") from exc


__all__ = ["EmailSenderSes"]
