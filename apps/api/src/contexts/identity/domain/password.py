"""Password value object + policy validation for the identity context.

The domain layer holds plaintext only transiently; hashing happens in adapter
code. `Password` therefore exists mostly to (a) enforce the policy from sprint
02 and (b) ensure plaintext never leaks through `repr()` or logs.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_LENGTH = 8
_SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?/"


class PasswordPolicyError(ValueError):
    """Raised when a password fails the configured policy."""


@dataclass(frozen=True, slots=True)
class Password:
    value: str

    def __repr__(self) -> str:
        return "Password(***)"

    def validate_policy(self) -> None:
        v = self.value
        if len(v) < _MIN_LENGTH:
            raise PasswordPolicyError(f"Password must be at least {_MIN_LENGTH} characters long")
        has_upper = False
        has_lower = False
        has_digit = False
        has_symbol = False
        for ch in v:
            if "A" <= ch <= "Z":
                has_upper = True
            elif "a" <= ch <= "z":
                has_lower = True
            elif "0" <= ch <= "9":
                has_digit = True
            elif ch in _SYMBOLS:
                has_symbol = True
        if not has_upper:
            raise PasswordPolicyError("Password must contain at least one uppercase letter")
        if not has_lower:
            raise PasswordPolicyError("Password must contain at least one lowercase letter")
        if not has_digit:
            raise PasswordPolicyError("Password must contain at least one digit")
        if not has_symbol:
            raise PasswordPolicyError(
                f"Password must contain at least one symbol from {_SYMBOLS!r}"
            )


__all__ = ["Password", "PasswordPolicyError"]
