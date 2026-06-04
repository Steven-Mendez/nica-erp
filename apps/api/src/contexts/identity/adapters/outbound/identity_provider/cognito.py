"""Cognito implementation of the :class:`IdentityProvider` port.

Wraps ``boto3.client("cognito-idp")`` and the User Pool's JWKS document.
The boto3 client is provided by the bootstrap factory when ``APP_ENV=aws``;
this module never constructs one itself, which keeps it test-friendly and
keeps boto3 out of the import path for ``APP_ENV=local``.

JWKS caching is module-level (per User-Pool id) with a 24 h TTL and
stale-on-error fallback. Fetches are protected by a process-wide lock so
two concurrent ``verify_token(...)`` calls cannot stampede the JWKS
endpoint.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm

from contexts.identity.application.errors import (
    ExpiredResetCodeError,
    InvalidConfirmationCodeError,
    InvalidCredentialsError,
    InvalidResetCodeError,
    LockoutActiveError,
    ResendThrottledError,
    SignupEmailNotConfirmedError,
    TokenExpiredError,
)
from contexts.identity.application.ports.outbound import Identity


class _FallbackClientError(Exception):
    """Fallback shim mirroring ``botocore.exceptions.ClientError``.

    Only used when botocore is not installed (e.g. local dev / CI for
    non-AWS tests). Tests import :data:`ClientError` from this module so the
    ``except`` branch in adapter methods catches whichever class is in scope.
    """

    def __init__(self, error_response: dict[str, Any], operation_name: str) -> None:
        super().__init__(f"{operation_name}: {error_response.get('Error', {}).get('Code', '?')}")
        self.response = error_response
        self.operation_name = operation_name


ClientError: type[Exception]
try:  # botocore is a runtime dependency only when APP_ENV=aws
    from botocore.exceptions import ClientError as _BotocoreClientError

    ClientError = _BotocoreClientError
except ModuleNotFoundError:  # pragma: no cover - exercised only when boto3 absent
    ClientError = _FallbackClientError

# Module-level JWKS cache, keyed by User Pool id. The reader path
# (`_get_jwks`) is lock-free: dict reads on CPython are atomic and a torn
# update only costs an extra fetch, never a wrong key. The locks below
# are per-pool ``asyncio.Lock`` instances that coalesce concurrent misses
# into a single in-flight HTTP fetch (anti-stampede) — readers awaiting
# the lock get the freshly-cached value when the leader releases it.
_JWKS_CACHE: dict[str, dict[str, Any]] = {}
_JWKS_CACHE_TIMESTAMP: dict[str, float] = {}
_JWKS_FETCH_LOCKS: dict[str, asyncio.Lock] = {}


# 15 minutes — Cognito does not expose the remaining lockout window. We pick
# the documented "soft" backoff so the HTTP layer can render Retry-After.
_LOCKOUT_RETRY_AFTER_SECONDS = 15 * 60


def _error_code(exc: Exception) -> str:
    """Return the ``Error.Code`` from a botocore ``ClientError``."""

    response = getattr(exc, "response", {}) or {}
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = error.get("Code", "") if isinstance(error, dict) else ""
    return str(code)


def _decode_unverified(token: str) -> dict[str, Any]:
    """Decode a JWT's payload without checking the signature.

    Used to harvest ``sub`` / ``email`` claims from a freshly minted Cognito
    access token — the token's authenticity is already guaranteed by the
    fact that Cognito itself returned it over TLS in the same boto3 call.
    We parse the payload segment directly instead of calling
    ``jwt.decode(..., options={"verify_signature": False})`` so the intent
    ("read claims, no signature check") is plain and no decoder option
    can be misconfigured to silently disable verification elsewhere.
    """

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidCredentialsError("JWT is not a three-part token")
    payload_b64 = parts[1]
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = base64.urlsafe_b64decode(payload_b64 + padding)
        claims = json.loads(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidCredentialsError("JWT payload is not valid JSON") from exc
    if not isinstance(claims, dict):  # pragma: no cover - defensive
        raise InvalidCredentialsError("decoded JWT claims were not a mapping")
    return claims


def _fetch_jwks_sync(url: str) -> dict[str, Any]:
    """Synchronous JWKS fetch — wrapped in ``asyncio.to_thread`` by callers.

    ``url`` is the User Pool's ``.well-known/jwks.json`` endpoint built
    from settings (region + user_pool_id); it is never derived from user
    input, so the ``urllib.request`` use is safe by construction.
    """

    if not url.startswith("https://"):  # defensive: refuse file:// or http://
        raise ValueError(f"JWKS URL must be HTTPS: {url!r}")
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read()
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):  # pragma: no cover - defensive
        raise ValueError("JWKS payload was not a JSON object")
    return payload


@dataclass(slots=True)
class IdentityProviderCognito:
    """:class:`IdentityProvider` backed by AWS Cognito User Pools.

    The boto3 client is injected so tests can pass a :class:`MagicMock` and
    so the bootstrap factory can configure region / profile centrally.
    """

    client: Any  # boto3 cognito-idp client (typed Any to avoid hard boto3 dep)
    user_pool_id: str
    app_client_id: str
    region: str
    jwks_ttl_seconds: int = 24 * 3600

    # ---------------------------------------------------------------- helpers

    @property
    def _issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def _jwks_url(self) -> str:
        return f"{self._issuer}/.well-known/jwks.json"

    async def _get_jwks(self) -> dict[str, Any]:
        """Return a (possibly cached) JWKS document.

        - Fresh-cache path: return immediately, no I/O, no lock.
        - Stale / missing cache: acquire the per-pool ``asyncio.Lock`` and
          re-check the cache; only the first waiter performs the HTTP
          fetch (anti-stampede). Followers see the freshly-cached value.
        - Fetch failure with a populated cache: return the stale entry
          (stale-on-error fallback per spec).
        - Fetch failure and no cache: raise :class:`InvalidCredentialsError`.
        """

        now = time.time()
        cached = _JWKS_CACHE.get(self.user_pool_id)
        cached_ts = _JWKS_CACHE_TIMESTAMP.get(self.user_pool_id, 0.0)
        if cached is not None and now - cached_ts < self.jwks_ttl_seconds:
            return cached

        lock = _JWKS_FETCH_LOCKS.setdefault(self.user_pool_id, asyncio.Lock())
        async with lock:
            # Re-check inside the lock — a concurrent waiter may have just
            # refreshed the cache, in which case we avoid the HTTP fetch.
            now = time.time()
            cached = _JWKS_CACHE.get(self.user_pool_id)
            cached_ts = _JWKS_CACHE_TIMESTAMP.get(self.user_pool_id, 0.0)
            if cached is not None and now - cached_ts < self.jwks_ttl_seconds:
                return cached

            try:
                jwks = await asyncio.to_thread(_fetch_jwks_sync, self._jwks_url)
            except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
                if cached is not None:
                    return cached
                raise InvalidCredentialsError(
                    "JWKS fetch failed and no cache is available"
                ) from None

            _JWKS_CACHE[self.user_pool_id] = jwks
            _JWKS_CACHE_TIMESTAMP[self.user_pool_id] = now
            return jwks

    # ------------------------------------------------------------- IdentityProvider

    async def register(self, *, email: str, password: str) -> str:
        try:
            response = await asyncio.to_thread(
                self.client.sign_up,
                ClientId=self.app_client_id,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}],
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "UsernameExistsException":
                # Enumeration-resistance: surface as a success-shaped result.
                return ""
            raise InvalidCredentialsError(f"SignUp failed: {code}") from exc

        user_sub = response.get("UserSub", "") if isinstance(response, dict) else ""
        return str(user_sub)

    async def authenticate(self, *, email: str, password: str) -> Identity:
        try:
            response = await asyncio.to_thread(
                self.client.initiate_auth,
                ClientId=self.app_client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email, "PASSWORD": password},
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "UserNotConfirmedException":
                raise SignupEmailNotConfirmedError(email) from exc
            if code in {"TooManyRequestsException", "TooManyFailedAttemptsException"}:
                raise LockoutActiveError(retry_after_seconds=_LOCKOUT_RETRY_AFTER_SECONDS) from exc
            # NotAuthorizedException, UserNotFoundException, PasswordResetRequiredException
            # and anything else collapse to invalid-credentials per the spec.
            raise InvalidCredentialsError(f"authenticate failed: {code}") from exc

        result = response.get("AuthenticationResult", {}) if isinstance(response, dict) else {}
        access_token = str(result.get("AccessToken", ""))
        refresh_token = str(result.get("RefreshToken", ""))
        id_token = str(result.get("IdToken", ""))
        claims = _decode_unverified(access_token) if access_token else {}
        return Identity(
            sub=str(claims.get("sub", "")),
            email=str(claims.get("email", email)),
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            claims=claims,
        )

    async def verify_token(self, *, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise InvalidCredentialsError("malformed JWT header") from exc

        kid = header.get("kid") if isinstance(header, dict) else None
        if not kid:
            raise InvalidCredentialsError("JWT header missing kid")

        jwks = await self._get_jwks()
        keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
        matching: dict[str, Any] | None = None
        for entry in keys:
            if isinstance(entry, dict) and entry.get("kid") == kid:
                matching = entry
                break
        if matching is None:
            raise InvalidCredentialsError(f"no JWKS key matches kid={kid!r}")

        public_key = RSAAlgorithm.from_jwk(json.dumps(matching))

        try:
            claims = jwt.decode(
                token,
                key=public_key,  # type: ignore[arg-type]
                algorithms=["RS256"],
                audience=self.app_client_id,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("access token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidCredentialsError(f"invalid token: {exc}") from exc

        if not isinstance(claims, dict):  # pragma: no cover - PyJWT always returns dict
            raise InvalidCredentialsError("decoded JWT claims were not a mapping")
        return claims

    async def refresh(self, *, refresh_token: str) -> Identity:
        try:
            response = await asyncio.to_thread(
                self.client.initiate_auth,
                ClientId=self.app_client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={"REFRESH_TOKEN": refresh_token},
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "NotAuthorizedException":
                raise TokenExpiredError("refresh token rejected") from exc
            raise InvalidCredentialsError(f"refresh failed: {code}") from exc

        result = response.get("AuthenticationResult", {}) if isinstance(response, dict) else {}
        access_token = str(result.get("AccessToken", ""))
        # Cognito does not always echo the refresh token on REFRESH_TOKEN_AUTH;
        # callers reuse the original when the response omits it.
        new_refresh = str(result.get("RefreshToken", "") or refresh_token)
        id_token = str(result.get("IdToken", ""))
        claims = _decode_unverified(access_token) if access_token else {}
        return Identity(
            sub=str(claims.get("sub", "")),
            email=str(claims.get("email", "")),
            access_token=access_token,
            refresh_token=new_refresh,
            id_token=id_token,
            claims=claims,
        )

    async def confirm_signup(self, *, email: str, code: str) -> str:
        try:
            await asyncio.to_thread(
                self.client.confirm_sign_up,
                ClientId=self.app_client_id,
                Username=email,
                ConfirmationCode=code,
            )
        except ClientError as exc:
            err_code = _error_code(exc)
            if err_code in {"CodeMismatchException", "ExpiredCodeException"}:
                raise InvalidConfirmationCodeError(
                    "confirmation code is invalid or expired"
                ) from exc
            if err_code == "NotAuthorizedException":
                # Already confirmed — fall through to fetch the existing sub.
                pass
            else:
                raise InvalidCredentialsError(f"confirm_sign_up failed: {err_code}") from exc

        return await self._lookup_sub(email)

    async def _lookup_sub(self, email: str) -> str:
        try:
            response = await asyncio.to_thread(
                self.client.admin_get_user,
                UserPoolId=self.user_pool_id,
                Username=email,
            )
        except ClientError as exc:
            raise InvalidCredentialsError(f"admin_get_user failed: {_error_code(exc)}") from exc

        attrs = response.get("UserAttributes", []) if isinstance(response, dict) else []
        for attr in attrs:
            if isinstance(attr, dict) and attr.get("Name") == "sub":
                return str(attr.get("Value", ""))
        return ""

    async def resend_confirmation(self, *, email: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.resend_confirmation_code,
                ClientId=self.app_client_id,
                Username=email,
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "UserNotFoundException":
                return
            if code == "InvalidParameterException":
                message = ""
                response = getattr(exc, "response", {})
                if isinstance(response, dict):
                    error = response.get("Error", {})
                    if isinstance(error, dict):
                        message = str(error.get("Message", ""))
                if "already confirmed" in message.lower():
                    return
            if code in {"LimitExceededException", "TooManyRequestsException"}:
                raise ResendThrottledError(retry_after_seconds=60) from exc
            raise InvalidCredentialsError(f"resend_confirmation_code failed: {code}") from exc

    async def forgot_password(self, *, email: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.forgot_password,
                ClientId=self.app_client_id,
                Username=email,
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "UserNotFoundException":
                return  # enumeration-resistance
            if code == "InvalidParameterException":
                # Spec: propagate so the HTTP layer surfaces a 422.
                raise
            raise InvalidCredentialsError(f"forgot_password failed: {code}") from exc

    async def confirm_forgot_password(self, *, email: str, code: str, new_password: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.confirm_forgot_password,
                ClientId=self.app_client_id,
                Username=email,
                ConfirmationCode=code,
                Password=new_password,
            )
        except ClientError as exc:
            err_code = _error_code(exc)
            if err_code == "ExpiredCodeException":
                raise ExpiredResetCodeError("reset code expired") from exc
            if err_code == "CodeMismatchException":
                raise InvalidResetCodeError("reset code is invalid or used") from exc
            raise InvalidCredentialsError(f"confirm_forgot_password failed: {err_code}") from exc

    async def change_password(
        self, *, access_token: str, old_password: str, new_password: str
    ) -> None:
        try:
            await asyncio.to_thread(
                self.client.change_password,
                AccessToken=access_token,
                PreviousPassword=old_password,
                ProposedPassword=new_password,
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code == "NotAuthorizedException":
                raise InvalidCredentialsError("current password incorrect") from exc
            raise InvalidCredentialsError(f"change_password failed: {code}") from exc

    async def revoke_refresh_token(self, *, refresh_token: str) -> None:
        """Cognito-side per-token revocation.

        ``admin_user_global_sign_out`` revokes ALL of a user's refresh
        tokens; per-token revocation requires the ``revoke_token``
        flow (configured via OAuth scopes on the user pool client).
        Until that wiring lands the safest no-op here is to defer to
        ``global_signout`` at the caller. We intentionally do nothing
        so a logout in the SPA does NOT silently invalidate every
        other session for the same user.
        """

        return None

    async def global_signout(self, *, external_sub: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.admin_user_global_sign_out,
                UserPoolId=self.user_pool_id,
                Username=external_sub,
            )
        except ClientError as exc:
            code = _error_code(exc)
            if code in {"UserNotFoundException", "NotAuthorizedException"}:
                return  # idempotent
            raise

    async def update_active_tenant(self, *, external_sub: str, tenant_id: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.admin_update_user_attributes,
                UserPoolId=self.user_pool_id,
                Username=external_sub,
                UserAttributes=[
                    {"Name": "custom:active_tenant", "Value": tenant_id},
                ],
            )
        except ClientError as exc:
            raise InvalidCredentialsError(
                f"admin_update_user_attributes failed: {_error_code(exc)}"
            ) from exc


__all__ = ["IdentityProviderCognito"]
