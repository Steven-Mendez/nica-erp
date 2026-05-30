"""``Ruc`` value object — Nicaragua tax-ID structural validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

# DGI's Registro Único de Contribuyentes is a 14-character string. The first
# 13 characters are digits and the 14th is an uppercase letter checksum-style
# suffix. We deliberately keep the validation structural (length + alphabet)
# instead of implementing the DGI checksum — the checksum table is not
# publicly stable and SMEs occasionally hold legacy RUCs that don't match
# the modern formula. Treat the column as "operator-asserted format" and
# let the DGI authorisation flow reject genuinely invalid RUCs downstream.
_RUC_RE = re.compile(r"^\d{13}[A-Z]$")


@dataclass(frozen=True, slots=True)
class Ruc:
    value: str

    def __post_init__(self) -> None:
        if not _RUC_RE.match(self.value):
            raise ValueError(
                "Ruc must be 13 digits followed by one uppercase letter (e.g. '0010101800010X')"
            )

    @classmethod
    def parse(cls, raw: str) -> Ruc:
        return cls(raw.strip())


__all__ = ["Ruc"]
