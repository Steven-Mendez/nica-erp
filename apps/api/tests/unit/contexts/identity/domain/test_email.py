"""Unit tests for the Email value object."""

from __future__ import annotations

import pytest

from contexts.identity.domain.email import Email


def test_email_lowercases_domain_only() -> None:
    e = Email("Alice@Example.COM")
    assert e.value == "Alice@example.com"


def test_email_rejects_missing_at_sign() -> None:
    with pytest.raises(ValueError):
        Email("not-an-email")


def test_email_rejects_domain_without_dot() -> None:
    with pytest.raises(ValueError):
        Email("a@b")


def test_email_parse_strips_whitespace() -> None:
    assert Email.parse("  alice@example.com  ").value == "alice@example.com"


def test_email_rejects_multiple_at_signs() -> None:
    with pytest.raises(ValueError):
        Email("a@b@c.io")


def test_email_rejects_whitespace_in_value() -> None:
    with pytest.raises(ValueError):
        Email("alice @example.com")


def test_email_rejects_overlong() -> None:
    long_local = "a" * 250
    with pytest.raises(ValueError):
        Email(f"{long_local}@example.com")


def test_email_is_frozen() -> None:
    e = Email("alice@example.com")
    with pytest.raises((AttributeError, TypeError)):
        e.value = "other@example.com"  # type: ignore[misc]
