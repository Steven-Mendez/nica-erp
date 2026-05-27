"""Packaged email templates + tiny string-substitution renderer.

We deliberately avoid Jinja2: the only substitution is the 6-digit
verification ``{{code}}``, so a one-line ``.replace`` is faster, has zero
runtime dependencies, and removes a template-injection attack surface.

The ``.html`` / ``.txt`` files in this package are loaded via
:mod:`importlib.resources` so the adapter keeps working when the wheel is
installed (no filesystem assumption).
"""

from __future__ import annotations

# Project targets Python 3.13+ (see apps/api/pyproject.toml); the 3.7
# backport (`importlib_resources`) is unnecessary.
from importlib.resources import (
    files,  # nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
)

_PACKAGE = "contexts.identity.adapters.outbound.email.templates"

# Templates are bundled with the wheel and immutable at runtime — read
# them once at module import so `render()` stays in-memory and never
# touches disk (or blocks the event loop) on the per-email hot path.
_BASE = files(_PACKAGE)
_TEMPLATES: dict[str, tuple[str, str]] = {
    name: (
        _BASE.joinpath(f"{name}.html").read_text(encoding="utf-8"),
        _BASE.joinpath(f"{name}.txt").read_text(encoding="utf-8"),
    )
    for name in ("signup_verification", "password_reset")
}


def render(name: str, *, code: str) -> tuple[str, str]:
    """Return ``(html, text)`` for the named template.

    ``name`` selects the basename: ``"signup_verification"`` or
    ``"password_reset"``. The verification code is substituted via a
    literal ``{{code}}`` placeholder.
    """

    try:
        html_tpl, text_tpl = _TEMPLATES[name]
    except KeyError as exc:
        raise FileNotFoundError(f"unknown email template: {name!r}") from exc
    return html_tpl.replace("{{code}}", code), text_tpl.replace("{{code}}", code)


__all__ = ["render"]
