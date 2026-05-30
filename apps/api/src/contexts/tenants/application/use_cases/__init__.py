"""Tenants use cases — one keyword-only dataclass per use case."""

from __future__ import annotations

from contexts.tenants.application.use_cases.accept_invitation import AcceptInvitation
from contexts.tenants.application.use_cases.cancel_invitation import CancelInvitation
from contexts.tenants.application.use_cases.create_tenant import CreateTenant
from contexts.tenants.application.use_cases.get_my_tenants import GetMyTenants
from contexts.tenants.application.use_cases.get_tenant import GetTenant
from contexts.tenants.application.use_cases.invite_member import InviteMember
from contexts.tenants.application.use_cases.list_invitations import ListInvitations
from contexts.tenants.application.use_cases.list_members import ListMembers
from contexts.tenants.application.use_cases.remove_member import RemoveMember
from contexts.tenants.application.use_cases.switch_active_tenant import (
    SwitchActiveTenant,
)
from contexts.tenants.application.use_cases.update_member_role import UpdateMemberRole
from contexts.tenants.application.use_cases.update_tenant import UpdateTenant

__all__ = [
    "AcceptInvitation",
    "CancelInvitation",
    "CreateTenant",
    "GetMyTenants",
    "GetTenant",
    "InviteMember",
    "ListInvitations",
    "ListMembers",
    "RemoveMember",
    "SwitchActiveTenant",
    "UpdateMemberRole",
    "UpdateTenant",
]
