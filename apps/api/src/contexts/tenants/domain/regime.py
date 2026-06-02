"""``Regime`` value object — Nicaragua fiscal regime.

The three values mirror the Nicaraguan DGI tax-regime categories:

- ``general`` — Régimen general: standard quarterly IR + monthly IVA
  filings, applies to most established businesses.
- ``cuota_fija`` — Cuota fija: flat monthly fee for micro-enterprises
  below the DGI's small-business thresholds; the operator does not
  file VAT.
- ``pequeno_contribuyente`` — Pequeño contribuyente: a simplified
  intermediate regime introduced in the 2020 tax reform; still files
  monthly but with reduced rate tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RegimeValue = Literal["general", "cuota_fija", "pequeno_contribuyente"]

_ALLOWED: tuple[RegimeValue, ...] = ("general", "cuota_fija", "pequeno_contribuyente")


@dataclass(frozen=True, slots=True)
class Regime:
    value: RegimeValue

    def __post_init__(self) -> None:
        if self.value not in _ALLOWED:
            raise ValueError(f"Regime must be one of {_ALLOWED!r}; got {self.value!r}")


__all__ = ["Regime", "RegimeValue"]
