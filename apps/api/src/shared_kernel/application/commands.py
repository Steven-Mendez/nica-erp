"""Marker base classes for CQRS messages."""

from __future__ import annotations


class Command:
    """Mutating intent. Subclass as `@dataclass(frozen=True)` with payload fields."""

    __slots__ = ()


class Query:
    """Read intent. Subclass as `@dataclass(frozen=True)` with filter fields."""

    __slots__ = ()
