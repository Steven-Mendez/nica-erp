"""Unit tests for tenants value objects."""

from __future__ import annotations

from datetime import date

import pytest

from contexts.tenants.domain import (
    KNOWN_MUNICIPALITIES,
    AuthorizationDgi,
    Municipality,
    Regime,
    Role,
    Ruc,
)


class TestRuc:
    def test_valid_ruc(self) -> None:
        ruc = Ruc.parse("0010101800010X")
        assert ruc.value == "0010101800010X"

    def test_trimmed(self) -> None:
        assert Ruc.parse("  0010101800010X  ").value == "0010101800010X"

    @pytest.mark.parametrize(
        "raw", ["", "123", "0010101800010", "0010101800010x", "ABCDEFGHIJKLMN"]
    )
    def test_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            Ruc.parse(raw)


class TestMunicipality:
    def test_known(self) -> None:
        assert Municipality("Managua").value == "Managua"

    def test_unknown(self) -> None:
        with pytest.raises(ValueError):
            Municipality("Atlantis")

    def test_catalog_non_empty(self) -> None:
        assert len(KNOWN_MUNICIPALITIES) >= 17


class TestRegime:
    @pytest.mark.parametrize("value", ["general", "simplified"])
    def test_valid(self, value: str) -> None:
        assert Regime(value).value == value  # type: ignore[arg-type]

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            Regime("custom")  # type: ignore[arg-type]


class TestAuthorizationDgi:
    def test_valid(self) -> None:
        vo = AuthorizationDgi(
            number="A-001", valid_from=date(2026, 1, 1), valid_to=date(2027, 1, 1)
        )
        assert vo.number == "A-001"

    def test_reversed_range(self) -> None:
        with pytest.raises(ValueError):
            AuthorizationDgi(
                number="A-001",
                valid_from=date(2027, 1, 1),
                valid_to=date(2026, 1, 1),
            )

    def test_number_too_long(self) -> None:
        with pytest.raises(ValueError):
            AuthorizationDgi(
                number="X" * 33, valid_from=date(2026, 1, 1), valid_to=date(2027, 1, 1)
            )

    def test_empty_number_accepted(self) -> None:
        AuthorizationDgi(number="", valid_from=date(1970, 1, 1), valid_to=date(1970, 1, 1))


class TestRole:
    def test_from_str(self) -> None:
        assert Role.from_str("admin") is Role.ADMIN

    def test_unknown(self) -> None:
        with pytest.raises(ValueError):
            Role.from_str("god")

    def test_iteration_order(self) -> None:
        assert list(Role) == [
            Role.VIEWER,
            Role.SALESPERSON,
            Role.ACCOUNTANT,
            Role.ADMIN,
            Role.OWNER,
        ]
