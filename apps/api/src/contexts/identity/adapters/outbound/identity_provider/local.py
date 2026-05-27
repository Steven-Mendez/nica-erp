"""``IdentityProviderLocal`` — DB-backed adapter for ``APP_ENV=local``.

Implements every method on the :class:`IdentityProvider` Protocol against
the ``auth_local_users`` ledger using the active
:class:`SqlAlchemyUnitOfWork.current_session`. The adapter never opens
its own database connection; the use case is responsible for wrapping
calls in ``async with uow.begin():``.

Design notes
------------

- Passwords are hashed with bcrypt (cost ``rounds=12``).
- Verification codes (signup + reset) are 6 random digits; only the
  SHA-256 hash is stored. The plaintext is sent over email and discarded.
- Access, refresh, and ID tokens are HS256 JWTs signed with
  ``settings.local_jwt_secret``. The claim shape is the canonical
  ``sub / email / email_verified / custom:active_tenant / aud / iss /
  exp / iat`` set required by the identity-provider-local spec.
- Refresh tokens are stateless (MVP); :meth:`global_signout` is a no-op
  for that reason. Post-MVP this method will truncate a future
  ``auth_local_refresh_tokens`` table.
- Email-enumeration resistance: ``register`` returns the existing
  ``sub`` on duplicates without sending a new code, and
  ``forgot_password`` silently no-ops when the email is unknown.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import jwt
from sqlalchemy.exc import IntegrityError

from contexts.identity.adapters.outbound.email.templates import render
from contexts.identity.adapters.outbound.persistence.sqlalchemy import auth_local_users as sql
from contexts.identity.application.errors import (
    EmailSendError,
    InvalidCredentialsError,
    LockoutActiveError,
    SignupEmailNotConfirmedError,
    TokenExpiredError,
)
from contexts.identity.application.ports.outbound import EmailSender, Identity
from contexts.identity.domain import Email
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

_AUD = "nica-erp-local"
_ISS = "nica-erp-local-idp"
_BCRYPT_ROUNDS = 12
_RESEND_COOLDOWN_SECONDS = 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mint_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass(slots=True)
class IdentityProviderLocal:
    """DB-backed :class:`IdentityProvider` for local development."""

    uow: SqlAlchemyUnitOfWork
    email_sender: EmailSender
    jwt_secret: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    signup_code_ttl_seconds: int
    password_reset_code_ttl_seconds: int
    verification_attempts_max: int
    verification_attempts_window_seconds: int
    aud: str = _AUD
    iss: str = _ISS
    now: Callable[[], datetime] = field(default=_utc_now)

    # IdentityProvider methods ------------------------------------------------
    async def register(self, *, email: str, password: str) -> str:
        normalised = Email.parse(email).value
        existing = await self._select_by_email(normalised)
        if existing is not None:
            # Enumeration-resistance: return the existing sub silently and
            # send nothing. The use case keeps its uniform response shape.
            return str(existing["id"])

        code = _mint_code()
        now = self.now()
        user_id = uuid4()
        # bcrypt with rounds=12 is ~250ms of CPU work; running it on the
        # event-loop thread would block every other coroutine for that
        # window. Offload to the default threadpool.
        password_hash = await asyncio.to_thread(_hash_password, password)
        params = {
            "id": user_id,
            "email": normalised,
            "password_hash": password_hash,
            "verification_code_hash": _sha256(code),
            "verification_code_expires_at": now + timedelta(seconds=self.signup_code_ttl_seconds),
            "attributes": '{"custom:active_tenant": ""}',
            "last_resend_at": now,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.uow.current_session.execute(sql.INSERT_USER, params)
        except IntegrityError:
            # Race: a concurrent register beat us. Treat as the duplicate
            # branch above — silently swallow.
            row = await self._select_by_email(normalised)
            if row is None:  # pragma: no cover — defensive
                raise
            return str(row["id"])

        await self._send_signup_code(to=normalised, code=code)
        return str(user_id)

    async def authenticate(self, *, email: str, password: str) -> Identity:
        normalised = Email.parse(email).value
        row = await self._select_by_email(normalised)
        if row is None:
            raise InvalidCredentialsError("invalid credentials")

        # Lockout-active check fires before password verification so a
        # locked-out caller never burns CPU on bcrypt.
        reset_at = row["verification_attempts_reset_at"]
        now = self.now()
        if (
            reset_at is not None
            and reset_at > now
            and row["verification_attempts"] >= self.verification_attempts_max
        ):
            raise LockoutActiveError(retry_after_seconds=int((reset_at - now).total_seconds()))

        if not row["email_verified"]:
            raise SignupEmailNotConfirmedError("email not confirmed")

        if not await asyncio.to_thread(_verify_password, password, row["password_hash"]):
            await self._increment_attempts(row_id=row["id"], current_reset_at=reset_at)
            raise InvalidCredentialsError("invalid credentials")

        # Success: reset the failure counter.
        await self.uow.current_session.execute(
            sql.RESET_ATTEMPTS,
            {"id": row["id"], "updated_at": now},
        )

        active_tenant = _read_active_tenant(row["attributes"])
        access_token, claims = self._make_access_token(
            sub=str(row["id"]),
            email=row["email"],
            email_verified=True,
            active_tenant=active_tenant,
        )
        refresh_token = self._make_refresh_token(sub=str(row["id"]))
        return Identity(
            sub=str(row["id"]),
            email=row["email"],
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=access_token,
            claims=claims,
        )

    async def verify_token(self, *, token: str) -> dict[str, Any]:
        try:
            decoded = jwt.decode(
                token,
                key=self.jwt_secret,
                algorithms=["HS256"],
                audience=self.aud,
                issuer=self.iss,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("access token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidCredentialsError(f"invalid token: {exc}") from exc
        assert isinstance(decoded, dict)
        return decoded

    async def refresh(self, *, refresh_token: str) -> Identity:
        try:
            decoded = jwt.decode(
                refresh_token,
                key=self.jwt_secret,
                algorithms=["HS256"],
                audience=self.aud,
                issuer=self.iss,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("refresh token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidCredentialsError(f"invalid refresh token: {exc}") from exc
        if decoded.get("typ") != "refresh":
            raise InvalidCredentialsError("not a refresh token")

        sub = decoded["sub"]
        row = await self._select_by_id(UUID(sub))
        if row is None:
            raise InvalidCredentialsError("unknown user for refresh")

        active_tenant = _read_active_tenant(row["attributes"])
        access_token, claims = self._make_access_token(
            sub=sub,
            email=row["email"],
            email_verified=row["email_verified"],
            active_tenant=active_tenant,
        )
        new_refresh = self._make_refresh_token(sub=sub)
        return Identity(
            sub=sub,
            email=row["email"],
            access_token=access_token,
            refresh_token=new_refresh,
            id_token=access_token,
            claims=claims,
        )

    async def confirm_signup(self, *, email: str, code: str) -> str:
        normalised = Email.parse(email).value
        row = await self._select_by_email(normalised)
        if row is None:
            raise InvalidCredentialsError("invalid code")
        expires_at = row["verification_code_expires_at"]
        stored_hash = row["verification_code_hash"]
        if (
            stored_hash is None
            or expires_at is None
            or expires_at < self.now()
            or _sha256(code) != stored_hash
        ):
            raise InvalidCredentialsError("invalid code")
        await self.uow.current_session.execute(
            sql.MARK_VERIFIED,
            {"id": row["id"], "updated_at": self.now()},
        )
        return str(row["id"])

    async def resend_confirmation(self, *, email: str) -> None:
        normalised = Email.parse(email).value
        row = await self._select_by_email(normalised)
        if row is None:
            return  # enumeration-resistance
        last_resend_at = row["last_resend_at"]
        now = self.now()
        if (
            last_resend_at is not None
            and (now - last_resend_at).total_seconds() < _RESEND_COOLDOWN_SECONDS
        ):
            # The spec mandates rate-limiting; the typed error catalogue does
            # not yet ship a dedicated RateLimitedError, so we surface
            # InvalidCredentialsError. The HTTP adapter maps this to 400.
            raise InvalidCredentialsError("resend rate-limited")
        code = _mint_code()
        await self.uow.current_session.execute(
            sql.UPDATE_VERIFICATION_CODE,
            {
                "id": row["id"],
                "verification_code_hash": _sha256(code),
                "verification_code_expires_at": now
                + timedelta(seconds=self.signup_code_ttl_seconds),
                "last_resend_at": now,
                "updated_at": now,
            },
        )
        await self._send_signup_code(to=normalised, code=code)

    async def forgot_password(self, *, email: str) -> None:
        normalised = Email.parse(email).value
        row = await self._select_by_email(normalised)
        if row is None:
            return  # enumeration-resistance: no row, no code, no email
        code = _mint_code()
        now = self.now()
        await self.uow.current_session.execute(
            sql.UPDATE_VERIFICATION_CODE,
            {
                "id": row["id"],
                "verification_code_hash": _sha256(code),
                "verification_code_expires_at": now
                + timedelta(seconds=self.password_reset_code_ttl_seconds),
                "last_resend_at": now,
                "updated_at": now,
            },
        )
        await self._send_reset_code(to=normalised, code=code)

    async def confirm_forgot_password(self, *, email: str, code: str, new_password: str) -> None:
        normalised = Email.parse(email).value
        row = await self._select_by_email(normalised)
        if row is None:
            raise InvalidCredentialsError("invalid code")
        stored_hash = row["verification_code_hash"]
        expires_at = row["verification_code_expires_at"]
        if (
            stored_hash is None
            or expires_at is None
            or expires_at < self.now()
            or _sha256(code) != stored_hash
        ):
            raise InvalidCredentialsError("invalid code")
        new_hash = await asyncio.to_thread(_hash_password, new_password)
        await self.uow.current_session.execute(
            sql.UPDATE_PASSWORD,
            {
                "id": row["id"],
                "password_hash": new_hash,
                "updated_at": self.now(),
            },
        )

    async def change_password(
        self, *, access_token: str, old_password: str, new_password: str
    ) -> None:
        claims = await self.verify_token(token=access_token)
        sub = claims["sub"]
        row = await self._select_by_id(UUID(sub))
        if row is None:
            raise InvalidCredentialsError("unknown user")
        if not await asyncio.to_thread(_verify_password, old_password, row["password_hash"]):
            raise InvalidCredentialsError("invalid credentials")
        new_hash = await asyncio.to_thread(_hash_password, new_password)
        await self.uow.current_session.execute(
            sql.UPDATE_PASSWORD,
            {
                "id": row["id"],
                "password_hash": new_hash,
                "updated_at": self.now(),
            },
        )

    async def global_signout(self, *, external_sub: str) -> None:
        # MVP: no refresh-token ledger to clear. Always idempotent.
        return None

    async def update_active_tenant(self, *, external_sub: str, tenant_id: str) -> None:
        await self.uow.current_session.execute(
            sql.UPDATE_ACTIVE_TENANT,
            {
                "id": UUID(external_sub),
                "tenant_id": tenant_id,
                "updated_at": self.now(),
            },
        )

    # Internal helpers --------------------------------------------------------
    async def _select_by_email(self, email: str) -> dict[str, Any] | None:
        result = await self.uow.current_session.execute(sql.SELECT_BY_EMAIL, {"email": email})
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def _select_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        result = await self.uow.current_session.execute(sql.SELECT_BY_ID, {"id": user_id})
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def _increment_attempts(self, *, row_id: UUID, current_reset_at: datetime | None) -> None:
        now = self.now()
        # First failure in a fresh window opens a new one. Subsequent
        # failures keep the existing window so the lockout duration is
        # measured from the first failure, not the last.
        if current_reset_at is None or current_reset_at <= now:
            reset_at = now + timedelta(seconds=self.verification_attempts_window_seconds)
        else:
            reset_at = current_reset_at
        await self.uow.current_session.execute(
            sql.INCREMENT_ATTEMPTS,
            {
                "id": row_id,
                "verification_attempts_reset_at": reset_at,
                "updated_at": now,
            },
        )

    async def _send_signup_code(self, *, to: str, code: str) -> None:
        html, text = render("signup_verification", code=code)
        try:
            await self.email_sender.send(
                to=to,
                subject="nica-erp: confirma tu cuenta / confirm your account",
                html=html,
                text=text,
            )
        except EmailSendError:
            raise
        except Exception as exc:
            raise EmailSendError(f"failed to deliver signup code: {exc}") from exc

    async def _send_reset_code(self, *, to: str, code: str) -> None:
        html, text = render("password_reset", code=code)
        try:
            await self.email_sender.send(
                to=to,
                subject="nica-erp: restablece tu contrasena / reset your password",
                html=html,
                text=text,
            )
        except EmailSendError:
            raise
        except Exception as exc:
            raise EmailSendError(f"failed to deliver reset code: {exc}") from exc

    def _make_access_token(
        self,
        *,
        sub: str,
        email: str,
        email_verified: bool,
        active_tenant: str,
    ) -> tuple[str, dict[str, Any]]:
        now_ts = int(self.now().timestamp())
        claims: dict[str, Any] = {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "custom:active_tenant": active_tenant,
            "aud": self.aud,
            "iss": self.iss,
            "exp": now_ts + self.jwt_access_ttl_seconds,
            "iat": now_ts,
        }
        token = jwt.encode(claims, self.jwt_secret, algorithm="HS256")
        return token, claims

    def _make_refresh_token(self, *, sub: str) -> str:
        now_ts = int(self.now().timestamp())
        claims: dict[str, Any] = {
            "sub": sub,
            "typ": "refresh",
            "aud": self.aud,
            "iss": self.iss,
            "exp": now_ts + self.jwt_refresh_ttl_seconds,
            "iat": now_ts,
        }
        return jwt.encode(claims, self.jwt_secret, algorithm="HS256")


# Module-level helpers ----------------------------------------------------
def _hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(
        plaintext.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def _verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _read_active_tenant(attributes: Any) -> str:
    """Pluck ``custom:active_tenant`` out of the JSONB column."""

    if not isinstance(attributes, dict):
        return ""
    value = attributes.get("custom:active_tenant", "")
    return value if isinstance(value, str) else ""


__all__ = ["IdentityProviderLocal"]
