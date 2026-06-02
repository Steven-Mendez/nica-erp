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


class TestFiscalContact:
    @pytest.mark.parametrize(
        "value",
        ["facturacion@miempresa.ni", "ada@example.com", "x.y+tag@a.bc.de"],
    )
    def test_valid_email(self, value: str) -> None:
        from contexts.tenants.domain.fiscal_contact import FiscalEmail

        assert FiscalEmail(value).value == value

    @pytest.mark.parametrize("value", ["", "no-at-sign", "@nodomain", "u@", "u@x"])
    def test_invalid_email(self, value: str) -> None:
        from contexts.tenants.domain.fiscal_contact import FiscalEmail

        with pytest.raises(ValueError):
            FiscalEmail(value)

    @pytest.mark.parametrize("value", ["+505 8888-8888", "+505 2222-1111", "+505 8888-0000"])
    def test_valid_phone(self, value: str) -> None:
        from contexts.tenants.domain.fiscal_contact import FiscalPhone

        assert FiscalPhone(value).value == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "+505 888-8888",  # short
            "+505 8888-888",  # short
            "+506 8888-8888",  # wrong country code
            "505 8888-8888",  # missing +
            "+5058888-8888",  # missing space
            "+505 88888888",  # missing hyphen
        ],
    )
    def test_invalid_phone(self, value: str) -> None:
        from contexts.tenants.domain.fiscal_contact import FiscalPhone

        with pytest.raises(ValueError):
            FiscalPhone(value)


class TestRegime:
    @pytest.mark.parametrize("value", ["general", "cuota_fija", "pequeno_contribuyente"])
    def test_valid(self, value: str) -> None:
        assert Regime(value).value == value  # type: ignore[arg-type]

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            Regime("custom")  # type: ignore[arg-type]

    def test_legacy_simplified_rejected(self) -> None:
        """Pre-0006 'simplified' is no longer a valid regime value.

        The 0006 migration rewrites any pre-existing rows from
        ``simplified`` to ``cuota_fija`` before the constraint tightens.
        """
        with pytest.raises(ValueError):
            Regime("simplified")  # type: ignore[arg-type]


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
