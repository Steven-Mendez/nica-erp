"""EmailSender outbound port.

The SMTP and SES adapters both implement this single-method Protocol. The
caller provides both an HTML and a plain-text body so the SMTP adapter can
attach them as a multipart message and the SES adapter can forward them
verbatim. There is intentionally no "verify sender" or "list identities"
method — those are operator concerns, not application concerns.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, html: str, text: str) -> None: ...


__all__ = ["EmailSender"]
