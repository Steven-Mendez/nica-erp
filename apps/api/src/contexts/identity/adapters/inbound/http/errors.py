"""Map identity application errors to RFC-7807 problem details.

The application layer raises plain Python exceptions (``InvalidCredentialsError``,
``LockoutActiveError``, ...) and never imports FastAPI. This module is the
single place where those errors become HTTP responses with
``Content-Type: application/problem+json`` per
``docs/08-api-conventions.md`` §Errors.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contexts.identity.adapters.inbound.http.schemas import ProblemDetail
from contexts.identity.application.errors import (
    EmailSendError,
    InvalidCredentialsError,
    LockoutActiveError,
    SignupEmailNotConfirmedError,
    TokenExpiredError,
    UserNotFoundError,
)
from contexts.identity.domain import PasswordPolicyError

PROBLEM_CONTENT_TYPE = "application/problem+json"


def _problem(status: int, code: str, title: str, **extra: Any) -> ProblemDetail:
    return ProblemDetail(status=status, code=code, title=title, **extra)


def to_problem_detail(exc: Exception) -> tuple[int, ProblemDetail]:
    """Translate an identity-context exception to an (HTTP status, problem) pair.

    Unmapped exceptions raise; callers should let FastAPI surface them as 500s.
    """

    if isinstance(exc, LockoutActiveError):
        return (
            401,
            _problem(
                401,
                "auth.lockout_active",
                "Account temporarily locked",
                detail=str(exc),
                retry_after_seconds=exc.retry_after_seconds,
            ),
        )
    if isinstance(exc, TokenExpiredError):
        return (
            401,
            _problem(401, "auth.token_expired", "Token expired", detail=str(exc) or None),
        )
    if isinstance(exc, SignupEmailNotConfirmedError):
        return (
            401,
            _problem(
                401,
                "auth.signup_email_not_confirmed",
                "Email confirmation required",
                detail=str(exc) or None,
            ),
        )
    if isinstance(exc, InvalidCredentialsError):
        return (
            401,
            _problem(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail=str(exc) or None,
            ),
        )
    if isinstance(exc, EmailSendError):
        return (
            502,
            _problem(502, "email.send_failed", "Email delivery failed", detail=str(exc) or None),
        )
    if isinstance(exc, UserNotFoundError):
        return (
            404,
            _problem(404, "user.not_found", "User not found", detail=str(exc) or None),
        )
    if isinstance(exc, PasswordPolicyError):
        return (
            422,
            _problem(
                422,
                "validation.password_policy",
                "Password policy violation",
                detail=str(exc),
            ),
        )
    if isinstance(exc, ValueError):
        return (
            422,
            _problem(
                422,
                "validation.request_invalid",
                "Request validation failed",
                detail=str(exc) or None,
            ),
        )
    raise exc  # pragma: no cover — defensive: caller should never reach here


def _problem_response(status: int, problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        content=problem.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the identity-context exceptions to RFC-7807 responses on ``app``."""

    @app.exception_handler(InvalidCredentialsError)
    async def _invalid_credentials(_request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(TokenExpiredError)
    async def _token_expired(_request: Request, exc: TokenExpiredError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(LockoutActiveError)
    async def _lockout(_request: Request, exc: LockoutActiveError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(SignupEmailNotConfirmedError)
    async def _signup_not_confirmed(
        _request: Request, exc: SignupEmailNotConfirmedError
    ) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(EmailSendError)
    async def _email_send(_request: Request, exc: EmailSendError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(UserNotFoundError)
    async def _user_not_found(_request: Request, exc: UserNotFoundError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(PasswordPolicyError)
    async def _password_policy(_request: Request, exc: PasswordPolicyError) -> JSONResponse:
        status, problem = to_problem_detail(exc)
        return _problem_response(status, problem)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default 422 body uses a different shape; remap to
        # RFC-7807 so all 4xx responses share one envelope. Include the
        # failed field path (`loc`) in the detail so the SPA can show the
        # user which field broke, instead of a bare diagnostic.
        errors = exc.errors()
        first = errors[0] if errors else None
        if isinstance(first, dict):
            msg = first.get("msg") or "invalid request"
            raw_loc = first.get("loc")
            loc_parts: list[str] = []
            if isinstance(raw_loc, (list, tuple)):
                # Drop the leading "body" / "query" prefix; the SPA already
                # knows the request was a body submission.
                for part in list(raw_loc)[1:]:
                    loc_parts.append(str(part))
            loc_str = ".".join(loc_parts)
            detail_str = f"{loc_str}: {msg}" if loc_str else str(msg)
        else:
            detail_str = "invalid request"
        problem = _problem(
            422,
            "validation.request_invalid",
            "Request validation failed",
            detail=detail_str,
        )
        return _problem_response(422, problem)


__all__ = [
    "PROBLEM_CONTENT_TYPE",
    "register_exception_handlers",
    "to_problem_detail",
]
