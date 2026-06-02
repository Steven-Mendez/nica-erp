"""Fiscal-contact value objects — email + phone surfaced on invoices.

These are intentionally narrow types: the domain only needs to
guarantee that the strings hitting persistence match the documented
shape. Heavier validation (DNS resolution, MX checks, dialing into
the phone) belongs at the integration boundary, not in domain rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Pragmatic email check — `local@domain.tld` with at least one dot in
# the domain. Matches what the SPA's Zod schema requires; the goal is
# to reject obvious typos (``foo``) not to be RFC-5322 perfect.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

# Nicaraguan phone in international format: ``+505 NNNN-NNNN``. The SPA
# masks input to this shape; the domain accepts the masked form.
_PHONE_RE = re.compile(r"^\+505 \d{4}-\d{4}$")


@dataclass(frozen=True, slots=True)
class FiscalEmail:
    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_RE.match(self.value):
            raise ValueError(f"Invalid fiscal email: {self.value!r}")


@dataclass(frozen=True, slots=True)
class FiscalPhone:
    """Nicaraguan phone in the canonical ``+505 NNNN-NNNN`` shape."""

    value: str

    def __post_init__(self) -> None:
        if not _PHONE_RE.match(self.value):
            raise ValueError(f"Invalid fiscal phone (expected '+505 NNNN-NNNN'): {self.value!r}")


__all__ = ["FiscalEmail", "FiscalPhone"]
