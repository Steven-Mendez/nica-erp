"""Authorization errors mapped to RFC-7807 problem details."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class ForbiddenError(Exception):
    """403 — actor lacks one or more required permissions."""

    missing: tuple[str, ...]

    def __init__(self, *, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        super().__init__(f"Missing permissions: {', '.join(self.missing)}")


__all__ = ["ForbiddenError"]
