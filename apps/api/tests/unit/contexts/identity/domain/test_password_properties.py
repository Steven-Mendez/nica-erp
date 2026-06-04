"""Property-based tests for the ``Password`` value object.

The hand-written ``test_password.py`` covers the boundary documentation
("this minimum-length string is rejected"). This suite asks the stronger
question: does the policy hold across the *whole* input space, not just
the five strings a reviewer thought of?
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Mirror the symbol whitelist exposed by ``password._SYMBOLS``. We import
# it through ``getattr`` so the test fails loudly if the module renames or
# removes the constant — that is a real signal, not a bug in this test.
import contexts.identity.domain.password as _pwd_mod
from contexts.identity.domain.password import Password, PasswordPolicyError

_SYMBOLS = _pwd_mod._SYMBOLS
_MIN_LENGTH = _pwd_mod._MIN_LENGTH

_ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ASCII_LOWER = "abcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"

# Every character the policy accepts as "neutral filler" (i.e. counts
# toward length but does not satisfy any class). We deliberately
# constrain to the four canonical classes so the strategy never accidentally
# adds an extra class to a "missing X" example.
_ALL_CLASSES = st.sampled_from(list(_ASCII_UPPER + _ASCII_LOWER + _DIGITS + _SYMBOLS))


@st.composite
def policy_compliant_password(draw: st.DrawFn) -> str:
    """Generate a string that satisfies every policy rule."""

    upper = draw(st.sampled_from(_ASCII_UPPER))
    lower = draw(st.sampled_from(_ASCII_LOWER))
    digit = draw(st.sampled_from(_DIGITS))
    symbol = draw(st.sampled_from(_SYMBOLS))
    # ``_MIN_LENGTH - 4`` more characters drawn from the same alphabet so
    # the result always meets the minimum length without growing huge.
    extra = draw(
        st.lists(
            _ALL_CLASSES,
            min_size=max(0, _MIN_LENGTH - 4),
            max_size=_MIN_LENGTH + 8,
        )
    )
    body = [upper, lower, digit, symbol, *extra]
    # Shuffle deterministically by drawing a permutation order.
    perm = draw(st.permutations(body))
    return "".join(perm)


def _classes_present(s: str) -> set[str]:
    seen: set[str] = set()
    for ch in s:
        if ch in _ASCII_UPPER:
            seen.add("upper")
        elif ch in _ASCII_LOWER:
            seen.add("lower")
        elif ch in _DIGITS:
            seen.add("digit")
        elif ch in _SYMBOLS:
            seen.add("symbol")
    return seen


@given(policy_compliant_password())
def test_compliant_password_always_passes(value: str) -> None:
    Password(value).validate_policy()


@given(st.text(alphabet=_ALL_CLASSES, max_size=_MIN_LENGTH - 1))
def test_too_short_always_rejected(value: str) -> None:
    assume(len(value) < _MIN_LENGTH)
    with pytest.raises(PasswordPolicyError):
        Password(value).validate_policy()


@given(st.text(alphabet=_ALL_CLASSES, min_size=_MIN_LENGTH, max_size=_MIN_LENGTH + 8))
@settings(suppress_health_check=[HealthCheck.filter_too_much])
def test_missing_a_class_always_rejected(value: str) -> None:
    classes = _classes_present(value)
    assume(len(classes) < 4)
    with pytest.raises(PasswordPolicyError):
        Password(value).validate_policy()


@given(st.text(min_size=1, max_size=64))
def test_repr_is_always_the_masked_literal(value: str) -> None:
    # The invariant is that ``repr`` reveals nothing about the value —
    # it always returns the same masked literal, regardless of the
    # secret. That literal happens to contain '*', so a ``value not in
    # repr`` check would yield false positives on single-character
    # secrets; the constant-equality check is the right shape.
    assert repr(Password(value)) == "Password(***)"
