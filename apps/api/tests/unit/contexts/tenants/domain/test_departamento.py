"""Unit tests for the ``Departamento`` value object."""

from __future__ import annotations

import pytest

from contexts.tenants.domain.departamento import KNOWN_DEPARTAMENTOS, Departamento


def test_catalog_contains_seventeen_entries() -> None:
    """Audit F-006: the canonical catalog is 15 deps + RAAN + RAAS."""
    assert len(KNOWN_DEPARTAMENTOS) == 17


@pytest.mark.parametrize(
    "name",
    [
        "Boaco",
        "Carazo",
        "Chinandega",
        "Chontales",
        "Estelí",
        "Granada",
        "Jinotega",
        "León",
        "Madriz",
        "Managua",
        "Masaya",
        "Matagalpa",
        "Nueva Segovia",
        "RAAN",
        "RAAS",
        "Rivas",
        "Río San Juan",
    ],
)
def test_every_catalog_value_constructs(name: str) -> None:
    assert Departamento(name).value == name


def test_unknown_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown departamento"):
        Departamento("Atlántico Norte")
