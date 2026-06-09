"""Statements for the ``auth_local_refresh_tokens`` jti ledger.

Audit F-005 / F-011 / F-016: refresh tokens now write a row at mint
time, the logout endpoint sets ``revoked_at``, and refresh validates
the jti is live before re-issuing.
"""

from __future__ import annotations

from sqlalchemy import bindparam, insert, select, update

from contexts.identity.adapters.outbound.persistence.sqlalchemy.tables import (
    auth_local_refresh_tokens,
)

_t = auth_local_refresh_tokens

INSERT_TOKEN = insert(_t).values(
    jti=bindparam("jti"),
    user_id=bindparam("user_id"),
    issued_at=bindparam("issued_at"),
    revoked_at=None,
    user_agent=bindparam("user_agent"),
    ip=bindparam("ip"),
)

# ``bindparam("jti")`` is reserved inside update() because it names a
# column of the target table; the WHERE param needs the ``b_`` prefix.
REVOKE_BY_JTI = (
    update(_t)
    .where(_t.c.jti == bindparam("b_jti"), _t.c.revoked_at.is_(None))
    .values(revoked_at=bindparam("revoked_at"))
)

FIND_LIVE_BY_JTI = select(_t.c.jti, _t.c.user_id, _t.c.issued_at).where(
    _t.c.jti == bindparam("jti"), _t.c.revoked_at.is_(None)
)


__all__ = ["FIND_LIVE_BY_JTI", "INSERT_TOKEN", "REVOKE_BY_JTI"]
