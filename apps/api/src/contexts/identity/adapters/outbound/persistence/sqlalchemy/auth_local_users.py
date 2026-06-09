"""Pre-built Core statements for ``auth_local_users``.

The local IdP adapter is large enough that inlining every statement
hurts readability. Hoisting them here keeps the IdP class focused on
policy and gives mypy a single place to type-check the projection.

Every statement is parameterised; the IdP supplies bound parameters via
:meth:`SqlAlchemyUnitOfWork.current_session.execute`. UPDATE statements
take their WHERE id as ``b_id`` — ``bindparam("id")`` is reserved
inside update() because it names a column of the target table.
"""

from __future__ import annotations

from sqlalchemy import Text, bindparam, cast, func, insert, literal, select, true, update
from sqlalchemy.dialects.postgresql import ARRAY

from contexts.identity.adapters.outbound.persistence.sqlalchemy.tables import auth_local_users

_t = auth_local_users

SELECT_BY_EMAIL = select(_t).where(_t.c.email == bindparam("email"))
SELECT_BY_ID = select(_t).where(_t.c.id == bindparam("id"))

INSERT_USER = insert(_t).values(
    id=bindparam("id"),
    email=bindparam("email"),
    password_hash=bindparam("password_hash"),
    email_verified=False,
    verification_code_hash=bindparam("verification_code_hash"),
    verification_code_expires_at=bindparam("verification_code_expires_at"),
    verification_attempts=0,
    attributes=bindparam("attributes"),
    last_resend_at=bindparam("last_resend_at"),
    created_at=bindparam("created_at"),
    updated_at=bindparam("updated_at"),
)

MARK_VERIFIED = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        email_verified=True,
        verification_code_hash=None,
        verification_code_expires_at=None,
        updated_at=bindparam("updated_at"),
    )
)

UPDATE_VERIFICATION_CODE = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        verification_code_hash=bindparam("verification_code_hash"),
        verification_code_expires_at=bindparam("verification_code_expires_at"),
        last_resend_at=bindparam("last_resend_at"),
        updated_at=bindparam("updated_at"),
    )
)

UPDATE_PASSWORD = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        password_hash=bindparam("password_hash"),
        verification_code_hash=None,
        verification_code_expires_at=None,
        updated_at=bindparam("updated_at"),
    )
)

INCREMENT_ATTEMPTS = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        verification_attempts=_t.c.verification_attempts + 1,
        verification_attempts_reset_at=bindparam("verification_attempts_reset_at"),
        updated_at=bindparam("updated_at"),
    )
)

RESET_ATTEMPTS = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        verification_attempts=0,
        verification_attempts_reset_at=None,
        updated_at=bindparam("updated_at"),
    )
)

# jsonb_set's path argument is text[]; the typed literal makes the
# driver send a real array instead of an untyped string.
_ACTIVE_TENANT_PATH = literal(["custom:active_tenant"], type_=ARRAY(Text()))

UPDATE_ACTIVE_TENANT = (
    update(_t)
    .where(_t.c.id == bindparam("b_id"))
    .values(
        attributes=func.jsonb_set(
            _t.c.attributes,
            _ACTIVE_TENANT_PATH,
            func.to_jsonb(cast(bindparam("tenant_id", type_=Text()), Text())),
            true(),
        ),
        updated_at=bindparam("updated_at"),
    )
)


__all__ = [
    "INCREMENT_ATTEMPTS",
    "INSERT_USER",
    "MARK_VERIFIED",
    "RESET_ATTEMPTS",
    "SELECT_BY_EMAIL",
    "SELECT_BY_ID",
    "UPDATE_ACTIVE_TENANT",
    "UPDATE_PASSWORD",
    "UPDATE_VERIFICATION_CODE",
]
