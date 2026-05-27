"""Email value object for the identity context.

The domain treats an Email as an immutable, validated string. The local-part
is preserved as supplied (RFC 5321 allows case-sensitive local-parts) while
the domain portion is lowercased for canonical comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared_kernel.domain.value_object import ValueObject

# Conservative validation: exactly one `@`, no whitespace, dot in the domain,
# total length ≤ 254. Compiled once at module load.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MAX_LENGTH = 254


@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        raw = self.value
        if not isinstance(raw, str):  # defensive — Email("…") only
            raise ValueError(f"Email must be a string, got {type(raw).__name__}")
        if len(raw) == 0 or len(raw) > _MAX_LENGTH:
            raise ValueError(f"Email length must be 1..{_MAX_LENGTH} chars")
        if raw.count("@") != 1:
            raise ValueError(f"Email must contain exactly one '@': {raw!r}")
        if not _EMAIL_RE.match(raw):
            raise ValueError(f"Email is not a valid address: {raw!r}")

        local, _, domain = raw.partition("@")
        canonical = f"{local}@{domain.lower()}"
        if canonical != raw:
            object.__setattr__(self, "value", canonical)

    @classmethod
    def parse(cls, value: str) -> Email:
        return cls(value.strip())


__all__ = ["Email"]
