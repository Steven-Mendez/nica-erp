"""FastAPI dependency factories for the tenants HTTP adapter."""

from __future__ import annotations

from fastapi import Depends

from bootstrap.container import (
    build_email_sender,
    build_identity_provider_for_request,
    build_invitation_repository,
    build_invitation_token_generator,
    build_membership_repository,
    build_tenant_repository,
)
from bootstrap.dependencies import get_request_uow
from contexts.identity.application.ports.outbound import IdentityProvider
from contexts.tenants.application.ports.outbound import (
    InvitationRepository,
    InvitationTokenGenerator,
    MembershipRepository,
    TenantRepository,
)
from contexts.tenants.application.use_cases import (
    AcceptInvitation,
    CancelInvitation,
    CreateTenant,
    GetMyTenants,
    GetTenant,
    InviteMember,
    ListInvitations,
    ListMembers,
    RemoveMember,
    SwitchActiveTenant,
    UpdateMemberRole,
    UpdateTenant,
)
from shared_kernel.adapters.outbox_sqlalchemy import OutboxWriterSqlAlchemy
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork


def get_tenant_repository(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> TenantRepository:
    return build_tenant_repository(uow)


def get_membership_repository(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> MembershipRepository:
    return build_membership_repository(uow)


def get_invitation_repository(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> InvitationRepository:
    return build_invitation_repository(uow)


def get_invitation_token_generator() -> InvitationTokenGenerator:
    return build_invitation_token_generator()


def get_identity_provider_for_tenants(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> IdentityProvider:
    return build_identity_provider_for_request(uow)


def get_outbox(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> OutboxWriterSqlAlchemy:
    return OutboxWriterSqlAlchemy(uow)


# --- Use case factories ---------------------------------------------------


def get_create_tenant(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
) -> CreateTenant:
    return CreateTenant(
        uow=uow,
        tenant_repository=tenant_repo,
        membership_repository=membership_repo,
        outbox=outbox,
    )


def get_get_my_tenants(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
) -> GetMyTenants:
    return GetMyTenants(
        uow=uow, membership_repository=membership_repo, tenant_repository=tenant_repo
    )


def get_get_tenant(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
) -> GetTenant:
    return GetTenant(uow=uow, tenant_repository=tenant_repo)


def get_update_tenant(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
) -> UpdateTenant:
    return UpdateTenant(uow=uow, tenant_repository=tenant_repo)


def get_invite_member(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    token_gen: InvitationTokenGenerator = Depends(get_invitation_token_generator),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
) -> InviteMember:
    return InviteMember(
        uow=uow,
        tenant_repository=tenant_repo,
        invitation_repository=invitation_repo,
        token_generator=token_gen,
        email_sender=build_email_sender(),
        outbox=outbox,
    )


def get_accept_invitation(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    token_gen: InvitationTokenGenerator = Depends(get_invitation_token_generator),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
    idp: IdentityProvider = Depends(get_identity_provider_for_tenants),
) -> AcceptInvitation:
    return AcceptInvitation(
        uow=uow,
        invitation_repository=invitation_repo,
        membership_repository=membership_repo,
        token_generator=token_gen,
        outbox=outbox,
        identity_provider=idp,
    )


def get_cancel_invitation(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
) -> CancelInvitation:
    return CancelInvitation(uow=uow, invitation_repository=invitation_repo, outbox=outbox)


def get_remove_member(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
) -> RemoveMember:
    return RemoveMember(uow=uow, membership_repository=membership_repo, outbox=outbox)


def get_update_member_role(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    outbox: OutboxWriterSqlAlchemy = Depends(get_outbox),
) -> UpdateMemberRole:
    return UpdateMemberRole(uow=uow, membership_repository=membership_repo, outbox=outbox)


def get_list_members(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> ListMembers:
    return ListMembers(uow=uow, membership_repository=membership_repo)


def get_list_invitations(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
) -> ListInvitations:
    return ListInvitations(uow=uow, invitation_repository=invitation_repo)


def get_switch_active_tenant(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    idp: IdentityProvider = Depends(get_identity_provider_for_tenants),
) -> SwitchActiveTenant:
    return SwitchActiveTenant(uow=uow, membership_repository=membership_repo, identity_provider=idp)


__all__ = [
    "get_accept_invitation",
    "get_cancel_invitation",
    "get_create_tenant",
    "get_get_my_tenants",
    "get_get_tenant",
    "get_invite_member",
    "get_list_invitations",
    "get_list_members",
    "get_remove_member",
    "get_switch_active_tenant",
    "get_update_member_role",
    "get_update_tenant",
]
