# apps/api/src/contexts/identity/adapters/inbound/http/router.py
"""FastAPI router for the identity HTTP adapter (``/v1/auth/*`` + ``/v1/me``).

Every route is a thin shim: parse the request body, hand off to the use
case, shape the response. Errors raised by the application layer bubble
up to the exception handlers registered in :mod:`errors`.

OpenAPI metadata (``summary``, ``description``, ``tags``,
``response_description``, ``responses``) is wired here rather than in
docstrings alone so Swagger UI and ReDoc render a complete catalogue —
including the RFC-7807 problem schema for each documented error.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from bootstrap.dependencies import current_actor
from contexts.identity.adapters.inbound.http.dependencies import (
    get_access_token,
    get_authenticate,
    get_change_password,
    get_confirm_signup,
    get_current_user,
    get_forgot_password,
    get_get_me,
    get_logout,
    get_refresh_token,
    get_register_user,
    get_resend_code,
    get_reset_password,
    get_update_profile,
)
from contexts.identity.adapters.inbound.http.errors import PROBLEM_CONTENT_TYPE
from contexts.identity.adapters.inbound.http.schemas import (
    ChangePasswordRequest,
    ConfirmSignupRequest,
    ForgotPasswordRequest,
    ForgotResponse,
    LoginRequest,
    MeResponse,
    ProblemDetail,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateMeRequest,
)
from contexts.identity.application.use_cases import (
    Authenticate,
    ChangePassword,
    ConfirmSignup,
    ForgotPassword,
    GetMe,
    Logout,
    RefreshToken,
    RegisterUser,
    ResendCode,
    ResetPassword,
    UpdateProfile,
)
from shared_kernel.adapters.context import CurrentUser
from shared_kernel.permissions import Actor

# Reusable ``responses=`` entries so each operation advertises the RFC-7807
# error envelope without each route restating the schema. Keys are the
# HTTP status; the body is rendered as ``application/problem+json``.
_PROBLEM = {
    "model": ProblemDetail,
    "content": {PROBLEM_CONTENT_TYPE: {}},
}
_VALIDATION_422: dict[int | str, dict[str, Any]] = {
    422: {**_PROBLEM, "description": "Request validation or password-policy failure"},
}
_UNAUTHENTICATED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {**_PROBLEM, "description": "Invalid credentials, expired token, or lockout"},
    **_VALIDATION_422,
}
_AUTHENTICATED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {**_PROBLEM, "description": "Missing, expired, or invalid bearer token"},
    403: {**_PROBLEM, "description": "Tenant scope missing or membership denied"},
    **_VALIDATION_422,
}

router = APIRouter(prefix="/v1")


# --- /v1/auth/* ------------------------------------------------------------


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
    summary="Start signup for a new email",
    response_description="Signup initiated; verification code sent if the email is new",
    responses=_VALIDATION_422,
)
async def register(
    body: RegisterRequest,
    uc: RegisterUser = Depends(get_register_user),
) -> RegisterResponse:
    """Begin an email-based signup.

    The response body is deliberately empty to avoid leaking whether the
    address was already registered (enumeration resistance). A verification
    code is dispatched out-of-band; clients call ``/auth/confirm-signup``
    next.
    """

    await uc.execute(email=body.email, password=body.password)
    return RegisterResponse()


@router.post(
    "/auth/confirm-signup",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    summary="Confirm signup with the emailed code",
    response_description="Email confirmed; the user may now log in",
    responses=_UNAUTHENTICATED_RESPONSES,
)
async def confirm_signup(
    body: ConfirmSignupRequest,
    uc: ConfirmSignup = Depends(get_confirm_signup),
) -> None:
    """Verify the one-time code emailed during ``/auth/register``."""

    await uc.execute(email=body.email, code=body.code)


@router.post(
    "/auth/resend-code",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    summary="Resend the signup verification code",
    response_description="A fresh verification code was dispatched",
    responses=_VALIDATION_422,
)
async def resend_code(
    body: ResendCodeRequest,
    uc: ResendCode = Depends(get_resend_code),
) -> None:
    """Re-send the signup verification code, throttled per email."""

    await uc.execute(email=body.email)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["auth"],
    summary="Exchange email + password for tokens",
    response_description="Access, refresh, and id tokens",
    responses=_UNAUTHENTICATED_RESPONSES,
)
async def login(
    body: LoginRequest,
    uc: Authenticate = Depends(get_authenticate),
) -> TokenResponse:
    """Authenticate the caller and return a token bundle."""

    identity = await uc.execute(email=body.email, password=body.password)
    return TokenResponse(
        access_token=identity.access_token,
        refresh_token=identity.refresh_token,
        id_token=identity.id_token,
    )


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    tags=["auth"],
    summary="Rotate the access token using a refresh token",
    response_description="A fresh access/refresh/id-token bundle",
    responses=_UNAUTHENTICATED_RESPONSES,
)
async def refresh(
    body: RefreshRequest,
    uc: RefreshToken = Depends(get_refresh_token),
) -> TokenResponse:
    """Issue a new token bundle from a still-valid refresh token."""

    identity = await uc.execute(refresh_token=body.refresh_token)
    return TokenResponse(
        access_token=identity.access_token,
        refresh_token=identity.refresh_token,
        id_token=identity.id_token,
    )


@router.post(
    "/auth/password/forgot",
    response_model=ForgotResponse,
    status_code=status.HTTP_200_OK,
    tags=["auth"],
    summary="Start the password-reset flow",
    response_description="Reset email dispatched if the address exists",
    responses=_VALIDATION_422,
)
async def forgot_password(
    body: ForgotPasswordRequest,
    uc: ForgotPassword = Depends(get_forgot_password),
) -> ForgotResponse:
    """Send a password-reset code; response is opaque on purpose."""

    await uc.execute(email=body.email)
    return ForgotResponse()


@router.post(
    "/auth/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    summary="Complete a password reset with the emailed code",
    response_description="Password rotated; the user can now log in",
    responses=_UNAUTHENTICATED_RESPONSES,
)
async def reset_password(
    body: ResetPasswordRequest,
    uc: ResetPassword = Depends(get_reset_password),
) -> None:
    """Set a new password using the code from ``/auth/password/forgot``."""

    await uc.execute(email=body.email, code=body.code, new_password=body.new_password)


@router.post(
    "/auth/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    summary="Rotate the caller's password",
    response_description="Password rotated; existing sessions remain valid",
    responses=_AUTHENTICATED_RESPONSES,
)
async def change_password(
    body: ChangePasswordRequest,
    access_token: str = Depends(get_access_token),
    _current_user: CurrentUser = Depends(get_current_user),
    uc: ChangePassword = Depends(get_change_password),
) -> None:
    """Change the caller's password while authenticated."""

    await uc.execute(
        access_token=access_token,
        old_password=body.old_password,
        new_password=body.new_password,
    )


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    summary="Invalidate the caller's refresh token",
    response_description="Refresh token revoked",
    responses=_AUTHENTICATED_RESPONSES,
)
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    uc: Logout = Depends(get_logout),
) -> None:
    """Revoke the caller's refresh token; access tokens expire naturally."""

    await uc.execute(current_user=current_user)


