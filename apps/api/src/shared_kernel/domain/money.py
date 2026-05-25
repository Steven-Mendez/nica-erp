from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from shared_kernel.domain.value_object import ValueObject


class CurrencyMismatchError(ValueError):
    """Raised when arithmetic mixes two different currencies."""

    def __init__(self, left: str, right: str) -> None:
        super().__init__(f"Currency mismatch: {left} vs {right}")
        self.left = left
        self.right = right


@dataclass(frozen=True, slots=True)
class Money(ValueObject):
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if not self.currency or len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"currency must be a 3-letter uppercase code, got {self.currency!r}")

    def _same(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)
