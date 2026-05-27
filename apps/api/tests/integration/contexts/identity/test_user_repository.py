"""Integration tests for :class:`UserRepositorySqlAlchemy`.

Round-trips a ``User`` aggregate through the real Postgres testcontainer,
verifies JSONB preference handling, and exercises both lookup paths.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from contexts.identity.adapters.outbound.persistence.sqlalchemy.user_repository import (
    UserRepositorySqlAlchemy,
)
from contexts.identity.domain import Email, User
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.integration
async def test_add_and_get_by_id(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    now = datetime.now(UTC)
    user = User(
        id_=uuid4(),
        external_sub="sub-1",
        email=Email.parse("user@example.com"),
        display_name="Demo User",
        locale="es-NI",
        timezone="America/Managua",
        preferences={"theme": "dark", "tags": ["a", "b"]},
        created_at=now,
        updated_at=now,
    )

    async with isolated_uow.begin():
        repo = UserRepositorySqlAlchemy(isolated_uow)
        await repo.add(user)

    async with isolated_uow.begin():
        repo = UserRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get_by_id(user.id)

    assert loaded is not None
    assert loaded.id == user.id
    assert loaded.external_sub == "sub-1"
    assert loaded.email.value == "user@example.com"
    assert loaded.display_name == "Demo User"
    assert loaded.locale == "es-NI"
    assert loaded.timezone == "America/Managua"
    assert loaded.preferences == {"theme": "dark", "tags": ["a", "b"]}


@pytest.mark.integration
async def test_get_by_external_sub(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    now = datetime.now(UTC)
    user = User(
        id_=uuid4(),
        external_sub="sub-xyz",
        email=Email.parse("xyz@example.com"),
        created_at=now,
        updated_at=now,
    )

    async with isolated_uow.begin():
        await UserRepositorySqlAlchemy(isolated_uow).add(user)

    async with isolated_uow.begin():
        loaded = await UserRepositorySqlAlchemy(isolated_uow).get_by_external_sub("sub-xyz")

    assert loaded is not None
    assert loaded.id == user.id


@pytest.mark.integration
async def test_get_by_id_missing(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    async with isolated_uow.begin():
        loaded = await UserRepositorySqlAlchemy(isolated_uow).get_by_id(uuid4())
    assert loaded is None


@pytest.mark.integration
async def test_update_round_trips_profile_changes(
    isolated_uow: SqlAlchemyUnitOfWork,
) -> None:
    now = datetime.now(UTC)
    user = User(
        id_=uuid4(),
        external_sub="sub-2",
        email=Email.parse("two@example.com"),
        created_at=now,
        updated_at=now,
    )

    async with isolated_uow.begin():
        await UserRepositorySqlAlchemy(isolated_uow).add(user)

    user.update_profile(
        display_name="Updated Name",
        locale="en-US",
        timezone="UTC",
        preferences={"theme": "light", "nested": {"x": 1}},
        now=datetime.now(UTC),
    )

    async with isolated_uow.begin():
        await UserRepositorySqlAlchemy(isolated_uow).update(user)

    async with isolated_uow.begin():
        loaded = await UserRepositorySqlAlchemy(isolated_uow).get_by_id(user.id)

    assert loaded is not None
    assert loaded.display_name == "Updated Name"
    assert loaded.locale == "en-US"
    assert loaded.timezone == "UTC"
    assert loaded.preferences == {"theme": "light", "nested": {"x": 1}}
