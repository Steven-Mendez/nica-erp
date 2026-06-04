"""Map tenants/RBAC domain errors to RFC-7807 problem details."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from contexts.identity.adapters.inbound.http.errors import PROBLEM_CONTENT_TYPE
from contexts.identity.adapters.inbound.http.schemas import ProblemDetail
from contexts.tenants.domain import (
    CannotDemoteOwnerError,
    CannotRemoveOwnerError,
    InvitationAlreadyAcceptedError,
    InvitationCancelledError,
    InvitationDuplicatePendingError,
    InvitationExpiredError,
    InvitationIdentityMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    NotAMemberError,
    OwnerAlreadyExistsError,
    OwnerRoleNotAllowedHereError,
    RucCollisionError,
    TenantNotFoundError,
)
from shared_kernel.permissions import ForbiddenError


def _problem_response(status: int, problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        content=problem.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def register_tenants_exception_handlers(app: FastAPI) -> None:
    """Wire tenants/RBAC exceptions to RFC-7807 responses on ``app``."""

    @app.exception_handler(ForbiddenError)
    async def _forbidden(_request: Request, exc: ForbiddenError) -> JSONResponse:
        # Audit F-030: detail is a generic Spanish copy; the missing
        # permission list is emitted only when non-empty so an empty
        # array does not appear in the body.
        problem = ProblemDetail(
            status=403,
            code="missing-permission",
            title="Acceso denegado",
            detail="Acceso denegado: faltan permisos.",
        )
        body = problem.model_dump(mode="json", exclude_none=True)
        missing = list(exc.missing)
        if missing:
            body["missing"] = missing
        return JSONResponse(content=body, status_code=403, media_type=PROBLEM_CONTENT_TYPE)

    @app.exception_handler(TenantNotFoundError)
    async def _tenant_not_found(_request: Request, exc: TenantNotFoundError) -> JSONResponse:
        return _problem_response(
            404,
            ProblemDetail(
                status=404, code="tenants.not_found", title="Tenant not found", detail=str(exc)
            ),
        )

    @app.exception_handler(NotAMemberError)
    async def _not_a_member(_request: Request, _exc: NotAMemberError) -> JSONResponse:
        # Audit F-030: detail SHALL NOT embed the tenant UUID or any
        # internal identifier.
        return _problem_response(
            403,
            ProblemDetail(
                status=403,
                code="tenant.not_member",
                title="Acceso denegado",
                detail="Acceso denegado.",
            ),
        )

    @app.exception_handler(RucCollisionError)
    async def _ruc_collision(_request: Request, exc: RucCollisionError) -> JSONResponse:
        return _problem_response(
            409,
            ProblemDetail(
                status=409,
                code="tenants.ruc_collision",
                title="RUC already in use",
                detail=str(exc),
            ),
        )

    @app.exception_handler(OwnerAlreadyExistsError)
    async def _owner_already_exists(
        _request: Request, exc: OwnerAlreadyExistsError
    ) -> JSONResponse:
        return _problem_response(
            409,
            ProblemDetail(
                status=409,
                code="tenants.owner_already_exists",
                title="Owner already exists",
                detail=str(exc),
            ),
        )

    @app.exception_handler(OwnerRoleNotAllowedHereError)
    async def _owner_not_here(_request: Request, exc: OwnerRoleNotAllowedHereError) -> JSONResponse:
        return _problem_response(
            422,
            ProblemDetail(
                status=422,
                code="validation.request_invalid",
                title="Owner role not allowed",
                detail=str(exc),
            ),
        )

    @app.exception_handler(CannotRemoveOwnerError)
    async def _cant_remove_owner(_request: Request, exc: CannotRemoveOwnerError) -> JSONResponse:
        return _problem_response(
            409,
            ProblemDetail(
                status=409,
                code="tenants.cannot_remove_owner",
                title="Cannot remove the owner",
                detail=str(exc),
            ),
        )

    @app.exception_handler(CannotDemoteOwnerError)
    async def _cant_demote_owner(_request: Request, exc: CannotDemoteOwnerError) -> JSONResponse:
        return _problem_response(
            409,
            ProblemDetail(
                status=409,
                code="tenants.cannot_demote_owner",
                title="Cannot demote the owner",
                detail=str(exc),
            ),
        )

    @app.exception_handler(InvitationExpiredError)
    async def _inv_expired(_request: Request, exc: InvitationExpiredError) -> JSONResponse:
        return _problem_response(
            410,
            ProblemDetail(
                status=410, code="invitation.expired", title="Invitation expired", detail=str(exc)
            ),
        )

    @app.exception_handler(InvitationAlreadyAcceptedError)
    async def _inv_accepted(_request: Request, exc: InvitationAlreadyAcceptedError) -> JSONResponse:
        return _problem_response(
            410,
            ProblemDetail(
                status=410,
                code="invitation.already_accepted",
                title="Invitation already accepted",
                detail=str(exc),
            ),
        )

    @app.exception_handler(InvitationCancelledError)
    async def _inv_cancelled(_request: Request, exc: InvitationCancelledError) -> JSONResponse:
        return _problem_response(
            410,
            ProblemDetail(
                status=410,
                code="invitation.cancelled",
                title="Invitation cancelled",
                detail=str(exc),
            ),
        )

    @app.exception_handler(InvitationInvalidError)
    async def _inv_invalid(_request: Request, exc: InvitationInvalidError) -> JSONResponse:
        return _problem_response(
            410,
            ProblemDetail(
                status=410, code="invitation.invalid", title="Invitation invalid", detail=str(exc)
            ),
        )

    @app.exception_handler(InvitationNotFoundError)
    async def _inv_not_found(_request: Request, exc: InvitationNotFoundError) -> JSONResponse:
        return _problem_response(
            410,
            ProblemDetail(
                status=410,
                code="invitation.not_found",
                title="Invitation not found",
                detail=str(exc),
            ),
        )

    @app.exception_handler(InvitationIdentityMismatchError)
    async def _inv_identity_mismatch(
        _request: Request, _exc: InvitationIdentityMismatchError
    ) -> JSONResponse:
        # Detail SHALL NOT leak the JWT sub to the requester.
        return _problem_response(
            403,
            ProblemDetail(
                status=403,
                code="invitation.identity_mismatch",
                title="Esta invitación no es para ti",
                detail=None,
            ),
        )

    @app.exception_handler(InvitationDuplicatePendingError)
    async def _inv_dup_pending(
        _request: Request, exc: InvitationDuplicatePendingError
    ) -> JSONResponse:
        return _problem_response(
            409,
            ProblemDetail(
                status=409,
                code="tenants.invitation_duplicate_pending",
                title="A pending invitation already exists",
                detail=str(exc),
            ),
        )


__all__ = ["register_tenants_exception_handlers"]
