"""Password value object + policy validation for the identity context.

The domain layer holds plaintext only transiently; hashing happens in adapter
code. `Password` therefore exists mostly to (a) enforce the policy from sprint
02 and (b) ensure plaintext never leaks through `repr()` or logs.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_LENGTH = 12
_MAX_LENGTH = 128
_SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?/"


class PasswordPolicyError(ValueError):
    """Raised when a password fails the configured policy.

    ``failed_rules`` carries the structured list of rule names that
    failed so the HTTP layer can surface each rule individually. Empty
    by default for back-compat with callers that only need the message.
    """

    def __init__(self, message: str, *, failed_rules: list[str] | None = None) -> None:
        super().__init__(message)
        self.failed_rules: list[str] = list(failed_rules or [])


@dataclass(frozen=True, slots=True)
class Password:
    value: str

    def __repr__(self) -> str:
        return "Password(***)"

    def validate_policy(self) -> None:
        v = self.value
        failed: list[str] = []
        if len(v) < _MIN_LENGTH:
            failed.append("min_length")
        if len(v) > _MAX_LENGTH:
            failed.append("max_length")
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
            failed.append("uppercase_missing")
        if not has_lower:
            failed.append("lowercase_missing")
        if not has_digit:
            failed.append("digit_missing")
        if not has_symbol:
            failed.append("symbol_missing")
        if failed:
            raise PasswordPolicyError(f"Password fails policy: {failed}", failed_rules=failed)


__all__ = ["Password", "PasswordPolicyError"]
