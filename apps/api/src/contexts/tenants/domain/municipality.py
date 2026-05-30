"""``Municipality`` value object backed by an extensible catalog."""

from __future__ import annotations

from dataclasses import dataclass

# Seventeen Nicaragua departmental capitals — the MVP supports issuing
# fiscal documents from any of them. Cabeceras y municipios adicionales
# se añaden aquí en una sola línea cuando los requiera un tenant.
KNOWN_MUNICIPALITIES: frozenset[str] = frozenset(
    {
        "Managua",
        "León",
        "Granada",
        "Masaya",
        "Estelí",
        "Matagalpa",
        "Chinandega",
        "Jinotega",
        "Nueva Segovia",
        "Madriz",
        "Boaco",
        "Carazo",
        "Chontales",
        "Rivas",
        "Río San Juan",
        "RAAN",
        "RAAS",
    }
)


@dataclass(frozen=True, slots=True)
class Municipality:
    value: str

    def __post_init__(self) -> None:
        if self.value not in KNOWN_MUNICIPALITIES:
            raise ValueError(f"Unknown municipality {self.value!r}; extend KNOWN_MUNICIPALITIES")


__all__ = ["KNOWN_MUNICIPALITIES", "Municipality"]
