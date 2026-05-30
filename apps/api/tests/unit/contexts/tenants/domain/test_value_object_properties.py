"""Property-based tests for the tenants value objects.

The hand-written ``test_value_objects.py`` documents boundary cases.
This suite searches the whole input space so a future change to the
``Ruc`` regex, the ``KNOWN_MUNICIPALITIES`` catalog, or the ``Regime``
literal set fails immediately if it weakens the invariant.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from contexts.tenants.domain import KNOWN_MUNICIPALITIES, Municipality, Regime, Ruc

_RUC_RE = re.compile(r"^\d{13}[A-Z]$")
_VALID_REGIMES = ("general", "simplified")


# --- Ruc ------------------------------------------------------------------


@st.composite
def valid_ruc(draw: st.DrawFn) -> str:
    digits = "".join(draw(st.sampled_from("0123456789")) for _ in range(13))
    suffix = draw(st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    return digits + suffix


_WS = st.text(alphabet=" \t", max_size=4)


@given(valid_ruc(), _WS, _WS)
def test_ruc_parse_accepts_any_regex_match(body: str, lead: str, trail: str) -> None:
    raw = f"{lead}{body}{trail}"
    assert Ruc.parse(raw).value == body


@given(st.text(min_size=0, max_size=20))
def test_ruc_parse_rejects_anything_else(value: str) -> None:
    assume(not _RUC_RE.match(value.strip()))
    with pytest.raises(ValueError):
        Ruc.parse(value)


# --- Municipality ---------------------------------------------------------


@given(st.sampled_from(sorted(KNOWN_MUNICIPALITIES)))
def test_known_municipality_always_accepted(value: str) -> None:
    assert Municipality(value).value == value


@given(st.text(min_size=0, max_size=24))
def test_unknown_municipality_always_rejected(value: str) -> None:
    assume(value not in KNOWN_MUNICIPALITIES)
    with pytest.raises(ValueError):
        Municipality(value)


# --- Regime ---------------------------------------------------------------


@given(st.sampled_from(_VALID_REGIMES))
def test_valid_regime_always_accepted(value: str) -> None:
    assert Regime(value).value == value  # type: ignore[arg-type]


@given(st.text(min_size=0, max_size=24))
def test_invalid_regime_always_rejected(value: str) -> None:
    assume(value not in _VALID_REGIMES)
    with pytest.raises(ValueError):
        Regime(value)  # type: ignore[arg-type]
