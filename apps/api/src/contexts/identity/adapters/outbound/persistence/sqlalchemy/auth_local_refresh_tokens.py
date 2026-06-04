"""SQL helpers for the ``auth_local_refresh_tokens`` jti ledger.

Audit F-005 / F-011 / F-016: refresh tokens now write a row at mint
time, the logout endpoint sets ``revoked_at``, and refresh validates
the jti is live before re-issuing.
"""

from __future__ import annotations

from sqlalchemy import text

INSERT_TOKEN = text(
    "INSERT INTO auth_local_refresh_tokens "
    "(jti, user_id, issued_at, revoked_at, user_agent, ip) VALUES "
    "(:jti, :user_id, :issued_at, NULL, :user_agent, :ip)"
)

REVOKE_BY_JTI = text(
    "UPDATE auth_local_refresh_tokens "
    "SET revoked_at = :revoked_at "
    "WHERE jti = :jti AND revoked_at IS NULL"
)

FIND_LIVE_BY_JTI = text(
    "SELECT jti, user_id, issued_at FROM auth_local_refresh_tokens "
    "WHERE jti = :jti AND revoked_at IS NULL"
)


__all__ = ["FIND_LIVE_BY_JTI", "INSERT_TOKEN", "REVOKE_BY_JTI"]
