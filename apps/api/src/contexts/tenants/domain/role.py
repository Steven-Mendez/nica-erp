"""``Role`` enum — the five MVP roles in privilege-ascent order."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    SALESPERSON = "salesperson"
    ACCOUNTANT = "accountant"
    ADMIN = "admin"
    OWNER = "owner"

    @classmethod
    def from_str(cls, raw: str) -> Role:
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"Unknown role {raw!r}; valid roles: {[r.value for r in cls]}"
            ) from exc


__all__ = ["Role"]
