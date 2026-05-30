"""Integration tests for :class:`TenantRepositorySqlAlchemy`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from contexts.tenants.adapters.outbound.persistence.sqlalchemy.tenant_repository import (
    TenantRepositorySqlAlchemy,
)
from contexts.tenants.domain import (
    AuthorizationDgi,
    Municipality,
    Regime,
    Ruc,
    Tenant,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


def _tenant() -> Tenant:
    now = datetime.now(UTC)
    return Tenant.register(
        name="Empresa Z",
        ruc=Ruc.parse("0010101800010X"),
        regime=Regime("general"),
        municipality=Municipality("Managua"),
        authorization_dgi=AuthorizationDgi(
            number="A-001",
            valid_from=date(2026, 1, 1),
            valid_to=date(2027, 1, 1),
        ),
        fiscal_address="Rotonda Centroamérica",
        is_withholder=False,
        now=now,
        id_=uuid4(),
    )


@pytest.mark.integration
async def test_add_and_get_by_id(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    tenant = _tenant()
    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        await repo.add(tenant)

    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get(tenant.id)

    assert loaded is not None
    assert loaded.id == tenant.id
    assert loaded.name == "Empresa Z"
    assert loaded.ruc.value == "0010101800010X"
    assert loaded.regime.value == "general"
    assert loaded.is_withholder is False


@pytest.mark.integration
async def test_get_by_ruc_finds_known_tenant(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    tenant = _tenant()
    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        await repo.add(tenant)

    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get_by_ruc("0010101800010X")

    assert loaded is not None
    assert loaded.id == tenant.id


@pytest.mark.integration
async def test_get_returns_none_for_missing(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get(uuid4())
    assert loaded is None


@pytest.mark.integration
async def test_update_persists_changes(isolated_uow: SqlAlchemyUnitOfWork) -> None:
    tenant = _tenant()
    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        await repo.add(tenant)

    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        loaded = await repo.get(tenant.id)
        assert loaded is not None
        loaded.update_fiscal(now=datetime.now(UTC), name="Empresa Z Renamed")
        await repo.update(loaded)

    async with isolated_uow.begin():
        repo = TenantRepositorySqlAlchemy(isolated_uow)
        reloaded = await repo.get(tenant.id)
    assert reloaded is not None
    assert reloaded.name == "Empresa Z Renamed"
