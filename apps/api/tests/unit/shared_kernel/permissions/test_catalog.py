"""Unit tests for the RBAC catalog."""

from __future__ import annotations

import asyncio
import time

from shared_kernel.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLES,
    TENANT_PERMISSIONS,
    PermissionCache,
)


class TestCatalog:
    def test_tenant_permissions_count(self) -> None:
        assert len(TENANT_PERMISSIONS) == 6

    def test_owner_holds_every_tenant_code(self) -> None:
        tenant_codes = {p.code for p in TENANT_PERMISSIONS}
        assert DEFAULT_ROLE_PERMISSIONS["owner"] == tenant_codes

    def test_roles_order(self) -> None:
        assert ROLES == ("viewer", "salesperson", "accountant", "admin", "owner")

    def test_admin_can_invite(self) -> None:
        assert "members:invite" in DEFAULT_ROLE_PERMISSIONS["admin"]

    def test_viewer_cannot_write(self) -> None:
        assert "tenant:write" not in DEFAULT_ROLE_PERMISSIONS["viewer"]


class TestPermissionCache:
    def test_hits_cache_within_ttl(self) -> None:
        async def runner() -> None:
            calls = {"n": 0}

            async def loader(role: str) -> frozenset[str]:
                calls["n"] += 1
                return frozenset({f"{role}:read"})

            cache = PermissionCache(ttl_seconds=60)
            a = await cache.get("admin", loader)
            b = await cache.get("admin", loader)
            assert a == b == frozenset({"admin:read"})
            assert calls["n"] == 1

        asyncio.run(runner())

    def test_ttl_expiry_refetches(self) -> None:
        async def runner() -> None:
            calls = {"n": 0}

            async def loader(role: str) -> frozenset[str]:
                calls["n"] += 1
                return frozenset({f"{role}:v{calls['n']}"})

            cache = PermissionCache(ttl_seconds=0.0)
            await cache.get("admin", loader)
            time.sleep(0.01)
            await cache.get("admin", loader)
            assert calls["n"] == 2

        asyncio.run(runner())
