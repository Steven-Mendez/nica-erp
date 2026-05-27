"""Pre-compiled SQL statements for ``auth_local_users``.

The local IdP adapter is large enough that inlining every ``text(...)``
fragment hurts readability. Hoisting them here keeps the IdP class
focused on policy and gives mypy a single place to type-check the column
projection.

Every statement is parameterised; the IdP supplies bound parameters via
:meth:`SqlAlchemyUnitOfWork.current_session.execute`.
"""

from __future__ import annotations

from sqlalchemy import text

# Full row projection used by the IdP for read-modify-write cycles.
_COLUMNS = (
    "id, email, password_hash, email_verified, verification_code_hash, "
    "verification_code_expires_at, verification_attempts, "
    "verification_attempts_reset_at, attributes, last_resend_at, "
    "created_at, updated_at"
)

# The f-string interpolates only the trusted module-level `_COLUMNS`
# constant — no user input reaches the SQL. The actual filters use bound
# `:email` / `:id` parameters, which SQLAlchemy escapes via the driver.
SELECT_BY_EMAIL = text(
    f"SELECT {_COLUMNS} FROM auth_local_users WHERE email = :email"
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
SELECT_BY_ID = text(
    f"SELECT {_COLUMNS} FROM auth_local_users WHERE id = :id"
)  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text

INSERT_USER = text(
    "INSERT INTO auth_local_users ("
    "id, email, password_hash, email_verified, verification_code_hash, "
    "verification_code_expires_at, verification_attempts, attributes, "
    "last_resend_at, created_at, updated_at"
    ") VALUES ("
    ":id, :email, :password_hash, FALSE, :verification_code_hash, "
    ":verification_code_expires_at, 0, CAST(:attributes AS jsonb), "
    ":last_resend_at, :created_at, :updated_at"
    ")"
)

MARK_VERIFIED = text(
    "UPDATE auth_local_users SET "
    "email_verified = TRUE, "
    "verification_code_hash = NULL, "
    "verification_code_expires_at = NULL, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)

UPDATE_VERIFICATION_CODE = text(
    "UPDATE auth_local_users SET "
    "verification_code_hash = :verification_code_hash, "
    "verification_code_expires_at = :verification_code_expires_at, "
    "last_resend_at = :last_resend_at, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)

UPDATE_PASSWORD = text(
    "UPDATE auth_local_users SET "
    "password_hash = :password_hash, "
    "verification_code_hash = NULL, "
    "verification_code_expires_at = NULL, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)

INCREMENT_ATTEMPTS = text(
    "UPDATE auth_local_users SET "
    "verification_attempts = verification_attempts + 1, "
    "verification_attempts_reset_at = :verification_attempts_reset_at, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)

RESET_ATTEMPTS = text(
    "UPDATE auth_local_users SET "
    "verification_attempts = 0, "
    "verification_attempts_reset_at = NULL, "
    "updated_at = :updated_at "
    "WHERE id = :id"
)

UPDATE_ACTIVE_TENANT = text(
    "UPDATE auth_local_users SET "
    "attributes = jsonb_set(attributes, '{custom:active_tenant}', "
    "to_jsonb(CAST(:tenant_id AS text)), true), "
    "updated_at = :updated_at "
    "WHERE id = :id"
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
