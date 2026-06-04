"""Integration tests for :class:`IdentityProviderLocal`.

Exercises the full local authentication loop against the testcontainer
Postgres: register -> confirm -> authenticate -> refresh -> forgot ->
confirm-forgot -> change-password, plus enumeration-resistance and the
lockout policy.

The :class:`RecordingEmailSender` fixture (see ``conftest.py``) captures
every send so we can parse the 6-digit code out of the body without
talking to a real SMTP server.
"""

from __future__ import annotations

import re

import jwt
import pytest

from contexts.identity.adapters.outbound.identity_provider.local import (
    IdentityProviderLocal,
)
from contexts.identity.application.errors import (
    ExpiredResetCodeError,
    InvalidConfirmationCodeError,
    InvalidCredentialsError,
    InvalidResetCodeError,
    LockoutActiveError,
    RateLimitedError,
    SignupEmailNotConfirmedError,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from tests.integration.contexts.identity.conftest import RecordingEmailSender

_CODE_RE = re.compile(r"\b(\d{6})\b")
_PASSWORD = "Demo1234!@xy"
_NEW_PASSWORD = "NewPass5678!@ab"


def _make_idp(
    *,
    uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> IdentityProviderLocal:
    return IdentityProviderLocal(
        uow=uow,
        email_sender=email_sender,
        jwt_secret=jwt_secret,
        jwt_access_ttl_seconds=3600,
        jwt_refresh_ttl_seconds=2_592_000,
        signup_code_ttl_seconds=900,
        password_reset_code_ttl_seconds=600,
        verification_attempts_max=5,
        verification_attempts_window_seconds=3600,
    )


def _extract_code(body: str) -> str:
    match = _CODE_RE.search(body)
    assert match is not None, f"no 6-digit code in body: {body!r}"
    return match.group(1)


@pytest.mark.integration
async def test_full_local_auth_loop(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)

    # 1. register -----------------------------------------------------------
    async with isolated_uow.begin() as session:
        sub = await idp.register(email="loop@example.com", password=_PASSWORD)
        from sqlalchemy import text

        row = (
            (
                await session.execute(
                    text(
                        "SELECT password_hash, email_verified FROM auth_local_users "
                        "WHERE email = :email"
                    ),
                    {"email": "loop@example.com"},
                )
            )
            .mappings()
            .one()
        )
    assert sub
    assert row["password_hash"] != _PASSWORD
    assert row["email_verified"] is False
    assert len(email_sender.sent) == 1
    code = _extract_code(email_sender.sent[-1].text)

    # 2. confirm_signup -----------------------------------------------------
    async with isolated_uow.begin():
        confirmed_sub = await idp.confirm_signup(email="loop@example.com", code=code)
    assert confirmed_sub == sub

    # 3. authenticate -------------------------------------------------------
    async with isolated_uow.begin():
        identity = await idp.authenticate(email="loop@example.com", password=_PASSWORD)
    decoded = jwt.decode(
        identity.access_token,
        key=jwt_secret,
        algorithms=["HS256"],
        audience="nica-erp-local",
        issuer="nica-erp-local-idp",
    )
    for claim in (
        "sub",
        "email",
        "email_verified",
        "custom:active_tenant",
        "aud",
        "iss",
        "exp",
        "iat",
    ):
        assert claim in decoded, f"claim {claim} missing"
    assert decoded["aud"] == "nica-erp-local"
    assert decoded["iss"] == "nica-erp-local-idp"
    assert decoded["exp"] - decoded["iat"] == 3600
    assert identity.id_token == identity.access_token

    # 4. refresh ------------------------------------------------------------
    async with isolated_uow.begin():
        refreshed = await idp.refresh(refresh_token=identity.refresh_token)
    assert refreshed.access_token
    assert refreshed.refresh_token

    # 5. forgot_password + confirm_forgot_password --------------------------
    email_sender.sent.clear()
    async with isolated_uow.begin():
        await idp.forgot_password(email="loop@example.com")
    assert len(email_sender.sent) == 1
    reset_code = _extract_code(email_sender.sent[-1].text)

    async with isolated_uow.begin():
        await idp.confirm_forgot_password(
            email="loop@example.com", code=reset_code, new_password=_NEW_PASSWORD
        )

    # 6. old password fails, new password succeeds -------------------------
    async with isolated_uow.begin():
        with pytest.raises(InvalidCredentialsError):
            await idp.authenticate(email="loop@example.com", password=_PASSWORD)
    async with isolated_uow.begin():
        identity2 = await idp.authenticate(email="loop@example.com", password=_NEW_PASSWORD)
    assert identity2.sub == sub


@pytest.mark.integration
async def test_revoked_refresh_token_is_rejected_on_next_refresh(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    """Audit F-016: revoking the refresh JWT MUST cause the next
    /refresh call to fail with InvalidCredentialsError even though
    the JWT's signature still validates."""
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="revoke@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="revoke@example.com", code=code)
    async with isolated_uow.begin():
        identity = await idp.authenticate(email="revoke@example.com", password=_PASSWORD)

    async with isolated_uow.begin():
        await idp.revoke_refresh_token(refresh_token=identity.refresh_token)

    async with isolated_uow.begin():
        with pytest.raises(InvalidCredentialsError):
            await idp.refresh(refresh_token=identity.refresh_token)


@pytest.mark.integration
async def test_refresh_token_rejected_as_access_token(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    """Audit F-011: a refresh token presented as Bearer on any
    protected endpoint MUST be rejected — typ:"refresh" tokens are
    only valid on /v1/auth/refresh, never on bearer-auth paths."""
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="typ@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="typ@example.com", code=code)
    async with isolated_uow.begin():
        identity = await idp.authenticate(email="typ@example.com", password=_PASSWORD)

    # The access token still verifies as itself.
    async with isolated_uow.begin():
        claims = await idp.verify_token(token=identity.access_token)
    assert claims["sub"] == identity.sub

    # But the refresh token, which carries typ:"refresh", is refused.
    async with isolated_uow.begin():
        with pytest.raises(InvalidCredentialsError):
            await idp.verify_token(token=identity.refresh_token)


@pytest.mark.integration
async def test_revoke_refresh_token_is_idempotent(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    """Revoking an already-revoked / unknown / malformed token MUST
    resolve as a no-op so the logout endpoint stays idempotent."""
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="idem@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="idem@example.com", code=code)
    async with isolated_uow.begin():
        identity = await idp.authenticate(email="idem@example.com", password=_PASSWORD)

    async with isolated_uow.begin():
        await idp.revoke_refresh_token(refresh_token=identity.refresh_token)
    async with isolated_uow.begin():
        await idp.revoke_refresh_token(refresh_token=identity.refresh_token)
    async with isolated_uow.begin():
        await idp.revoke_refresh_token(refresh_token="not-even-a-jwt")


@pytest.mark.integration
async def test_unverified_login_raises_signup_not_confirmed(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="unverified@example.com", password=_PASSWORD)

    async with isolated_uow.begin():
        with pytest.raises(SignupEmailNotConfirmedError):
            await idp.authenticate(email="unverified@example.com", password=_PASSWORD)


@pytest.mark.integration
async def test_register_existing_email_is_silent_no_op(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)

    async with isolated_uow.begin():
        first_sub = await idp.register(email="dup@example.com", password=_PASSWORD)
    assert len(email_sender.sent) == 1

    async with isolated_uow.begin():
        second_sub = await idp.register(email="dup@example.com", password="Other9876!@cd")
    # Same sub returned; no extra email sent.
    assert second_sub == first_sub
    assert len(email_sender.sent) == 1


@pytest.mark.integration
async def test_forgot_password_unknown_email_no_op(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)

    async with isolated_uow.begin():
        await idp.forgot_password(email="missing@example.com")

    assert email_sender.sent == []


@pytest.mark.integration
async def test_lockout_after_five_failed_attempts(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)

    async with isolated_uow.begin():
        await idp.register(email="lockout@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="lockout@example.com", code=code)

    # Five wrong attempts.
    for _ in range(5):
        async with isolated_uow.begin():
            with pytest.raises(InvalidCredentialsError):
                await idp.authenticate(email="lockout@example.com", password="WrongPass1!@xy")

    # Sixth call — even with the correct password — must lock out.
    async with isolated_uow.begin():
        with pytest.raises(LockoutActiveError) as exc_info:
            await idp.authenticate(email="lockout@example.com", password=_PASSWORD)
    assert exc_info.value.retry_after_seconds > 0


@pytest.mark.integration
async def test_update_active_tenant_propagates_into_next_token(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)

    async with isolated_uow.begin():
        sub = await idp.register(email="tenant@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="tenant@example.com", code=code)

    async with isolated_uow.begin():
        await idp.update_active_tenant(external_sub=sub, tenant_id="tenant-x")

    async with isolated_uow.begin():
        identity = await idp.authenticate(email="tenant@example.com", password=_PASSWORD)

    decoded = jwt.decode(
        identity.access_token,
        key=jwt_secret,
        algorithms=["HS256"],
        audience="nica-erp-local",
        issuer="nica-erp-local-idp",
    )
    assert decoded["custom:active_tenant"] == "tenant-x"


@pytest.mark.integration
async def test_resend_confirmation_rate_limited_within_window(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="resend@example.com", password=_PASSWORD)
    email_sender.sent.clear()

    async with isolated_uow.begin():
        with pytest.raises(RateLimitedError) as exc_info:
            await idp.resend_confirmation(email="resend@example.com")
    assert exc_info.value.scope == "resend"
    assert exc_info.value.retry_after_seconds >= 1
    assert email_sender.sent == []


@pytest.mark.integration
async def test_global_signout_is_always_a_no_op(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        result = await idp.global_signout(external_sub="00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.integration
async def test_confirm_signup_is_idempotent_after_success(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    """Audit F-002: confirming the same email twice with a valid code
    SHALL return the same external_sub instead of raising on the second
    call (the hash is cleared by MARK_VERIFIED, so the second call
    cannot reproduce the original verification)."""
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        sub = await idp.register(email="retry@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        first = await idp.confirm_signup(email="retry@example.com", code=code)
    async with isolated_uow.begin():
        second = await idp.confirm_signup(email="retry@example.com", code=code)
    assert first == sub
    assert second == sub


@pytest.mark.integration
async def test_confirm_signup_with_wrong_code_raises_invalid_confirmation_code(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="wrong-otp@example.com", password=_PASSWORD)

    async with isolated_uow.begin():
        with pytest.raises(InvalidConfirmationCodeError):
            await idp.confirm_signup(email="wrong-otp@example.com", code="000000")


@pytest.mark.integration
async def test_confirm_signup_for_unknown_email_raises_invalid_confirmation_code(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        with pytest.raises(InvalidConfirmationCodeError):
            await idp.confirm_signup(email="ghost@example.com", code="123456")


@pytest.mark.integration
async def test_confirm_forgot_password_with_wrong_code_raises_invalid_reset_code(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    async with isolated_uow.begin():
        await idp.register(email="reset-bad@example.com", password=_PASSWORD)
    code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="reset-bad@example.com", code=code)
    email_sender.sent.clear()
    async with isolated_uow.begin():
        await idp.forgot_password(email="reset-bad@example.com")
    assert len(email_sender.sent) == 1

    async with isolated_uow.begin():
        with pytest.raises(InvalidResetCodeError) as exc_info:
            await idp.confirm_forgot_password(
                email="reset-bad@example.com",
                code="000000",
                new_password=_NEW_PASSWORD,
            )
    # The expired subclass must not match on a wrong-but-fresh code.
    assert not isinstance(exc_info.value, ExpiredResetCodeError)


@pytest.mark.integration
async def test_confirm_forgot_password_after_ttl_raises_expired_reset_code(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    from datetime import UTC, datetime, timedelta

    fixed_now = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    clock = {"value": fixed_now}

    def now() -> datetime:
        return clock["value"]

    idp = IdentityProviderLocal(
        uow=isolated_uow,
        email_sender=email_sender,
        jwt_secret=jwt_secret,
        jwt_access_ttl_seconds=3600,
        jwt_refresh_ttl_seconds=2_592_000,
        signup_code_ttl_seconds=900,
        password_reset_code_ttl_seconds=600,
        verification_attempts_max=5,
        verification_attempts_window_seconds=3600,
        now=now,
    )

    async with isolated_uow.begin():
        await idp.register(email="reset-ttl@example.com", password=_PASSWORD)
    signup_code = _extract_code(email_sender.sent[-1].text)
    async with isolated_uow.begin():
        await idp.confirm_signup(email="reset-ttl@example.com", code=signup_code)
    email_sender.sent.clear()
    async with isolated_uow.begin():
        await idp.forgot_password(email="reset-ttl@example.com")
    reset_code = _extract_code(email_sender.sent[-1].text)

    # Advance past the password_reset_code_ttl_seconds window.
    clock["value"] = fixed_now + timedelta(seconds=601)

    async with isolated_uow.begin():
        with pytest.raises(ExpiredResetCodeError):
            await idp.confirm_forgot_password(
                email="reset-ttl@example.com",
                code=reset_code,
                new_password=_NEW_PASSWORD,
            )


@pytest.mark.integration
async def test_local_idp_satisfies_identity_provider_protocol(
    isolated_uow: SqlAlchemyUnitOfWork,
    email_sender: RecordingEmailSender,
    jwt_secret: str,
) -> None:
    from contexts.identity.application.ports.outbound import IdentityProvider

    idp = _make_idp(uow=isolated_uow, email_sender=email_sender, jwt_secret=jwt_secret)
    assert isinstance(idp, IdentityProvider)
