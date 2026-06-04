"""``Departamento`` value object — Nicaraguan administrative division.

Audit F-006: the wizard used to mislabel the 17-department enum as
"municipality"; the canonical fiscal model splits the two so the
backend can hold both the departamento (constrained enum) and the
municipality (free-text).
"""

from __future__ import annotations

from dataclasses import dataclass

# 15 departamentos + 2 autonomous Caribbean regions (RACCN / RACCS,
# historically RAAN / RAAS). Alphabetical order matches the SPA's
# ``DEPARTAMENTOS`` constant so the two never drift.
KNOWN_DEPARTAMENTOS: frozenset[str] = frozenset(
    {
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
    }
)


@dataclass(frozen=True, slots=True)
class Departamento:
    """Departamento value object enforcing the 17-value catalog."""

    value: str

    def __post_init__(self) -> None:
        if self.value not in KNOWN_DEPARTAMENTOS:
            raise ValueError(
                f"Unknown departamento {self.value!r}; "
                "must be one of the 17 Nicaraguan administrative divisions"
            )


__all__ = ["KNOWN_DEPARTAMENTOS", "Departamento"]
