"""Marker base class for Value Objects.

VOs are immutable, equal by structural value, and never carry identity.
Concrete VOs (Money, Email, …) declare themselves as `@dataclass(frozen=True)`
and inherit from this marker so type checks and `import-linter` boundaries
stay readable.
"""

from __future__ import annotations


class ValueObject:
    """Marker for frozen-dataclass value objects."""

    __slots__ = ()
