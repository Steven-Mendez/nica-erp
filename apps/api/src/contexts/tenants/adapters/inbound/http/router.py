"""FastAPI router for the tenants HTTP adapter."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from bootstrap.db import get_uow as get_request_uow
from bootstrap.dependencies import require
from contexts.identity.adapters.inbound.http.dependencies import get_current_user
from contexts.tenants.adapters.inbound.http.dependencies import (
    get_accept_invitation,
    get_cancel_invitation,
    get_create_tenant,
    get_get_my_tenants,
    get_get_tenant,
    get_invitation_repository,
    get_invitation_token_generator,
    get_invite_member,
    get_list_invitations,
    get_list_members,
    get_remove_member,
    get_resend_invitation,
    get_switch_active_tenant,
    get_tenant_repository,
    get_update_member_role,
    get_update_tenant,
)
from contexts.tenants.adapters.inbound.http.schemas import (
    AcceptInvitationResponse,
    AcceptInvitationTokenBundle,
    AuthorizationDgiPayload,
    CreateInvitationRequest,
    CreateTenantRequest,
    InvitationResponse,
    MemberResponse,
    MembersPageResponse,
    MyTenantItem,
    MyTenantsResponse,
    SwitchTenantRequest,
    SwitchTokenResponse,
    TenantResponse,
    UpdateMemberRoleRequest,
    UpdateTenantRequest,
)
from contexts.tenants.application.ports.outbound import (
    InvitationRepository,
    InvitationTokenGenerator,
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
    ResendInvitation,
    SwitchActiveTenant,
    UpdateMemberRole,
    UpdateTenant,
)
from contexts.tenants.application.use_cases.accept_invitation import (
    AcceptInvitationCommand,
)
from contexts.tenants.application.use_cases.cancel_invitation import (
    CancelInvitationCommand,
)
from contexts.tenants.application.use_cases.create_tenant import CreateTenantCommand
from contexts.tenants.application.use_cases.invite_member import InviteMemberCommand
from contexts.tenants.application.use_cases.list_members import (
    LIST_MEMBERS_DEFAULT_LIMIT,
    LIST_MEMBERS_MAX_LIMIT,
    LIST_MEMBERS_MAX_Q_LENGTH,
    ListMembersQuery,
)
from contexts.tenants.application.use_cases.remove_member import RemoveMemberCommand
from contexts.tenants.application.use_cases.resend_invitation import (
    ResendInvitationCommand,
)
from contexts.tenants.application.use_cases.switch_active_tenant import (
    SwitchActiveTenantCommand,
)
from contexts.tenants.application.use_cases.update_member_role import (
    UpdateMemberRoleCommand,
)
from contexts.tenants.application.use_cases.update_tenant import UpdateTenantCommand
from contexts.tenants.domain import AuthorizationDgi, Role, Tenant
from shared_kernel.adapters.context import CurrentUser
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from shared_kernel.permissions import Actor

router = APIRouter()

# Plaintext accept URL the operator email links to. Locally the SPA
# binds it; in AWS CloudFront fronts the SPA at the dist-id host.
# Uses the hash-token form (`#t=<token>`) so the token never reaches the
# server log — the SPA strips it via history.replaceState on mount.
_DEFAULT_INVITE_URL_TEMPLATE = "http://localhost:5173/invitations/accept#t={token}"


def _dgi_to_vo(payload: AuthorizationDgiPayload | None) -> AuthorizationDgi | None:
    # Per ADR-0034: a tenant may have no DGI authorization yet.
    if payload is None:
        return None
    return AuthorizationDgi(
        number=payload.number,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    dgi = tenant.authorization_dgi
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        ruc=tenant.ruc.value if tenant.ruc is not None else None,
        regime=tenant.regime.value if tenant.regime is not None else None,
        departamento=tenant.departamento,
        municipality=tenant.municipality.value if tenant.municipality is not None else None,
        authorization_dgi=AuthorizationDgiPayload(
            number=dgi.number,
            valid_from=dgi.valid_from,
            valid_to=dgi.valid_to,
        )
        if dgi is not None
        else None,
        fiscal_address=tenant.fiscal_address,
        fiscal_email=tenant.fiscal_email.value if tenant.fiscal_email is not None else None,
        fiscal_phone=tenant.fiscal_phone.value if tenant.fiscal_phone is not None else None,
        is_withholder=tenant.is_withholder,
        status=tenant.status,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


# --- POST /v1/tenants (no tenant required, allowlisted) -------------------


@router.post(
    "/v1/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tenants"],
    summary="Create a tenant",
)
async def create_tenant(
    body: CreateTenantRequest,
    current_user: CurrentUser = Depends(get_current_user),
    uc: CreateTenant = Depends(get_create_tenant),
    get: GetTenant = Depends(get_get_tenant),
) -> TenantResponse:
    result = await uc.execute(
        CreateTenantCommand(
            actor_user_id=current_user.user_id,
            name=body.name,
            ruc=body.ruc,
            regime=body.regime,
            departamento=body.departamento,
            municipality=body.municipality,
            authorization_dgi=_dgi_to_vo(body.authorization_dgi),
            fiscal_address=body.fiscal_address,
            fiscal_email=body.fiscal_email,
            fiscal_phone=body.fiscal_phone,
            is_withholder=body.is_withholder,
        )
    )
    # The tenant rows the actor just created are visible because the
    # ``tenant_members_self`` policy returns the row via the user-id
    # branch even before the active tenant is set.
    tenant = await get.execute(tenant_id=result.tenant_id)
    return _tenant_to_response(tenant)


# --- GET /v1/tenants/me ---------------------------------------------------


@router.get(
    "/v1/tenants/me",
    response_model=MyTenantsResponse,
    tags=["tenants"],
    summary="List the caller's memberships",
)
async def get_my_tenants(
    current_user: CurrentUser = Depends(get_current_user),
    uc: GetMyTenants = Depends(get_get_my_tenants),
) -> MyTenantsResponse:
    views = await uc.execute(user_id=current_user.user_id)
    return MyTenantsResponse(
        items=[
            MyTenantItem(
                tenant_id=v.tenant_id,
                name=v.name,
                role=v.role.value,
                status=v.status,
                joined_at=v.joined_at,
            )
            for v in views
        ]
    )


# --- GET /v1/tenants/{id} -------------------------------------------------


@router.get(
    "/v1/tenants/{tenant_id}",
    response_model=TenantResponse,
    tags=["tenants"],
    summary="Read a tenant's fiscal metadata",
)
async def get_tenant(
    tenant_id: UUID,
    _actor: Actor = Depends(require("tenant:read")),
    uc: GetTenant = Depends(get_get_tenant),
) -> TenantResponse:
    tenant = await uc.execute(tenant_id=tenant_id)
    return _tenant_to_response(tenant)


# --- PATCH /v1/tenants/{id} -----------------------------------------------


@router.patch(
    "/v1/tenants/{tenant_id}",
    response_model=TenantResponse,
    tags=["tenants"],
    summary="Update a tenant's fiscal metadata",
)
async def update_tenant(
    tenant_id: UUID,
    body: UpdateTenantRequest,
    _actor: Actor = Depends(require("tenant:write")),
    uc: UpdateTenant = Depends(get_update_tenant),
) -> TenantResponse:
    tenant = await uc.execute(
        UpdateTenantCommand(
            tenant_id=tenant_id,
            name=body.name,
            ruc=body.ruc,
            regime=body.regime,
            departamento=body.departamento,
            municipality=body.municipality,
            authorization_dgi=_dgi_to_vo(body.authorization_dgi)
            if body.authorization_dgi is not None
            else None,
            fiscal_address=body.fiscal_address,
            fiscal_email=body.fiscal_email,
            fiscal_phone=body.fiscal_phone,
            is_withholder=body.is_withholder,
        )
    )
    return _tenant_to_response(tenant)


# --- POST /v1/tenants/{id}/switch -----------------------------------------


@router.post(
    "/v1/tenants/{tenant_id}/switch",
    response_model=SwitchTokenResponse,
    tags=["tenants"],
    summary="Switch the caller's active tenant",
)
async def switch_active_tenant(
    tenant_id: UUID,
    body: SwitchTenantRequest,
    current_user: CurrentUser = Depends(get_current_user),
    uc: SwitchActiveTenant = Depends(get_switch_active_tenant),
) -> SwitchTokenResponse:
    identity = await uc.execute(
        SwitchActiveTenantCommand(
            actor_user_id=current_user.user_id,
            external_sub=current_user.external_sub,
            target_tenant_id=tenant_id,
            refresh_token=body.refresh_token,
        )
    )
    return SwitchTokenResponse(
        access_token=identity.access_token,
        refresh_token=identity.refresh_token,
        id_token=identity.id_token,
    )


# --- Members --------------------------------------------------------------


@router.get(
    "/v1/tenants/{tenant_id}/members",
    response_model=MembersPageResponse,
    tags=["tenants"],
    summary="List members of a tenant (paginated, filterable, sortable)",
)
async def list_members(
    tenant_id: UUID,
    limit: int = Query(default=LIST_MEMBERS_DEFAULT_LIMIT, ge=1, le=LIST_MEMBERS_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=LIST_MEMBERS_MAX_Q_LENGTH),
    roles: list[Literal["owner", "admin", "accountant", "salesperson", "viewer"]] | None = Query(
        default=None
    ),
    statuses: list[Literal["active", "removed"]] | None = Query(default=None),
    sort: Literal["joined_at", "display_name", "email", "role"] = Query(default="joined_at"),
    dir: Literal["asc", "desc"] = Query(default="asc"),
    _actor: Actor = Depends(require("members:read")),
    uc: ListMembers = Depends(get_list_members),
) -> MembersPageResponse:
    query = ListMembersQuery(
        tenant_id=tenant_id,
        q=q,
        roles=tuple(Role(r) for r in (roles or [])),
        statuses=tuple(statuses or []),
        sort=sort,
        dir=dir,
        limit=limit,
        offset=offset,
    )
    result = await uc.execute(query)
    return MembersPageResponse(
        items=[
            MemberResponse(
                user_id=v.user_id,
                tenant_id=v.tenant_id,
                role=v.role.value,
                status=v.status,
                joined_at=v.joined_at,
                removed_at=v.removed_at,
                display_name=v.display_name,
                email=v.email,
            )
            for v in result.items
        ],
        total=result.total,
        limit=query.limit,
        offset=query.offset,
    )


@router.patch(
    "/v1/tenants/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tenants"],
    summary="Change a member's role",
)
async def update_member_role(
    tenant_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    _actor: Actor = Depends(require("members:update-role")),
    uc: UpdateMemberRole = Depends(get_update_member_role),
) -> None:
    await uc.execute(
        UpdateMemberRoleCommand(tenant_id=tenant_id, target_user_id=user_id, new_role=body.role)
    )


@router.delete(
    "/v1/tenants/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tenants"],
    summary="Remove a member from the tenant",
)
async def remove_member(
    tenant_id: UUID,
    user_id: UUID,
    _actor: Actor = Depends(require("members:remove")),
    uc: RemoveMember = Depends(get_remove_member),
) -> None:
    await uc.execute(RemoveMemberCommand(tenant_id=tenant_id, target_user_id=user_id))


# --- Invitations ----------------------------------------------------------


@router.get(
    "/v1/tenants/{tenant_id}/invitations",
    response_model=list[InvitationResponse],
    tags=["tenants"],
    summary="List invitations of a tenant",
)
async def list_invitations(
    tenant_id: UUID,
    _actor: Actor = Depends(require("members:read")),
    uc: ListInvitations = Depends(get_list_invitations),
) -> list[InvitationResponse]:
    invitations = await uc.execute(tenant_id=tenant_id)
    return [
        InvitationResponse(
            id=i.id,
            tenant_id=i.tenant_id,
            email=i.email,
            proposed_role=i.proposed_role.value,
            status=i.status,
            expires_at=i.expires_at,
            created_at=i.created_at,
            cancelled_at=i.cancelled_at,
        )
        for i in invitations
    ]


@router.post(
    "/v1/tenants/{tenant_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tenants"],
    summary="Invite a new member to the tenant",
)
async def invite_member(
    tenant_id: UUID,
    body: CreateInvitationRequest,
    _actor: Actor = Depends(require("members:invite")),
    uc: InviteMember = Depends(get_invite_member),
) -> InvitationResponse:
    result = await uc.execute(
        InviteMemberCommand(
            tenant_id=tenant_id,
            email=body.email,
            proposed_role=body.proposed_role,
            invite_url_template=_DEFAULT_INVITE_URL_TEMPLATE,
        )
    )
    return InvitationResponse(
        id=result.invitation_id,
        tenant_id=tenant_id,
        email=body.email.lower(),
        proposed_role=body.proposed_role,
        status="pending",
        expires_at=result.expires_at,
        created_at=result.expires_at,  # placeholder; full row available via GET
        cancelled_at=None,
    )


@router.delete(
    "/v1/tenants/{tenant_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tenants"],
    summary="Cancel a pending invitation",
)
async def cancel_invitation(
    tenant_id: UUID,
    invitation_id: UUID,
    _actor: Actor = Depends(require("members:invite")),
    uc: CancelInvitation = Depends(get_cancel_invitation),
) -> None:
    await uc.execute(CancelInvitationCommand(tenant_id=tenant_id, invitation_id=invitation_id))


@router.post(
    "/v1/tenants/{tenant_id}/invitations/{invitation_id}/resend",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tenants"],
    summary="Cancel a pending invitation and issue a fresh one",
)
async def resend_invitation(
    tenant_id: UUID,
    invitation_id: UUID,
    _actor: Actor = Depends(require("members:invite")),
    uc: ResendInvitation = Depends(get_resend_invitation),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
) -> InvitationResponse:
    result = await uc.execute(
        ResendInvitationCommand(
            tenant_id=tenant_id,
            invitation_id=invitation_id,
            invite_url_template=_DEFAULT_INVITE_URL_TEMPLATE,
        )
    )
    fresh = await invitation_repo.get(result.invitation_id)
    if fresh is None:
        raise HTTPException(status_code=500, detail="Resend succeeded but row not found")
    return InvitationResponse(
        id=fresh.id,
        tenant_id=fresh.tenant_id,
        email=fresh.email,
        proposed_role=fresh.proposed_role.value,
        status=fresh.status,
        expires_at=fresh.expires_at,
        created_at=fresh.created_at,
        cancelled_at=fresh.cancelled_at,
    )


# --- /v1/invitations/* (public, allowlisted) ------------------------------

public_router = APIRouter()


class AcceptInvitationByBodyRequest(BaseModel):
    """Body shape for the hash-fragment-safe accept endpoint.

    The SPA reads the token from ``location.hash``, strips it via
    ``history.replaceState``, then POSTs the token here so it never
    appears in server logs / Referer headers.

    ``refresh_token`` is optional: when the caller has no prior
    ``custom:active_tenant`` claim and supplies one here, the endpoint
    rotates the caller's session so the new membership's tenant is
    immediately active without a follow-up
    ``POST /v1/tenants/{id}/switch`` round-trip.
    """

    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)


class InvitationPreviewResponse(BaseModel):
    """Public metadata for the pre-signup screen."""

    email: str
    organization_name: str
    role: str


@public_router.post(
    "/v1/invitations/accept",
    response_model=AcceptInvitationResponse,
    tags=["tenants"],
    summary="Accept an invitation token (body-form)",
)
async def accept_invitation_by_body(
    body: AcceptInvitationByBodyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    uc: AcceptInvitation = Depends(get_accept_invitation),
) -> AcceptInvitationResponse:
    # The decision to rotate is taken from the validated
    # `CurrentUser.active_tenant` (sourced from the bearer token), not
    # from any field in the request body — see the use case for why.
    result = await uc.execute(
        AcceptInvitationCommand(
            token=body.token,
            user_id=current_user.user_id,
            external_sub=current_user.external_sub,
            prior_active_tenant=current_user.active_tenant,
            refresh_token=body.refresh_token,
        )
    )
    tokens: AcceptInvitationTokenBundle | None = None
    if result.tokens is not None:
        tokens = AcceptInvitationTokenBundle(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            id_token=result.tokens.id_token,
        )
    return AcceptInvitationResponse(tenant_id=result.tenant_id, role=result.role, tokens=tokens)


@public_router.get(
    "/v1/invitations/{token}/preview",
    response_model=InvitationPreviewResponse,
    tags=["tenants"],
    summary="Preview an invitation (email + organization + role)",
)
async def preview_invitation(
    token: str,
    token_generator: InvitationTokenGenerator = Depends(get_invitation_token_generator),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> InvitationPreviewResponse:
    """Return safe metadata for the pre-signup screen.

    The response exposes only fields the recipient already has from
    the invitation email — never tenant fiscal data or membership
    rosters. The token must validate; expired / unknown tokens
    return 404 so we don't reveal which tokens exist.
    """

    try:
        token_generator.verify(token=token)
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(status_code=404, detail="Invitation not found") from exc

    token_hash = token_generator.hash(token=token)
    async with uow.begin():
        invitation = await invitation_repo.get_by_token_hash(token_hash)
        if invitation is None or invitation.status != "pending":
            raise HTTPException(status_code=404, detail="Invitation not found")
        tenant = await tenant_repo.get(invitation.tenant_id)
        if tenant is None:  # pragma: no cover — defensive
            raise HTTPException(status_code=404, detail="Invitation not found")
        return InvitationPreviewResponse(
            email=invitation.email,
            organization_name=tenant.name,
            role=invitation.proposed_role.value,
        )


__all__ = ["public_router", "router"]