# --- /v1/me ---------------------------------------------------------------


@router.get(
    "/me",
    response_model=MeResponse,
    tags=["me"],
    summary="Read the caller's profile",
    response_description="Caller profile + active tenant",
    responses=_AUTHENTICATED_RESPONSES,
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    uc: GetMe = Depends(get_get_me),
    actor: Actor = Depends(current_actor),
) -> MeResponse:
    """Return the caller's profile, hydrated from the persistence layer."""

    user = await uc.execute(current_user=current_user)
    return MeResponse(
        id=user.id,
        email=user.email.value,
        display_name=user.display_name,
        locale=user.locale,
        timezone=user.timezone,
        preferences=user.preferences,
        active_tenant=current_user.active_tenant,
        role=actor.role,
        permissions=sorted(actor.permissions),
    )


@router.patch(
    "/me",
    response_model=MeResponse,
    tags=["me"],
    summary="Update the caller's editable profile fields",
    response_description="Updated profile + active tenant",
    responses=_AUTHENTICATED_RESPONSES,
)
async def patch_me(
    body: UpdateMeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    uc: UpdateProfile = Depends(get_update_profile),
) -> MeResponse:
    """Partially update the caller's profile; unknown fields return 422."""

    user = await uc.execute(
        current_user=current_user,
        display_name=body.display_name,
        locale=body.locale,
        timezone=body.timezone,
        preferences=body.preferences,
    )
    return MeResponse(
        id=user.id,
        email=user.email.value,
        display_name=user.display_name,
        locale=user.locale,
        timezone=user.timezone,
        preferences=user.preferences,
        active_tenant=current_user.active_tenant,
    )


__all__ = ["router"]
