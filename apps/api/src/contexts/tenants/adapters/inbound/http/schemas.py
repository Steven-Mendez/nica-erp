"""Pydantic v2 request/response models for the tenants HTTP adapter."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contexts.tenants.domain.departamento import KNOWN_DEPARTAMENTOS

# --- shared ---------------------------------------------------------------


class AuthorizationDgiPayload(BaseModel):
    number: str = Field(examples=["A-001"], max_length=32)
    valid_from: date = Field(examples=["2026-01-01"])
    valid_to: date = Field(examples=["2027-01-01"])


# --- create / update tenant -----------------------------------------------


RegimeLiteral = Literal["general", "cuota_fija", "pequeno_contribuyente"]


class CreateTenantRequest(BaseModel):
    name: str = Field(examples=["Mi Empresa"], max_length=200)
    ruc: str | None = Field(default=None, examples=["0010101800010X"])
    regime: RegimeLiteral | None = Field(default=None, examples=["general"])
    departamento: str | None = Field(default=None, examples=["Managua"], max_length=64)
    municipality: str | None = Field(default=None, examples=["Managua"])
    authorization_dgi: AuthorizationDgiPayload | None = Field(default=None)
    fiscal_address: str | None = Field(
        default=None,
        examples=["Rotonda Centroamérica, Managua"],
        max_length=500,
    )
    fiscal_email: str | None = Field(
        default=None, examples=["facturacion@miempresa.ni"], max_length=320
    )
    fiscal_phone: str | None = Field(default=None, examples=["+505 8888-8888"], max_length=32)
    is_withholder: bool = Field(default=False)

    @field_validator("name", "fiscal_address", "fiscal_email", "fiscal_phone", mode="before")
    @classmethod
    def reject_angle_brackets(cls, v: object) -> object:
        # Audit F-019: silently stripping `<` and `>` corrupted the
        # operator's input. Reject loudly with a Spanish copy instead.
        if isinstance(v, str) and ("<" in v or ">" in v):
            raise ValueError('El nombre no puede contener "<" o ">".')
        return v

    @field_validator("departamento", mode="after")
    @classmethod
    def validate_departamento(cls, v: str | None) -> str | None:
        # Audit F-006: pin `departamento` to the 17-value catalog so the
        # wizard / settings editor cannot persist a free-text typo.
        if v is None or v == "":
            return v
        if v not in KNOWN_DEPARTAMENTOS:
            raise ValueError("Departamento inválido")
        return v


class UpdateTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    ruc: str | None = Field(default=None, examples=["0010101800010X"])
    regime: RegimeLiteral | None = None
    departamento: str | None = Field(default=None, max_length=64)
    municipality: str | None = None
    authorization_dgi: AuthorizationDgiPayload | None = None
    fiscal_address: str | None = Field(default=None, max_length=500)
    fiscal_email: str | None = Field(default=None, max_length=320)
    fiscal_phone: str | None = Field(default=None, max_length=32)
    is_withholder: bool | None = None

    @field_validator("name", "fiscal_address", "fiscal_email", "fiscal_phone", mode="before")
    @classmethod
    def reject_angle_brackets(cls, v: object) -> object:
        # Audit F-019 — see CreateTenantRequest.reject_angle_brackets.
        if isinstance(v, str) and ("<" in v or ">" in v):
            raise ValueError('El nombre no puede contener "<" o ">".')
        return v

    @field_validator("departamento", mode="after")
    @classmethod
    def validate_departamento(cls, v: str | None) -> str | None:
        # Audit F-006 — see CreateTenantRequest.validate_departamento.
        if v is None or v == "":
            return v
        if v not in KNOWN_DEPARTAMENTOS:
            raise ValueError("Departamento inválido")
        return v


class TenantResponse(BaseModel):
    id: UUID
    name: str
    ruc: str | None = None
    regime: RegimeLiteral | None = None
    departamento: str | None = None
    municipality: str | None = None
    authorization_dgi: AuthorizationDgiPayload | None = None
    fiscal_address: str | None = None
    fiscal_email: str | None = None
    fiscal_phone: str | None = None
    is_withholder: bool
    status: str
    created_at: datetime
    updated_at: datetime


# --- switch tenant --------------------------------------------------------


class SwitchTenantRequest(BaseModel):
    # Optional: the use case prefers the `nica_erp_rt` cookie. The
    # body field stays for one transition cycle so older SPA builds
    # still work; new SPA builds POST `{}` with `credentials: include`.
    refresh_token: str | None = None


class SwitchTokenResponse(BaseModel):
    # Refresh token rides exclusively in the `nica_erp_rt` cookie set
    # by the switch endpoint (`response.set_cookie`); the body only
    # carries the rotated access + id tokens.
    access_token: str
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


class MembersPageResponse(BaseModel):
    """Paginated envelope for the members list endpoint.

    ``total`` is the count of members matching the filter predicates,
    *ignoring* ``limit`` / ``offset``. ``limit`` and ``offset`` echo
    the effective request values so the SPA can build a pagination
    footer without re-reading the URL.
    """

    items: list[MemberResponse]
    total: int
    limit: int
    offset: int


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

    @field_validator("email", mode="before")
    @classmethod
    def reject_angle_brackets(cls, v: object) -> object:
        if isinstance(v, str) and ("<" in v or ">" in v):
            raise ValueError('El correo no puede contener "<" o ">".')
        return v


class AcceptInvitationTokenBundle(BaseModel):
    """Token bundle returned when the caller's session is rotated.

    Mirrors the identity context's ``TokenResponse`` shape so the SPA can
    pass either object to its ``storeTokens()`` helper without branching.
    The refresh token rides exclusively in the ``nica_erp_rt`` cookie set
    by the accept endpoint when a rotation occurs.
    """

    access_token: str
    id_token: str
    token_type: Literal["Bearer"] = "Bearer"


class AcceptInvitationResponse(BaseModel):
    tenant_id: UUID
    role: Literal["admin", "accountant", "salesperson", "viewer"]
    # Non-null only when the caller had no prior `custom:active_tenant`
    # and supplied a refresh token; rotating the session in that case
    # spares the SPA from a separate `POST /v1/tenants/{id}/switch`
    # round-trip. Veteran callers receive ``null`` and keep their
    # current active empresa.
    tokens: AcceptInvitationTokenBundle | None = None


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
    "AcceptInvitationTokenBundle",
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
