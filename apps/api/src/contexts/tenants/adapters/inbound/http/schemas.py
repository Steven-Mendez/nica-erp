"""Pydantic v2 request/response models for the tenants HTTP adapter."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- shared ---------------------------------------------------------------


class AuthorizationDgiPayload(BaseModel):
    number: str = Field(examples=["A-001"], max_length=32)
    valid_from: date = Field(examples=["2026-01-01"])
    valid_to: date = Field(examples=["2027-01-01"])


# --- create / update tenant -----------------------------------------------


class CreateTenantRequest(BaseModel):
    name: str = Field(examples=["Mi Empresa"], max_length=200)
    ruc: str | None = Field(default=None, examples=["0010101800010X"])
    regime: Literal["general", "simplified"] | None = Field(default=None, examples=["general"])
    municipality: str | None = Field(default=None, examples=["Managua"])
    authorization_dgi: AuthorizationDgiPayload | None = Field(default=None)
    fiscal_address: str | None = Field(
        default=None,
        examples=["Rotonda Centroamérica, Managua"],
        max_length=500,
    )
    is_withholder: bool = Field(default=False)


class UpdateTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    regime: Literal["general", "simplified"] | None = None
    municipality: str | None = None
    authorization_dgi: AuthorizationDgiPayload | None = None
    fiscal_address: str | None = Field(default=None, max_length=500)
    is_withholder: bool | None = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    ruc: str | None = None
    regime: Literal["general", "simplified"] | None = None
    municipality: str | None = None
    authorization_dgi: AuthorizationDgiPayload | None = None
    fiscal_address: str | None = None
    is_withholder: bool
    status: str
    created_at: datetime
    updated_at: datetime


# --- switch tenant --------------------------------------------------------


class SwitchTenantRequest(BaseModel):
    refresh_token: str


class SwitchTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    id_token: str
    token_type: Literal["Bearer"] = "Bearer"


# --- members --------------------------------------------------------------


class MemberResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: Literal["owner", "admin", "accountant", "salesperson", "viewer"]
    status: Literal["active", "removed"]
    joined_at: datetime
    removed_at: datetime | None = None
    display_name: str | None = None
    email: str | None = None


class UpdateMemberRoleRequest(BaseModel):
    role: Literal["admin", "accountant", "salesperson", "viewer"]


# --- invitations ----------------------------------------------------------


class InvitationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    proposed_role: Literal["admin", "accountant", "salesperson", "viewer"]
    status: Literal["pending", "accepted", "cancelled", "expired"]
    expires_at: datetime
    created_at: datetime
    cancelled_at: datetime | None = None


class CreateInvitationRequest(BaseModel):
    email: str = Field(examples=["x@test.dev"], max_length=320)
    proposed_role: Literal["admin", "accountant", "salesperson", "viewer"] = Field(
        examples=["accountant"]
    )


class AcceptInvitationResponse(BaseModel):
    tenant_id: UUID
    role: Literal["admin", "accountant", "salesperson", "viewer"]


# --- my tenants -----------------------------------------------------------


class MyTenantItem(BaseModel):
    tenant_id: UUID
    name: str
    role: Literal["owner", "admin", "accountant", "salesperson", "viewer"]
    status: str
    joined_at: datetime


class MyTenantsResponse(BaseModel):
    items: list[MyTenantItem]


__all__ = [
    "AcceptInvitationResponse",
    "AuthorizationDgiPayload",
    "CreateInvitationRequest",
    "CreateTenantRequest",
    "InvitationResponse",
    "MemberResponse",
    "MyTenantItem",
    "MyTenantsResponse",
    "SwitchTenantRequest",
    "SwitchTokenResponse",
    "TenantResponse",
    "UpdateMemberRoleRequest",
    "UpdateTenantRequest",
]
