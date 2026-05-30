"""``AuthorizationDgi`` value object — DGI invoicing authorisation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class AuthorizationDgi:
    number: str
    valid_from: date
    valid_to: date

    def __post_init__(self) -> None:
        if len(self.number) > 32:
            raise ValueError("AuthorizationDgi.number must be ≤ 32 characters")
        if self.valid_to < self.valid_from:
            raise ValueError("AuthorizationDgi.valid_to must be ≥ valid_from")


__all__ = ["AuthorizationDgi"]
