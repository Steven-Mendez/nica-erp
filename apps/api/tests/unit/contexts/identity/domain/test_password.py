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


def test_eight_char_password_rejected_for_audit_f036() -> None:
    """Audit F-036: the SPA used to show two policies (8+ vs 12+).
    The canonical policy is 12+, so an 8-char password is rejected
    even when all 4 character classes are present.
    """
    with pytest.raises(PasswordPolicyError) as exc_info:
        Password("Short1!a").validate_policy()
    assert "min_length" in exc_info.value.failed_rules


def test_failed_rules_lists_all_violations() -> None:
    """Caller can read every rule that failed in one pass."""
    with pytest.raises(PasswordPolicyError) as exc_info:
        Password("short").validate_policy()
    failed = exc_info.value.failed_rules
    assert "min_length" in failed
    assert "uppercase_missing" in failed
    assert "digit_missing" in failed
    assert "symbol_missing" in failed
