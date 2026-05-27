"""Unit tests for `bootstrap.settings.Settings`.

The contract exercised here is the build-arg → env-var → `Settings.git_sha`
hand-off documented in `add-api-container-image`: the Dockerfile bakes
`GIT_SHA` into the runtime environment, the running container reads it via
`os.environ`, and `/healthz` reports that exact value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bootstrap import settings as settings_module
from bootstrap.settings import Settings, get_settings


def test_git_sha_defaults_to_unknown_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    # Both forms (constructor + factory default) read from the process env,
    # so we also bust the lru_cache to be safe across test ordering.
    get_settings.cache_clear()

    assert Settings().git_sha == "unknown"


def test_git_sha_reflects_image_baked_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Dockerfile's `ARG GIT_SHA / ENV GIT_SHA=$GIT_SHA` becomes this env."""
    monkeypatch.setenv("GIT_SHA", "abcdef0")
    get_settings.cache_clear()

    assert Settings().git_sha == "abcdef0"


def test_git_sha_accepts_full_40_char_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    full_sha = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("GIT_SHA", full_sha)
    get_settings.cache_clear()

    assert Settings().git_sha == full_sha


def test_get_settings_returns_same_instance() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second


def test_settings_module_does_not_invoke_subprocess_at_import() -> None:
    """The build-arg path bans subprocess at module import time."""
    import inspect

    source = inspect.getsource(settings_module)
    assert "subprocess" not in source


def test_settings_rejects_unset_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`APP_ENV` has no default — instantiation MUST fail when it's unset.

    Per the ``api-bootstrap`` spec, a misconfigured container must fail
    fast rather than silently fall back to the local identity adapter in
    production.
    """

    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()

    # `_env_file=None` bypasses the repo-root `.env.local` so the test
    # exercises the "no APP_ENV anywhere" contract; otherwise the dev's
    # local file would satisfy the field via the file source.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_local_without_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``APP_ENV=local``, ``LOCAL_JWT_SECRET`` must be set."""

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LOCAL_JWT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
