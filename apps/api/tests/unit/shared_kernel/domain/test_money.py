# apps/api/tests/unit/shared_kernel/domain/test_money.py
"""Unit tests for the Money value object: equality, currency invariants, arithmetic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from shared_kernel.domain.money import CurrencyMismatchError, Money


def test_money_equality_by_value() -> None:
    assert Money(Decimal("10.00"), "NIO") == Money(Decimal("10.00"), "NIO")


def test_money_add_same_currency() -> None:
    a = Money(Decimal("10.00"), "NIO")
    b = Money(Decimal("2.50"), "NIO")
    assert a + b == Money(Decimal("12.50"), "NIO")


def test_money_add_rejects_mixed_currencies() -> None:
    a = Money(Decimal("10.00"), "NIO")
    b = Money(Decimal("1.00"), "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = a + b


def test_money_subtract_same_currency_can_go_negative() -> None:
    a = Money(Decimal("1.00"), "NIO")
    b = Money(Decimal("3.00"), "NIO")
    assert a - b == Money(Decimal("-2.00"), "NIO")


def test_money_subtract_rejects_mixed_currencies() -> None:
    a = Money(Decimal("10.00"), "NIO")
    b = Money(Decimal("1.00"), "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = a - b


def test_money_currency_must_be_3_letter_upper() -> None:
    with pytest.raises(ValueError):
        Money(Decimal("1"), "nio")
    with pytest.raises(ValueError):
        Money(Decimal("1"), "NIOO")


def test_money_coerces_str_amount_to_decimal() -> None:
    m = Money("3.50", "NIO")  # type: ignore[arg-type]
    assert m.amount == Decimal("3.50")


def test_money_negation_preserves_currency() -> None:
    m = Money(Decimal("10.00"), "NIO")
    assert -m == Money(Decimal("-10.00"), "NIO")
