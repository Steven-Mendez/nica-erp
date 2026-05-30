"""``Regime`` value object — Nicaragua fiscal regime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RegimeValue = Literal["general", "simplified"]


@dataclass(frozen=True, slots=True)
class Regime:
    value: RegimeValue

    def __post_init__(self) -> None:
        if self.value not in ("general", "simplified"):
            raise ValueError(f"Regime must be 'general' or 'simplified'; got {self.value!r}")


__all__ = ["Regime", "RegimeValue"]
