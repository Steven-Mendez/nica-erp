"""Unit tests for the Password value object and policy validation."""

from __future__ import annotations

import pytest

from contexts.identity.domain.password import Password, PasswordPolicyError


def test_compliant_password_passes() -> None:
    Password("Abcdefgh1!23").validate_policy()


def test_short_password_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        Password("Ab1!sho").validate_policy()


def test_missing_uppercase_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        Password("abcdefgh1!23").validate_policy()


def test_missing_lowercase_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        Password("ABCDEFGH1!23").validate_policy()


def test_missing_digit_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        Password("Abcdefghij!@").validate_policy()


def test_missing_symbol_rejected() -> None:
    with pytest.raises(PasswordPolicyError):
        Password("Abcdefgh1234").validate_policy()


def test_repr_masks_value() -> None:
    raw = "Abcdefgh1!23"
    p = Password(raw)
    assert raw not in repr(p)
    assert repr(p) == "Password(***)"
