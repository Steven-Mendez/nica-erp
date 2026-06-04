"""HTTP-level coverage for the identity context's RFC-7807 mapping.

Each test instantiates the typed application exception, runs it through
``to_problem_detail``, and (where it matters) asserts the response
shape produced by the registered exception handler — including the
``Retry-After`` header on ``ResendThrottledError``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contexts.identity.adapters.inbound.http.errors import (
    PROBLEM_CONTENT_TYPE,
    register_exception_handlers,
    to_problem_detail,
)
from contexts.identity.application.errors import (
    ExpiredResetCodeError,
    InvalidConfirmationCodeError,
    InvalidCredentialsError,
    InvalidResetCodeError,
    ResendThrottledError,
)

pytestmark = pytest.mark.integration


def test_invalid_confirmation_code_maps_to_400() -> None:
    status, problem = to_problem_detail(InvalidConfirmationCodeError("bad otp"))
    assert status == 400
    assert problem.status == 400
    assert problem.code == "auth.invalid_confirmation_code"
    assert problem.title == "Invalid confirmation code"


def test_invalid_reset_code_maps_to_410_reset_token_used() -> None:
    status, problem = to_problem_detail(InvalidResetCodeError("used"))
    assert status == 410
    assert problem.status == 410
    assert problem.code == "auth.reset_token_used"
    assert problem.title == "Reset link no longer valid"


def test_expired_reset_code_maps_to_410_reset_token_expired() -> None:
    status, problem = to_problem_detail(ExpiredResetCodeError("expired"))
    assert status == 410
    assert problem.code == "auth.reset_token_expired"
    assert problem.title == "Reset link expired"


def test_expired_reset_code_subclass_takes_precedence_over_parent() -> None:
    """``ExpiredResetCodeError`` is a subclass of ``InvalidResetCodeError``;
    the more specific match must win in ``to_problem_detail``.
    """

    exc = ExpiredResetCodeError("expired")
    assert isinstance(exc, InvalidResetCodeError)  # sanity
    _status, problem = to_problem_detail(exc)
    assert problem.code == "auth.reset_token_expired"  # NOT reset_token_used


def test_resend_throttled_maps_to_429_with_rate_limited_code_and_scope() -> None:
    """Audit F-003: the resend cooldown SHALL emit ``auth.rate_limited``
    with ``scope:"resend"``, a Spanish title, and a Retry-After body
    field."""
    status, problem = to_problem_detail(ResendThrottledError(retry_after_seconds=42))
    assert status == 429
    assert problem.code == "auth.rate_limited"
    assert problem.title == "Demasiados intentos"
    body = problem.model_dump(mode="json", exclude_none=True)
    assert body["retry_after_seconds"] == 42
    assert body["scope"] == "resend"
    assert body["detail"].startswith("Espera 42 s")


def test_invalid_credentials_still_maps_to_401() -> None:
    """Regression: ``InvalidCredentialsError`` keeps its 401 status."""

    status, problem = to_problem_detail(InvalidCredentialsError("nope"))
    assert status == 401
    assert problem.code == "auth.invalid_credentials"


@pytest.mark.integration
async def test_resend_throttled_response_carries_retry_after_header() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/throttle")
    async def _throttle() -> None:  # pragma: no cover — exercised via the request
        raise ResendThrottledError(retry_after_seconds=17)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/throttle")

    assert response.status_code == 429
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert response.headers["retry-after"] == "17"
    body = response.json()
    assert body["code"] == "auth.rate_limited"
    assert body["retry_after_seconds"] == 17
    assert body["scope"] == "resend"


@pytest.mark.integration
async def test_invalid_confirmation_code_response_envelope() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/bad-otp")
    async def _bad_otp() -> None:  # pragma: no cover
        raise InvalidConfirmationCodeError("invalid code")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/bad-otp")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert response.json()["code"] == "auth.invalid_confirmation_code"


@pytest.mark.integration
async def test_expired_reset_code_response_envelope() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/expired-reset")
    async def _expired_reset() -> None:  # pragma: no cover
        raise ExpiredResetCodeError("expired")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/expired-reset")

    assert response.status_code == 410
    assert response.json()["code"] == "auth.reset_token_expired"


@pytest.mark.integration
async def test_invalid_reset_code_response_envelope() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/used-reset")
    async def _used_reset() -> None:  # pragma: no cover
        raise InvalidResetCodeError("used")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/used-reset")

    assert response.status_code == 410
    assert response.json()["code"] == "auth.reset_token_used"
