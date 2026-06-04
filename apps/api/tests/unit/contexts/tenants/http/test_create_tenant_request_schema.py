"""Contract tests for :class:`CreateTenantRequest`.

Only `name` is required; every fiscal field is `Optional[...]`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def test_departamento_from_catalog_is_accepted() -> None:
    body = CreateTenantRequest.model_validate({"name": "Mi Empresa", "departamento": "Managua"})
    assert body.departamento == "Managua"


def test_unknown_departamento_is_rejected_with_spanish_copy() -> None:
    """Audit F-006: the schema pins departamento to the 17-value catalog."""
    with pytest.raises(ValidationError) as exc_info:
        CreateTenantRequest.model_validate(
            {"name": "Mi Empresa", "departamento": "Atlántico Norte"}
        )
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("departamento",) and "inválido" in str(e["msg"]) for e in errors)


def test_municipality_is_free_text() -> None:
    body = CreateTenantRequest.model_validate(
        {"name": "Mi Empresa", "departamento": "Managua", "municipality": "Distrito V"}
    )
    assert body.municipality == "Distrito V"


def test_name_with_angle_brackets_is_rejected() -> None:
    """Audit F-019: silently stripping `<` and `>` corrupted operator input.
    The schema MUST reject the input and surface a Spanish message."""
    with pytest.raises(ValidationError) as exc_info:
        CreateTenantRequest.model_validate({"name": "<script>Mi Empresa"})
    errors = exc_info.value.errors()
    assert any(
        e["loc"] == ("name",) and "<" in str(e["msg"]) and ">" in str(e["msg"]) for e in errors
    )
