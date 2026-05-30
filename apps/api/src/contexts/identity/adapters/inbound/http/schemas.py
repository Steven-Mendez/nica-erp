# apps/api/src/contexts/identity/adapters/inbound/http/schemas.py
"""Pydantic v2 request/response models for the identity HTTP adapter.

Schemas are intentionally thin: most field-level validation lives in the
domain layer (``Email.parse``, ``Password.validate_policy``) so the same
rules apply regardless of how a use case is invoked. The schemas merely
shape the wire payloads, forbid unknown fields where required by the
identity-http spec (notably :class:`UpdateMeRequest`), and carry
``Field(examples=...)`` / ``json_schema_extra`` so Swagger UI and ReDoc
render concrete payloads next to each operation.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Reusable example literals — keep the rendered docs consistent across
# every request/response that mentions the same field.
_EXAMPLE_EMAIL = "ada@example.com"
_EXAMPLE_PASSWORD = "S3cret-Passw0rd!"
_EXAMPLE_NEW_PASSWORD = "Even-Str0nger-Passw0rd!"
_EXAMPLE_CODE = "123456"
_EXAMPLE_USER_ID = "01HFZX9C9PRRRZ3W0Q9F0J9K2H"
_EXAMPLE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
_EXAMPLE_REFRESH = "v1.MRSt...redacted"

# --- Request bodies --------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])
    password: str = Field(examples=[_EXAMPLE_PASSWORD])


class ConfirmSignupRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])
    code: str = Field(examples=[_EXAMPLE_CODE])


class ResendCodeRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])


class LoginRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])
    password: str = Field(examples=[_EXAMPLE_PASSWORD])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(examples=[_EXAMPLE_REFRESH])


class ForgotPasswordRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])


class ResetPasswordRequest(BaseModel):
    email: str = Field(examples=[_EXAMPLE_EMAIL])
    code: str = Field(examples=[_EXAMPLE_CODE])
    new_password: str = Field(examples=[_EXAMPLE_NEW_PASSWORD])


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(examples=[_EXAMPLE_PASSWORD])
    new_password: str = Field(examples=[_EXAMPLE_NEW_PASSWORD])


class UpdateMeRequest(BaseModel):
    """Partial update of the caller's editable profile fields.

    ``extra="forbid"`` ensures attempts to mutate ``email`` / ``id`` /
    ``external_sub`` etc. surface a 422 (per the spec's "patching email
    is rejected" scenario) instead of being silently ignored.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Ada Lovelace",
                    "locale": "es-NI",
                    "timezone": "America/Managua",
                    "preferences": {"theme": "system"},
                }
            ]
        },
    )

    display_name: str | None = Field(default=None, examples=["Ada Lovelace"])
    locale: str | None = Field(default=None, examples=["es-NI"])
    timezone: str | None = Field(default=None, examples=["America/Managua"])
    preferences: dict[str, Any] | None = Field(default=None, examples=[{"theme": "system"}])


# --- Response bodies -------------------------------------------------------


class RegisterResponse(BaseModel):
    """Deliberately empty: register's body must not reveal pre-existence."""

    model_config = ConfigDict(json_schema_extra={"examples": [{}]})


class ForgotResponse(BaseModel):
    """Deliberately empty: forgot-password is enumeration-resistant."""

    model_config = ConfigDict(json_schema_extra={"examples": [{}]})


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": _EXAMPLE_TOKEN,
                    "refresh_token": _EXAMPLE_REFRESH,
                    "id_token": _EXAMPLE_TOKEN,
                    "token_type": "Bearer",
                }
            ]
        }
    )

    access_token: str = Field(examples=[_EXAMPLE_TOKEN])
    refresh_token: str = Field(examples=[_EXAMPLE_REFRESH])
    id_token: str = Field(examples=[_EXAMPLE_TOKEN])
    token_type: Literal["Bearer"] = "Bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _EXAMPLE_USER_ID,
                    "email": _EXAMPLE_EMAIL,
                    "display_name": "Ada Lovelace",
                    "locale": "es-NI",
                    "timezone": "America/Managua",
                    "preferences": {"theme": "system"},
                    "active_tenant": "acme",
                    "role": "admin",
                    "permissions": ["tenant:read", "tenant:write"],
                }
            ]
        }
    )

    id: UUID = Field(examples=[_EXAMPLE_USER_ID])
    email: str = Field(examples=[_EXAMPLE_EMAIL])
    # ``display_name`` is the first-login probe — the SPA redirects to
    # ``/welcome`` while it is ``None``. ``locale`` is deferred to the
    # future i18n sprint; the SPA does not render it today.
    display_name: str | None = Field(default=None, examples=["Ada Lovelace"])
    locale: str | None = Field(default=None, examples=["es-NI"])
    timezone: str | None = Field(default=None, examples=["America/Managua"])
    preferences: dict[str, Any] = Field(examples=[{"theme": "system"}])
    active_tenant: str | None = Field(default=None, examples=["acme"])
    role: str | None = Field(default=None, examples=["admin"])
    permissions: list[str] = Field(default_factory=list, examples=[["tenant:read"]])


class ProblemDetail(BaseModel):
    """RFC-7807 problem detail with the project-stable ``code`` extension."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "type": "about:blank",
                    "title": "Invalid credentials",
                    "status": 401,
                    "code": "auth.invalid_credentials",
                    "detail": "Email or password is incorrect.",
                }
            ]
        },
    )

    type: str = "about:blank"
    title: str = Field(examples=["Invalid credentials"])
    status: int = Field(examples=[401])
    detail: str | None = Field(default=None, examples=["Email or password is incorrect."])
    code: str = Field(examples=["auth.invalid_credentials"])
    retry_after_seconds: int | None = Field(default=None, examples=[60])


__all__ = [
    "ChangePasswordRequest",
    "ConfirmSignupRequest",
    "ForgotPasswordRequest",
    "ForgotResponse",
    "LoginRequest",
    "MeResponse",
    "ProblemDetail",
    "RefreshRequest",
    "RegisterRequest",
    "RegisterResponse",
    "ResendCodeRequest",
    "ResetPasswordRequest",
    "TokenResponse",
    "UpdateMeRequest",
]
