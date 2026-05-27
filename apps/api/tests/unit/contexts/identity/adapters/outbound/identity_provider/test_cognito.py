"""Unit tests for :class:`IdentityProviderCognito`.

The boto3 client is faked with :class:`MagicMock`; methods return plain
dicts that mimic the cognito-idp response shapes. The JWKS fetch helper
is monkeypatched so no real network call ever happens.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import jwt
import pytest

from contexts.identity.adapters.outbound.identity_provider import cognito as cognito_mod
from contexts.identity.adapters.outbound.identity_provider.cognito import (
    ClientError,
    IdentityProviderCognito,
)
from contexts.identity.application.errors import (
    InvalidCredentialsError,
    LockoutActiveError,
    SignupEmailNotConfirmedError,
    TokenExpiredError,
)
from contexts.identity.application.ports.outbound import Identity

pytestmark = pytest.mark.unit


USER_POOL_ID = "us-east-1_test"
APP_CLIENT_ID = "client-123"
REGION = "us-east-1"


def _client_error(code: str, message: str = "boom", op: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, op)


def _make_access_token(claims: dict[str, Any]) -> str:
    """Mint an unsigned JWT for tests — the adapter decodes claims unsigned
    for ``authenticate`` / ``refresh`` so a HS256 stub is sufficient.
    """

    return jwt.encode(claims, "test-stub-secret-that-is-long-enough-32b", algorithm="HS256")


@pytest.fixture(autouse=True)
def clear_jwks_cache() -> Iterator[None]:
    cognito_mod._JWKS_CACHE.clear()
    cognito_mod._JWKS_CACHE_TIMESTAMP.clear()
    cognito_mod._JWKS_FETCH_LOCKS.clear()
    yield
    cognito_mod._JWKS_CACHE.clear()
    cognito_mod._JWKS_CACHE_TIMESTAMP.clear()
    cognito_mod._JWKS_FETCH_LOCKS.clear()


@pytest.fixture
def cognito_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def adapter(cognito_client: MagicMock) -> IdentityProviderCognito:
    return IdentityProviderCognito(
        client=cognito_client,
        user_pool_id=USER_POOL_ID,
        app_client_id=APP_CLIENT_ID,
        region=REGION,
    )


# ---------------------------------------------------------------- register


async def test_register_happy_returns_sub(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.sign_up.return_value = {"UserSub": "sub-abc"}

    result = await adapter.register(email="new@x.io", password="Demo1234!@xy")

    assert result == "sub-abc"
    cognito_client.sign_up.assert_called_once()
    kwargs = cognito_client.sign_up.call_args.kwargs
    assert kwargs["ClientId"] == APP_CLIENT_ID
    assert kwargs["Username"] == "new@x.io"
    assert kwargs["Password"] == "Demo1234!@xy"
    assert kwargs["UserAttributes"] == [{"Name": "email", "Value": "new@x.io"}]


async def test_register_swallows_username_exists(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.sign_up.side_effect = _client_error("UsernameExistsException", op="SignUp")

    result = await adapter.register(email="taken@x.io", password="Demo1234!@xy")

    # Spec: adapter returns success-shaped result without raising.
    assert isinstance(result, str)


async def test_register_other_client_error_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.sign_up.side_effect = _client_error("InvalidPasswordException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.register(email="x@x.io", password="weak")


# ---------------------------------------------------------------- authenticate


async def test_authenticate_happy_returns_identity(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    access_token = _make_access_token({"sub": "abc-123", "email": "u@x.io"})
    cognito_client.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": access_token,
            "RefreshToken": "rt",
            "IdToken": "id",
        }
    }

    identity = await adapter.authenticate(email="u@x.io", password="StrongPass123!")

    assert isinstance(identity, Identity)
    assert identity.sub == "abc-123"
    assert identity.email == "u@x.io"
    assert identity.access_token == access_token
    assert identity.refresh_token == "rt"
    assert identity.id_token == "id"
    assert identity.claims["sub"] == "abc-123"
    cognito_client.initiate_auth.assert_called_once()
    kwargs = cognito_client.initiate_auth.call_args.kwargs
    assert kwargs["AuthFlow"] == "USER_PASSWORD_AUTH"


async def test_authenticate_not_authorized_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.initiate_auth.side_effect = _client_error("NotAuthorizedException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.authenticate(email="u@x.io", password="wrong")


async def test_authenticate_user_not_confirmed_raises_signup_not_confirmed(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.initiate_auth.side_effect = _client_error("UserNotConfirmedException")

    with pytest.raises(SignupEmailNotConfirmedError):
        await adapter.authenticate(email="u@x.io", password="StrongPass123!")


async def test_authenticate_too_many_requests_raises_lockout(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.initiate_auth.side_effect = _client_error("TooManyRequestsException")

    with pytest.raises(LockoutActiveError) as excinfo:
        await adapter.authenticate(email="u@x.io", password="x")

    assert excinfo.value.retry_after_seconds == 15 * 60


async def test_authenticate_user_not_found_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.initiate_auth.side_effect = _client_error("UserNotFoundException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.authenticate(email="missing@x.io", password="x")


# ---------------------------------------------------------------- verify_token


def _stub_jwks_decode(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fetch_returns: dict[str, Any] | None = None,
    fetch_raises: Exception | None = None,
    decode_returns: dict[str, Any] | None = None,
    decode_raises: Exception | None = None,
) -> dict[str, int]:
    """Stub the JWKS fetch and ``jwt.decode``. Returns call counters."""

    counters = {"fetch": 0, "decode": 0}

    def fake_fetch(url: str) -> dict[str, Any]:
        counters["fetch"] += 1
        if fetch_raises is not None:
            raise fetch_raises
        assert fetch_returns is not None
        return fetch_returns

    monkeypatch.setattr(cognito_mod, "_fetch_jwks_sync", fake_fetch)

    def fake_get_unverified_header(token: str) -> dict[str, str]:
        return {"kid": "test-kid", "alg": "RS256"}

    monkeypatch.setattr(cognito_mod.jwt, "get_unverified_header", fake_get_unverified_header)

    def fake_from_jwk(blob: str) -> str:
        return "FAKE_PUBLIC_KEY"

    monkeypatch.setattr(cognito_mod.RSAAlgorithm, "from_jwk", fake_from_jwk)

    def fake_decode(token: str, **kwargs: Any) -> dict[str, Any]:
        counters["decode"] += 1
        if decode_raises is not None:
            raise decode_raises
        assert decode_returns is not None
        return decode_returns

    monkeypatch.setattr(cognito_mod.jwt, "decode", fake_decode)

    return counters


async def test_verify_token_first_call_fetches_jwks(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    jwks = {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "x", "e": "AQAB"}]}
    claims = {"sub": "abc", "aud": APP_CLIENT_ID, "iss": "x"}
    counters = _stub_jwks_decode(monkeypatch, fetch_returns=jwks, decode_returns=claims)

    result1 = await adapter.verify_token(token="header.payload.sig")
    result2 = await adapter.verify_token(token="header.payload.sig")

    assert result1 == claims
    assert result2 == claims
    # First call fetches; second call hits the warm cache.
    assert counters["fetch"] == 1
    assert counters["decode"] == 2
    assert cognito_mod._JWKS_CACHE[USER_POOL_ID] == jwks


async def test_verify_token_uses_stale_cache_on_error(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "x", "e": "AQAB"}]}
    # Pre-populate the cache as STALE (older than the TTL).
    cognito_mod._JWKS_CACHE[USER_POOL_ID] = stale
    cognito_mod._JWKS_CACHE_TIMESTAMP[USER_POOL_ID] = time.time() - (25 * 3600)
    claims = {"sub": "abc"}
    counters = _stub_jwks_decode(
        monkeypatch,
        fetch_raises=OSError("transient 5xx"),
        decode_returns=claims,
    )

    result = await adapter.verify_token(token="header.payload.sig")

    assert result == claims
    assert counters["fetch"] == 1  # attempt was made
    assert counters["decode"] == 1  # validation still happened against stale cache


async def test_verify_token_no_cache_error_fails_closed(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    counters = _stub_jwks_decode(
        monkeypatch,
        fetch_raises=OSError("transient 5xx"),
        decode_returns={"sub": "abc"},
    )

    with pytest.raises(InvalidCredentialsError):
        await adapter.verify_token(token="header.payload.sig")

    assert counters["fetch"] == 1
    assert counters["decode"] == 0  # never reached


async def test_verify_token_expired_raises_token_expired(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    jwks = {"keys": [{"kid": "test-kid", "kty": "RSA"}]}
    _stub_jwks_decode(
        monkeypatch,
        fetch_returns=jwks,
        decode_raises=jwt.ExpiredSignatureError("expired"),
    )

    with pytest.raises(TokenExpiredError):
        await adapter.verify_token(token="header.payload.sig")


async def test_verify_token_invalid_signature_raises_invalid_credentials(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    jwks = {"keys": [{"kid": "test-kid", "kty": "RSA"}]}
    _stub_jwks_decode(
        monkeypatch,
        fetch_returns=jwks,
        decode_raises=jwt.InvalidSignatureError("bad sig"),
    )

    with pytest.raises(InvalidCredentialsError):
        await adapter.verify_token(token="header.payload.sig")


async def test_verify_token_kid_missing_from_jwks_raises_invalid_credentials(
    adapter: IdentityProviderCognito, monkeypatch: pytest.MonkeyPatch
) -> None:
    # JWKS has different kid than the token header.
    jwks = {"keys": [{"kid": "other-kid", "kty": "RSA"}]}
    _stub_jwks_decode(monkeypatch, fetch_returns=jwks, decode_returns={"sub": "abc"})

    with pytest.raises(InvalidCredentialsError):
        await adapter.verify_token(token="header.payload.sig")


# ---------------------------------------------------------------- refresh


async def test_refresh_happy_returns_identity(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    access_token = _make_access_token({"sub": "abc-123", "email": "u@x.io"})
    cognito_client.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": access_token,
            "IdToken": "id",
        }
    }

    identity = await adapter.refresh(refresh_token="rt-old")

    assert identity.sub == "abc-123"
    assert identity.refresh_token == "rt-old"  # echoed when Cognito omits it
    kwargs = cognito_client.initiate_auth.call_args.kwargs
    assert kwargs["AuthFlow"] == "REFRESH_TOKEN_AUTH"


async def test_refresh_not_authorized_raises_token_expired(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.initiate_auth.side_effect = _client_error("NotAuthorizedException")

    with pytest.raises(TokenExpiredError):
        await adapter.refresh(refresh_token="rt-bad")


# ---------------------------------------------------------------- confirm_signup


async def test_confirm_signup_happy_returns_sub(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.confirm_sign_up.return_value = {}
    cognito_client.admin_get_user.return_value = {
        "UserAttributes": [{"Name": "sub", "Value": "abc-123"}]
    }

    sub = await adapter.confirm_signup(email="u@x.io", code="123456")

    assert sub == "abc-123"


async def test_confirm_signup_bad_code_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.confirm_sign_up.side_effect = _client_error("CodeMismatchException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.confirm_signup(email="u@x.io", code="bad")


async def test_confirm_signup_already_confirmed_returns_sub(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.confirm_sign_up.side_effect = _client_error("NotAuthorizedException")
    cognito_client.admin_get_user.return_value = {
        "UserAttributes": [{"Name": "sub", "Value": "abc-123"}]
    }

    sub = await adapter.confirm_signup(email="u@x.io", code="123456")

    assert sub == "abc-123"


# ---------------------------------------------------------------- resend_confirmation


async def test_resend_confirmation_swallows_user_not_found(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.resend_confirmation_code.side_effect = _client_error("UserNotFoundException")

    result = await adapter.resend_confirmation(email="missing@x.io")

    assert result is None


async def test_resend_confirmation_swallows_already_confirmed(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.resend_confirmation_code.side_effect = _client_error(
        "InvalidParameterException", message="User is already confirmed."
    )

    result = await adapter.resend_confirmation(email="u@x.io")

    assert result is None


# ---------------------------------------------------------------- forgot_password


async def test_forgot_password_swallows_user_not_found(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.forgot_password.side_effect = _client_error("UserNotFoundException")

    result = await adapter.forgot_password(email="missing@x.io")

    assert result is None


async def test_forgot_password_propagates_invalid_parameter(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.forgot_password.side_effect = _client_error(
        "InvalidParameterException", message="not an email"
    )

    with pytest.raises(ClientError):
        await adapter.forgot_password(email="not-an-email")


# ---------------------------------------------------------------- confirm_forgot_password


async def test_confirm_forgot_password_bad_code_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.confirm_forgot_password.side_effect = _client_error("ExpiredCodeException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.confirm_forgot_password(
            email="u@x.io", code="bad", new_password="StrongPass123!"
        )


# ---------------------------------------------------------------- change_password


async def test_change_password_wrong_old_raises_invalid_credentials(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.change_password.side_effect = _client_error("NotAuthorizedException")

    with pytest.raises(InvalidCredentialsError):
        await adapter.change_password(
            access_token="at", old_password="wrong", new_password="NewPass123!"
        )


# ---------------------------------------------------------------- global_signout


async def test_global_signout_happy_returns_none(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.admin_user_global_sign_out.return_value = {}

    result = await adapter.global_signout(external_sub="abc-123")

    assert result is None
    cognito_client.admin_user_global_sign_out.assert_called_once_with(
        UserPoolId=USER_POOL_ID, Username="abc-123"
    )


async def test_global_signout_swallows_user_not_found(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.admin_user_global_sign_out.side_effect = _client_error("UserNotFoundException")

    result = await adapter.global_signout(external_sub="abc-123")

    assert result is None


async def test_global_signout_swallows_not_authorized(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.admin_user_global_sign_out.side_effect = _client_error("NotAuthorizedException")

    result = await adapter.global_signout(external_sub="abc-123")

    assert result is None


async def test_global_signout_propagates_other_errors(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.admin_user_global_sign_out.side_effect = _client_error("InternalErrorException")

    with pytest.raises(ClientError):
        await adapter.global_signout(external_sub="abc-123")


# ---------------------------------------------------------------- update_active_tenant


async def test_update_active_tenant_calls_admin_update_user_attributes(
    adapter: IdentityProviderCognito, cognito_client: MagicMock
) -> None:
    cognito_client.admin_update_user_attributes.return_value = {}

    await adapter.update_active_tenant(external_sub="abc-123", tenant_id="t-1")

    kwargs = cognito_client.admin_update_user_attributes.call_args.kwargs
    assert kwargs["UserPoolId"] == USER_POOL_ID
    assert kwargs["Username"] == "abc-123"
    assert kwargs["UserAttributes"] == [{"Name": "custom:active_tenant", "Value": "t-1"}]


# ---------------------------------------------------------------- protocol conformance


def test_adapter_satisfies_identity_provider_protocol(
    adapter: IdentityProviderCognito,
) -> None:
    from contexts.identity.application.ports.outbound import IdentityProvider

    assert isinstance(adapter, IdentityProvider)
