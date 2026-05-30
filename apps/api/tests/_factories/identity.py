"""Identity-context domain object builders.

The canonical password literal is kept identical to ``E2E_PASSWORD`` in
``tests/e2e/conftest.py`` so identity flows remain cross-layer consistent
— a unit test that builds a password is using the same string the e2e
suite will type into the SPA's login form.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from contexts.identity.domain.email import Email
from contexts.identity.domain.password import Password
from contexts.identity.domain.user import User

CANONICAL_PASSWORD = "Demo1234!@xy"


def make_password(value: str = CANONICAL_PASSWORD) -> Password:
    """Return a ``Password`` whose ``validate_policy()`` succeeds.

    The default is the same literal the e2e suite uses, so a test that
    constructs the password matches the string a real user would type.
    """

    return Password(value)


def make_user(
    *,
    external_sub: str | None = None,
    email: str = "user@nica-erp.test",
    now: datetime | None = None,
) -> User:
    """Return a ``User`` aggregate ready for unit tests.

    The aggregate is constructed via ``register`` so the
    ``UserRegistered`` event lands in ``pop_events()``. ``external_sub``
    must be a valid UUID string — production uses Cognito's ``sub`` claim
    or the local IdP's row id; the factory generates one when omitted.
    """

    moment = now or datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    sub = external_sub or str(uuid4())
    return User.register(
        external_sub=sub,
        email=Email(email),
        now=moment,
    )
