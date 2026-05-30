"""Contract tests for :class:`CreateTenantRequest`.

Only `name` is required; every fiscal field is `Optional[...]`.
"""

from __future__ import annotations

from contexts.tenants.adapters.inbound.http.schemas import CreateTenantRequest


def test_name_only_payload_is_accepted() -> None:
    body = CreateTenantRequest.model_validate({"name": "Mi Empresa"})
    assert body.name == "Mi Empresa"
    assert body.ruc is None
    assert body.regime is None
    assert body.municipality is None
    assert body.authorization_dgi is None
    assert body.fiscal_address is None
    assert body.is_withholder is False


def test_name_plus_is_withholder_payload_is_accepted() -> None:
    body = CreateTenantRequest.model_validate({"name": "Mi Empresa", "is_withholder": False})
    assert body.name == "Mi Empresa"
    assert body.authorization_dgi is None


def test_explicit_null_payload_is_accepted() -> None:
    body = CreateTenantRequest.model_validate(
        {
            "name": "Mi Empresa",
            "ruc": None,
            "regime": None,
            "municipality": None,
            "authorization_dgi": None,
            "fiscal_address": None,
        }
    )
    assert body.ruc is None
    assert body.regime is None
    assert body.authorization_dgi is None


def test_full_payload_validates() -> None:
    body = CreateTenantRequest.model_validate(
        {
            "name": "Empresa A",
            "ruc": "0010101800010X",
            "regime": "general",
            "municipality": "Managua",
            "authorization_dgi": {
                "number": "A-001",
                "valid_from": "2026-01-01",
                "valid_to": "2027-01-01",
            },
            "fiscal_address": "Rotonda Centroamérica, Managua",
            "is_withholder": True,
        }
    )
    assert body.ruc == "0010101800010X"
    assert body.regime == "general"
    assert body.authorization_dgi is not None
    assert body.authorization_dgi.number == "A-001"
